# Information Model

**Status**: Code-only reconstruction

No generic `Information` model was found in `src/tinycua/tinycua/models/` during code exploration.

The implemented structured information carrier is `DigestedInformation`. Evidence: `src/tinycua/tinycua/models/digested_information.py:8-58`.

The digester tool returns a simple dict with `digest` and `format`. Evidence: `src/tinycua/tinycua/tools/digest_information.py:13-40`.
