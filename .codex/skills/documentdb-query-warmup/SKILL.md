---
name: documentdb-query-warmup
description: Use when planning Amazon DocumentDB migration query warm-up, especially v5 to v8 migrations where Performance Insights query data helps reduce cold query planner risk.
---

# DocumentDB Query Warm-Up

## Use Case

Use this skill for Amazon DocumentDB migration warm-up planning when the engineer needs to extract top read query digests from AWS Performance Insights, filter noisy/system queries, deduplicate workload shapes, and produce a warm-up candidate list for review.

Do not use this skill to execute warm-up queries against a real DocumentDB cluster. Never run candidate queries unless the user explicitly asks for execution in a separate request.

## Required Inputs

Before running anything, confirm these values are available from the user request, environment, or explicit defaults:

- AWS region: `--region` or `AWS_REGION`
- DB resource IDs: `--db-resource-ids` or `DOCDB_PI_RESOURCE_IDS`
- Start time: `--start-time` or `DOCDB_PI_START_TIME`
- End time: `--end-time` or `DOCDB_PI_END_TIME`
- Output directory: `--output-dir` or `OUTPUT_DIR`, default `query-warmup/output`

Also verify these files exist:

- `query-warmup/extract_queries.sh`
- `query-warmup/filter_queries.py`
- `query-warmup/generate_warmup_candidates.py`

If required inputs are missing, stop and ask for them. If `aws` is missing, report that AWS CLI setup is required.

## Workflow

Run the workflow in this order from the repository root:

```bash
query-warmup/extract_queries.sh \
  --region "$AWS_REGION" \
  --db-resource-ids "$DOCDB_PI_RESOURCE_IDS" \
  --start-time "$DOCDB_PI_START_TIME" \
  --end-time "$DOCDB_PI_END_TIME" \
  --output-dir "${OUTPUT_DIR:-query-warmup/output}"
```

Then filter:

```bash
python3 query-warmup/filter_queries.py \
  --input-dir "${OUTPUT_DIR:-query-warmup/output}/raw" \
  --output "${OUTPUT_DIR:-query-warmup/output}/filtered_queries.json"
```

Then generate candidates:

```bash
python3 query-warmup/generate_warmup_candidates.py \
  --input "${OUTPUT_DIR:-query-warmup/output}/filtered_queries.json" \
  --output "${OUTPUT_DIR:-query-warmup/output}/warmup_candidates.json"
```

After each step, inspect the expected artifact. Stop on missing files, malformed JSON, or empty results that look unexpected for the capture window.

## Artifacts

- `output/raw/<resource-id>.json`: raw Performance Insights response for one DocumentDB instance.
- `output/raw/manifest.json`: extraction parameters and raw file list.
- `output/filtered_queries.json`: cleaned read query shapes after system-query removal and deduplication.
- `output/warmup_candidates.json`: final human-readable candidate list for future execution tooling.

The default `output/` path is `query-warmup/output/` unless the user supplied a different output directory.

## Summary Metrics

Compute summary metrics from JSON artifacts, not from shell output. Use this pattern, replacing `query-warmup/output` if needed:

```bash
python3 - <<'PY'
import json
from collections import Counter
from pathlib import Path

output_dir = Path("query-warmup/output")
raw_dir = output_dir / "raw"
filtered_path = output_dir / "filtered_queries.json"
candidates_path = output_dir / "warmup_candidates.json"

raw_count = 0
for path in raw_dir.glob("*.json"):
    if path.name == "manifest.json":
        continue
    payload = json.loads(path.read_text())
    pi_payload = payload.get("performance_insights", payload)
    raw_count += len(pi_payload.get("MetricList", []))

filtered = json.loads(filtered_path.read_text())
queries = filtered.get("queries", [])
accepted_before_dedupe = sum(len(q.get("source_metadata", [])) for q in queries)
removed_by_filtering = raw_count - accepted_before_dedupe
deduplicated_query_shapes = len(queries)
duplicates_collapsed = accepted_before_dedupe - deduplicated_query_shapes

candidates = json.loads(candidates_path.read_text())
candidate_list = candidates.get("candidates", [])
namespaces = Counter(
    f"{item.get('database')}.{item.get('collection')}"
    for item in candidate_list
    if item.get("database") and item.get("collection")
)

print(json.dumps({
    "raw_queries_extracted": raw_count,
    "queries_removed_by_filtering": removed_by_filtering,
    "duplicates_collapsed": duplicates_collapsed,
    "deduplicated_queries": deduplicated_query_shapes,
    "warmup_candidates": len(candidate_list),
    "top_databases_collections": namespaces.most_common(10),
}, indent=2))
PY
```

## Final Response

Write the final response for a senior DevOps/Cloud engineer. Keep it concise and include:

- Inputs used: region, resource IDs, time window, output directory.
- Artifact paths generated.
- Counts: raw queries extracted, queries removed by filtering, duplicates collapsed, deduplicated queries, final warm-up candidates.
- Top databases/collections involved.
- Human review items: verify candidate shapes are representative, confirm collection/index restoration status on v8, review any high-load aggregation shapes, and decide whether to cap future executor concurrency.
- Safety note: no warm-up queries were executed against DocumentDB.

