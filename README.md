# DocumentDB Query Planner Warm-Up Toolkit

This project helps engineers prepare Amazon DocumentDB clusters for major version migrations by turning real Performance Insights query activity into a reviewed warm-up candidate list.

It was built for the common DocumentDB v5 to v8 migration case where data and indexes are migrated successfully, but the new cluster starts with cold query planner state. Query planner statistics, cached execution plans, and historical index usage patterns are not transferred by migration tooling, so initial production traffic can see temporary latency spikes after cutover.

The toolkit does not execute warm-up queries. It extracts historical query shapes, filters and deduplicates them, and writes JSON artifacts for human review and future execution tooling.

## What This Solves

In a blue/green DocumentDB migration, AWS Database Migration Service can move data and CDC changes, and indexes can be restored separately. The target cluster can still be operationally cold because planner state is rebuilt only after queries begin running.

This project helps reduce that risk by:

- extracting top query digests from AWS Performance Insights
- removing system, admin, write, malformed, and low-value query activity
- deduplicating similar read query shapes
- generating a structured warm-up candidate file
- preserving source metadata for engineer review

## Repository Map

- `query-warmup/`: core extraction, filtering, candidate generation, and regression test scripts
- `sample-data/`: optional demo dataset and workload generator for producing Performance Insights signal in a test cluster
- `sample-data/schemas/`: collection summaries and example documents for the demo dataset
- `scripts/`: helper scripts for connecting to the AWS Labs DocumentDB MCP server
- `docs/`: original project prompts and workflow notes
- `.codex/skills/`: repo-local Codex skill for running the warm-up planning workflow

## Safety Boundaries

The core warm-up toolkit is analysis-only:

- It does not connect to DocumentDB.
- It does not execute generated candidates.
- It does not insert, update, delete, drop, create, or migrate data.
- It does call AWS Performance Insights through the AWS CLI during extraction.

The optional `sample-data/` scripts do connect to a DocumentDB-compatible cluster when you explicitly run them. They are demo scaffolding only and are not required for a real migration workflow.

The optional MCP launcher in `scripts/` starts the AWS Labs DocumentDB MCP server for read-oriented inspection workflows. Do not put credentials in scripts or committed files.

## Quickstart

Prerequisites:

- Bash
- Python 3.10+
- AWS CLI configured with access to Performance Insights
- Amazon DocumentDB Performance Insights resource IDs for the source cluster instances

Extract query digests from Performance Insights:

```bash
query-warmup/extract_queries.sh \
  --region us-east-1 \
  --db-resource-ids db-AAAA,db-BBBB \
  --start-time 2026-06-01T00:00:00Z \
  --end-time 2026-06-01T01:00:00Z \
  --output-dir query-warmup/output
```

Filter and deduplicate read query shapes:

```bash
python3 query-warmup/filter_queries.py \
  --input-dir query-warmup/output/raw \
  --output query-warmup/output/filtered_queries.json
```

Generate warm-up candidates:

```bash
python3 query-warmup/generate_warmup_candidates.py \
  --input query-warmup/output/filtered_queries.json \
  --output query-warmup/output/warmup_candidates.json
```

Run the local regression test:

```bash
python3 query-warmup/test_query_warmup.py
```

## Generated Artifacts

Default output path: `query-warmup/output/`

- `raw/<resource-id>.json`: wrapped AWS Performance Insights response for one DocumentDB instance
- `raw/manifest.json`: extraction parameters and raw file list
- `filtered_queries.json`: cleaned and deduplicated read query shapes
- `warmup_candidates.json`: final human-readable candidate list for review

Performance Insights reports DB load time series. The toolkit uses total load as a ranking signal, not as an exact execution count.

## Optional Demo Data

Use `sample-data/` only when you want to create a small demo workload in a non-production DocumentDB 5.0 cluster.

The demo flow is:

1. Seed synthetic collections with `sample-data/seed_data.py`.
2. Generate repeated read-heavy query activity with `sample-data/workload_generator.py`.
3. Wait for Performance Insights to populate.
4. Run the `query-warmup/` extraction and candidate generation flow.

See `sample-data/README.md` for connection settings, default document counts, and workload tuning flags.

## Human Review Checklist

Before any future execution tool runs generated candidates against a target cluster, engineers should review:

- whether candidate query shapes represent real production traffic
- whether target v8 collections and indexes have been restored
- whether high-load aggregations need lower concurrency or manual handling
- whether candidates target expected databases and collections
- whether any sensitive values appear in captured example statements
- whether warm-up execution should be capped, staged, or skipped for specific namespaces

## Optional AI and MCP Workflows

The repository includes a Codex skill for running the warm-up planning workflow and scripts for launching the AWS Labs DocumentDB MCP server. These are intended to help engineers inspect databases, collections, indexes, sample documents, explain plans, and generated warm-up candidates through review-driven workflows.

See:

- `query-warmup/README.md` for the core workflow
- `sample-data/README.md` for demo data setup
- `scripts/README.md` for MCP launcher usage
- `docs/README.md` for historical prompts and project context

## Disclaimer

Generated warm-up candidates should always be reviewed by engineers before production use.

This project does not modify databases, migrate data, or execute warm-up queries automatically. Engineers remain responsible for validating generated outputs and migration decisions.

## License

MIT License
