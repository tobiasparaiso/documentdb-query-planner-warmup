Now implement a DocumentDB MCP server for this repository.

Problem:
We already have a toolkit that extracts top DocumentDB queries from AWS Performance Insights, filters and deduplicates them, and generates warm-up candidate JSON files.

Goal:
Add an MCP server that allows engineers and Codex to inspect a DocumentDB-compatible cluster using natural language.

The MCP should help enrich the warm-up workflow by exposing safe read-only tools.

Required tools:
1. list_databases
   - Lists available databases.

2. list_collections
   - Lists collections for a selected database.

3. list_indexes
   - Lists indexes for a selected database and collection.

4. sample_documents
   - Returns a limited sample of documents from a selected collection.
   - Must support a limit parameter.
   - Default limit should be small.

5. explain_query
   - Runs explain executionStats for a selected database, collection, and query filter.
   - Should support optional projection and sort if possible.

6. inspect_warmup_candidates
   - Reads the generated warm-up candidate JSON file.
   - Summarizes targeted databases, collections, operation types, and candidate count.

Safety requirements:
- Read-only only.
- Never insert, update, delete, drop, or create data.
- Never execute warm-up queries unless explicitly requested.
- Require connection string through environment variable.
- Do not hardcode credentials.
- Add clear error handling.
- Add README instructions for local usage.

Before implementing, inspect the repository structure and propose the MCP file layout.