# DocumentDB Query Warm-Up Toolkit

This toolkit prepares warm-up candidates for an Amazon DocumentDB v5 to v8 migration. It extracts top query digests from AWS Performance Insights, filters the raw metrics into workload-like read query shapes, and writes a candidate file for a future executor.

The scripts do not connect to DocumentDB and do not execute queries.

## Prerequisites

- Bash
- Python 3.10+
- AWS CLI configured with access to Performance Insights
- Amazon DocumentDB DB resource IDs for the source cluster instances

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

Performance Insights reports DB load time series. The filtered output treats total load as the ranking signal rather than an exact execution count.

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

## Local Smoke Test

```bash
python3 query-warmup/test_query_warmup.py
```

