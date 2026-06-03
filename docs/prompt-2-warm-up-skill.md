Now create a Codex Skill for this repository.

Problem:
The repository now has scripts to extract DocumentDB query data from AWS Performance Insights, filter and deduplicate queries, and generate a warm-up candidate list.

Goal:
Create a Codex Skill that guides Codex to run this workflow end-to-end in the correct order and produce a readable final summary for the engineer.

The skill should:
- Explain when to use it: DocumentDB migration warm-up planning, especially v5 to v8 migration with cold query planner risk.
- Run or guide execution of:
  1. extract_queries.sh
  2. filter_queries.py
  3. generate_warmup_candidates.py
- Validate required inputs before execution.
- Explain generated artifacts.
- Summarize:
  - number of raw queries extracted
  - number of queries removed by filtering
  - number of deduplicated queries
  - number of final warm-up candidates
  - top databases/collections involved
- Highlight risks or items requiring human review.
- Never execute warm-up queries against a real database unless explicitly asked.
- Keep the final output readable for a senior DevOps/Cloud engineer.

Before implementing, inspect the current repository and propose the skill file location and structure based on Codex plugin/skill conventions used in this repo.