# Digester Tools

**Status**: Code-only reconstruction

`DigestInformationTool` is a `Tool` named `digest_information` that returns `{"digest": information, "format": "structured"}`. Evidence: `src/tinycua/tinycua/tools/digest_information.py:13-40`.

`EnhancedContextRetrievalTool` is a `Tool` named `enhanced_context_retrieval` that caches by serialized session context and returns stub search results. Evidence: `src/tinycua/tinycua/tools/enhanced_context_retrieval.py:16-104`.

`information_digester_tool_scope()` includes both tools and no outer agent tools. Evidence: `src/tinycua/tinycua/config/tool_scopes.py:45-60`.
