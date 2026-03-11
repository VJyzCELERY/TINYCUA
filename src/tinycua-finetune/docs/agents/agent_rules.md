# Subproject-Specific Agent Rules

This document outlines rules for using AI agents specifically in tinycua-finetune.

## Additional Rules for tinycua-finetune

- Always read `specs/spec.md` and `specs/design.md` before generating any training or
  conversion code.
- Training scripts must never hardcode model paths, dataset paths, or credentials.
  Use CLI arguments or environment variables only.
- Generated training code must be compatible with the three supported modes:
  `qlora`, `lora`, and `offload`. Do not add new modes without an approved spec change.
- Dataset records and tool manifests must be validated against their defined schemas
  before use. Never silently ignore missing required fields.
- Do not add new Python dependencies without updating `requirements.txt`.
- All generated code must pass `make lint`, `make test`, and `make complexity`.
