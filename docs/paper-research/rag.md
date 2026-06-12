# Literature Review: Retrieval-Augmented Generation (RAG)

## Draft

Retrieval-Augmented Generation (RAG) addresses the knowledge limitations of language models by grounding generation in external retrieved documents (Lewis et al., 2020). In its Naive form, RAG follows a straightforward retrieve-then-generate pipeline: relevant documents are fetched from a knowledge base and concatenated with the user query as input to the model. While effective for knowledge access, Naive RAG suffers from noisy retrieval and context bloat — retrieved documents often include irrelevant content that pollutes the generation process (Gao et al., 2024).

Researchers enhance Advanced RAG through pre-retrieval and post-retrieval optimization strategies that improve both the quality of retrieved documents and how effectively the model uses them (Gao et al., 2024). Pre-retrieval techniques refine queries and index structures before retrieval, while post-retrieval methods re-rank, filter, or compress retrieved content to reduce noise. Despite these improvements, Advanced RAG still processes all retrieved content within a single model, leaving the fundamental problem of context bloat unresolved. Modular RAG further extends the paradigm by introducing composable retrieval and generation components that can be orchestrated for specific task requirements (Gao et al., 2024).

However, RAG fundamentally addresses knowledge access, not context management — all retrieved documents are passed to a single model that must attend to, filter, and reason over the full set. TinyCUA extends the RAG paradigm by decomposing context across staged processing nodes, where each node receives only the context relevant to its specific responsibility.
