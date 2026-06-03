Use the DocumentDB query planner warm-up skill.

Task:
Run the full workflow to extract top read queries from AWS Performance Insights, filter and deduplicate them, and generate the final warm-up candidate list.

Use the current repository scripts and skill instructions.

Expected output:
- Confirm which input parameters are required before execution.
- Run the scripts in the correct order.
- Show the generated files.
- Summarize the final result:
  - raw queries extracted
  - filtered queries
  - deduplicated queries
  - final warm-up candidates
  - most relevant databases/collections
- Show the final warm-up candidate list in a readable format.
- Highlight any query that should be manually reviewed before execution.
- Do not execute warm-up queries against DocumentDB yet.