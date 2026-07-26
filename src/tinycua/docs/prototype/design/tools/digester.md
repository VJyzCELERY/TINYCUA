# Digester Tools

**Status**: Code-only reconstruction

`DigestInformationTool` is the InformationDigester's required structured commit. It
validates a context summary, key points, advisory instructions, constraints, and known
gaps, then returns those fields with an explicit success flag. Evidence:
`src/tinycua/tinycua/tools/digest_information.py`.

`EnhancedContextRetrievalTool` is a `Tool` named `enhanced_context_retrieval` that caches by serialized session context and returns stub search results. Evidence: `src/tinycua/tinycua/tools/enhanced_context_retrieval.py:16-104`.

`information_digester_tool_scope()` includes both tools and selected read-only
exploration tools. Evidence: `src/tinycua/tinycua/config/tool_scopes.py`.
