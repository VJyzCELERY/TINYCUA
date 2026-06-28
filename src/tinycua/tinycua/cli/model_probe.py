"""Best-effort probe for the served model's real context length (FR-084).

LM Studio and Ollama expose ``context_length`` on their OpenAI-compatible
``GET /v1/models`` endpoint. Vanilla OpenAI cloud omits the field. This
module probes the server once at startup so the compaction threshold
(``compaction_threshold * max_context``, float 0-1 default 0.7) tracks the
real wall instead of the SDK's optimistic ``128_000`` default.

The probe is best-effort: any failure (network, parse, missing field) falls
back silently to the caller-provided ``fallback``. Never raises.
"""

from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


async def resolve_max_context(
    base_url: str,
    api_key: str,
    model_name: str,
    fallback: int,
) -> int:
    """Return the served model's context length, or fallback on any failure.

    Probes ``GET {base_url}/v1/models`` via the OpenAI SDK. Tries (in order):
      1. ``context_length`` field on each model object (LM Studio/Ollama
         extension — present on the OpenAI-compatible endpoint).
      2. ``fallback`` (the SDK ``LanguageModel.max_context`` passed in).

    Any exception (network, parse, missing field, empty list) → return
    ``fallback`` with a DEBUG log. Never raises.

    Args:
        base_url: The provider base URL (e.g. ``http://localhost:1234/v1``).
        api_key: The API key (may be empty for local servers).
        model_name: The model name to match (best-effort; falls back to the
            first model with a ``context_length`` if no name match).
        fallback: The fallback context length when the probe fails.

    Returns:
        The resolved context length (int > 0), or ``fallback``.
    """
    try:
        client = AsyncOpenAI(api_key=api_key or "", base_url=base_url)
        try:
            models = await client.models.list()
        finally:
            await client.close()

        data: list[Any] = getattr(models, "data", []) or []
        if not data:
            logger.info("max_context_probe_empty_models fallback=%d", fallback)
            return fallback

        # Prefer a name match; fall back to the first model with a context_length.
        name_lower = model_name.lower()
        first_with_ctx: int | None = None
        for m in data:
            cl = _extract_context_length(m)
            if cl is None or cl <= 0:
                continue
            if first_with_ctx is None:
                first_with_ctx = cl
            mid = str(getattr(m, "id", "") or "").lower()
            if mid and name_lower and (name_lower in mid or mid in name_lower):
                logger.info(
                    "max_context_probed model=%s context_length=%d", m.id, cl
                )
                return cl

        if first_with_ctx is not None:
            logger.info(
                "max_context_probed_first context_length=%d", first_with_ctx
            )
            return first_with_ctx

        logger.info("max_context_probe_no_field fallback=%d", fallback)
        return fallback
    except Exception:  # noqa: BLE001 — best-effort probe, never raises.
        logger.debug("max_context_probe_failed fallback=%d", fallback, exc_info=True)
        return fallback


def _extract_context_length(model: Any) -> int | None:
    """Extract context_length from a model object across server variants.

    LM Studio /v1/models puts ``context_length`` on the top-level model
    object. Ollama does the same. Some variants nest it under
    ``loaded_instances[0].config.context_length``. This helper checks
    the common shapes.

    Args:
        model: A model object from the OpenAI SDK models.list() response.

    Returns:
        The context length as a positive int, or None when absent/invalid.
    """
    # Top-level context_length (LM Studio /v1/models, Ollama).
    cl = getattr(model, "context_length", None)
    if isinstance(cl, (int, float)) and cl > 0:
        return int(cl)
    # Some servers nest it under loaded_instances[0].config.context_length.
    instances = getattr(model, "loaded_instances", None)
    if instances and isinstance(instances, list) and len(instances) > 0:
        cfg = getattr(instances[0], "config", None)
        if cfg is not None:
            cl = getattr(cfg, "context_length", None)
            if isinstance(cl, (int, float)) and cl > 0:
                return int(cl)
    # Raw dict shape (some SDK versions return dicts).
    if isinstance(model, dict):
        cl = model.get("context_length")
        if isinstance(cl, (int, float)) and cl > 0:
            return int(cl)
        insts = model.get("loaded_instances")
        if isinstance(insts, list) and insts:
            cfg = insts[0].get("config") if isinstance(insts[0], dict) else None
            if isinstance(cfg, dict):
                cl = cfg.get("context_length")
                if isinstance(cl, (int, float)) and cl > 0:
                    return int(cl)
    return None
