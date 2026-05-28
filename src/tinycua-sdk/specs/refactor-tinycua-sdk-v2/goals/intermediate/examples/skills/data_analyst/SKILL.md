---
name: data_analyst
description: Analyze datasets, generate charts, and interpret statistical results.
category: data_science
author: tinycua-team
version: 1.2.0
---

## Instructions

When the user provides data or asks for analysis:

1. Load the data using `read_csv` or `read_json`.
2. Inspect the schema and summarize key statistics (mean, median, std).
3. If the user asks for visualization, use `generate_chart` with appropriate chart type.
4. Explain your conclusions in plain language, avoiding jargon where possible.

Always validate that file paths exist before reading.
