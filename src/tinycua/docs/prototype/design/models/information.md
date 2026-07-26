# Information Model

**Status**: Code-only reconstruction

No generic `Information` model was found in `src/tinycua/tinycua/models/` during code exploration.

The implemented structured information carrier is `DigestedInformation`. Evidence: `src/tinycua/tinycua/models/digested_information.py:8-58`.

The digester tool returns validated fields matching `DigestedInformation`, together
with an explicit success flag. The runtime attaches the original query. Evidence:
`src/tinycua/tinycua/tools/digest_information.py`.
