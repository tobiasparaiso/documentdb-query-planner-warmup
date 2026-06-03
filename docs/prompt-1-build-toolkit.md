You are working in the repository documentdb-query-planner-warmup.

Problem:
We are preparing an Amazon DocumentDB v5 to v8 migration. During validation, we identified that the new v8 cluster has cold query planner state after migration. DMS migrates data and CDC changes, and indexes are restored separately, but query planner statistics, cached execution plans, and index usage patterns are not migrated.

Goal:
Create a small script-based toolkit that extracts top read queries from AWS Performance Insights, filters and deduplicates them, and generates a warm-up candidate list that can later be executed against the new DocumentDB v8 cluster.

Create the following scripts:

1. extract_queries.sh
Purpose:
- Query AWS Performance Insights for top read queries across DocumentDB instances.
- Save raw output into a structured JSON file.
- Support inputs through environment variables or CLI arguments:
  - AWS region
  - DB resource ID or list of DB resource IDs
  - start time
  - end time
  - output directory
- Use AWS CLI where possible.
- Fail clearly when required inputs are missing.
- Do not hardcode account-specific values.

2. filter_queries.py
Purpose:
- Read the raw extracted query data.
- Remove system/internal/non-useful queries.
- Remove empty, malformed, or non-read queries.
- Deduplicate similar queries where possible.
- Preserve useful metadata such as source instance, frequency/count, database, collection, and query shape if available.
- Output a cleaned JSON file.

3. generate_warmup_candidates.py
Purpose:
- Read the filtered query list.
- Generate a final warm-up candidate JSON file.
- The output should be human-readable and structured for later execution.
- Include fields such as database, collection, operation type, query/filter shape, sort/projection if available, and source metadata.
- Do not execute anything against DocumentDB yet.
- The script should only generate the candidate file.

Requirements:
- Keep the toolkit simple and production-readable.
- Use clear file names and predictable output paths.
- Include basic validation and helpful error messages.
- Add usage examples in comments or README if needed.
- Avoid overengineering.
- Before implementing, inspect the repository structure and propose the exact file layout and execution flow.