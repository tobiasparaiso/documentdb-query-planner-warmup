# DocumentDB Query Warm-Up Toolkit

This directory contains the core scripts for preparing warm-up candidates for an Amazon DocumentDB v5 to v8 migration. It extracts top query digests from AWS Performance Insights, filters the raw metrics into workload-like read query shapes, and writes a candidate file for engineer review or a future executor.

The scripts do not connect to DocumentDB and do not execute queries.

Use this workflow when a target DocumentDB cluster has been migrated but may start with cold query planner state. The output is intended to help engineers identify representative read queries that could later be used to initialize planner behavior before production traffic arrives.

## Prerequisites

- Bash
- Python 3.10+
- AWS CLI configured with access to Performance Insights
- Amazon DocumentDB DB resource IDs for the source cluster instances

## Input and Output Contract

Inputs:

- AWS region
- one or more DocumentDB Performance Insights DB resource IDs
- ISO-8601 start and end timestamps for the Performance Insights capture window
- output directory, defaulting to `query-warmup/output`

Outputs:

- `query-warmup/output/raw/<resource-id>.json`
- `query-warmup/output/raw/manifest.json`
- `query-warmup/output/filtered_queries.json`
- `query-warmup/output/warmup_candidates.json`

Performance Insights reports DB load time series. The filtered and generated outputs use total load as a ranking signal, not as an exact execution count.

## 1. Extract Performance Insights Query Digests

```bash
query-warmup/extract_queries.sh \
  --region us-east-1 \
  --db-resource-ids db-AAAA,db-BBBB \
  --start-time 2026-06-01T00:00:00Z \
  --end-time 2026-06-01T01:00:00Z \
  --output-dir query-warmup/output
```

The same inputs can be provided with environment variables:

```bash
export AWS_REGION="us-east-1"
export DOCDB_PI_RESOURCE_IDS="db-AAAA,db-BBBB"
export DOCDB_PI_START_TIME="2026-06-01T00:00:00Z"
export DOCDB_PI_END_TIME="2026-06-01T01:00:00Z"
export OUTPUT_DIR="query-warmup/output"

query-warmup/extract_queries.sh
```

Outputs:

- `query-warmup/output/raw/<resource-id>.json`
- `query-warmup/output/raw/manifest.json`

The extractor uses:

- `aws pi get-resource-metrics`
- `--service-type DOCDB`
- `db.load.avg`
- group by `db.query_tokenized`

## 2. Filter Raw Query Metrics

```bash
python3 query-warmup/filter_queries.py \
  --input-dir query-warmup/output/raw \
  --output query-warmup/output/filtered_queries.json
```

The filter removes:

- empty or malformed statements
- non-read operations
- writes such as `insert`, `update`, and `delete`
- admin/system commands such as `hello`, `isMaster`, `serverStatus`, `buildInfo`, `replSet*`, and `admin.$cmd`

It deduplicates similar query shapes by replacing literal strings, dates, ObjectIds, and numbers with placeholders.

Output:

- `query_count`: number of deduplicated read query shapes
- `queries`: sorted query shapes with operation, database, collection, normalized shape, source instances, load summary, and raw source metadata

## 3. Generate Warm-Up Candidates

```bash
python3 query-warmup/generate_warmup_candidates.py \
  --input query-warmup/output/filtered_queries.json \
  --output query-warmup/output/warmup_candidates.json
```

The candidate file is pretty-printed JSON with:

- `database`
- `collection`
- `operation`
- `query_shape`
- `filter_shape`
- `sort_shape`
- `projection_shape`
- `pipeline_shape`
- `source_metadata`

This file is intentionally structured for a later executor script. It is not executable by itself.

## Review Guidance

Before using generated candidates in any future executor, review:

- targeted databases and collections
- whether each collection and index exists on the target cluster
- high-load aggregation shapes that may need lower concurrency
- candidates with unexpected namespaces or missing metadata
- whether example statements expose sensitive values

Do not execute candidates against production until an engineer has approved the candidate list and the target cluster state.

## Local Smoke Test

```bash
python3 query-warmup/test_query_warmup.py
```
