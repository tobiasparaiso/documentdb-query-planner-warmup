# Amazon DocumentDB Sample Data and Workload

This directory provides optional demo scaffolding for Amazon DocumentDB 5.0. It is useful when you want to create repeatable Performance Insights query signal in a non-production cluster before testing the warm-up toolkit.

You do not need this directory for a real migration. For production migration planning, run the `query-warmup/` scripts against Performance Insights data from the real source cluster.

- `seed_data.py` seeds fake generic data into multiple databases and collections.
- `workload_generator.py` generates a balanced mixed workload so AWS Performance Insights records repeated top queries.
- `schemas/` documents the sample collections and example documents.

The sample scripts connect to a DocumentDB-compatible cluster only when you run them explicitly. Use a test cluster and avoid production credentials.

## Dataset layout

Databases and collections:

- `sales_demo.orders`
- `sales_demo.subscriptions`
- `support_demo.tickets`
- `support_demo.events`

Shared query-friendly fields across collections:

- `client_id`
- `status`
- `category`
- `region`
- `created_at`

## Prerequisites

- Python 3.10+
- Access to an existing Amazon DocumentDB 5.0 cluster
- Network access and security group rules that allow the connection
- A local CA bundle file if your cluster requires TLS verification
- Python dependency:

```bash
python3 -m pip install pymongo
```

## Connection configuration

The scripts use environment variables instead of hard-coded connection details.

Required:

```bash
export DOCDB_URI="mongodb://USERNAME:PASSWORD@YOUR-DOCDB-ENDPOINT:27017/?replicaSet=rs0&readPreference=secondaryPreferred"
```

Optional TLS CA bundle:

```bash
export DOCDB_TLS_CA_FILE="/path/to/global-bundle.pem"
```

Notes:

- `retryWrites=false` is forced by the scripts because Amazon DocumentDB does not support retryable writes.
- If your connection string already includes TLS parameters, the script-level CA file remains optional.

## Seed the dataset

Default seed volumes:

- `orders`: 20,000
- `subscriptions`: 5,000
- `tickets`: 10,000
- `events`: 25,000

Example:

```bash
python3 sample-data/seed_data.py --recreate --seed 42
```

Useful flags:

```bash
python3 sample-data/seed_data.py --help
```

- `--recreate`: drops the target collections before re-seeding
- `--seed`: makes fake data generation deterministic
- `--client-count`: adjusts the reusable `client_id` pool
- `--batch-size`: controls insert batch size
- `--orders`, `--subscriptions`, `--tickets`, `--events`: override document counts

The script also creates demo indexes such as:

- `{ client_id: 1 }`
- `{ region: 1 }`
- `{ status: 1, created_at: -1 }`
- one collection-specific compound index

## Run the workload generator

Default behavior:

- runs for 10 minutes
- sleeps 0.2 seconds between operations
- mixes point lookups, aggregations, counts, and light updates

Example 10-minute Performance Insights run:

```bash
python3 sample-data/workload_generator.py --duration-seconds 600 --sleep-seconds 0.1
```

Read-only variant:

```bash
python3 sample-data/workload_generator.py --duration-seconds 600 --no-include-updates
```

Smoke test:

```bash
python3 sample-data/workload_generator.py --duration-seconds 60 --sleep-seconds 0.05
```

Useful flags:

```bash
python3 sample-data/workload_generator.py --help
```

- `--duration-seconds`: total run time
- `--sleep-seconds`: pause between operations to tune workload intensity
- `--recent-days`: changes the recency filter in queries
- `--summary-every`: prints lightweight progress output
- `--seed`: makes workload selection repeatable
- `--include-updates` / `--no-include-updates`: toggles mixed write activity

## Demo flow

1. Seed the collections.
2. Run the workload generator.
3. Wait for AWS Performance Insights to populate and stabilize.
4. Perform the extraction step from `query-warmup/`.

## How long to run before extracting Performance Insights

Recommended:

- Run for at least 10 minutes for the actual capture.
- Prefer 15 minutes if the cluster is lightly provisioned or the workload rate is low.

Guidance:

- Under 5 minutes is fine for a smoke test but often too short for a clean Performance Insights demo.
- 10 minutes is the default target because it usually yields repeated top-query patterns.
- 15 minutes gives more stable rankings and better signal if query throughput is modest.
