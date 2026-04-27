#!/usr/bin/env python3
"""Generate a balanced query workload against the demo DocumentDB dataset."""

from __future__ import annotations

import argparse
import os
import random
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection

REGIONS = ["us-east", "us-west", "eu-west", "eu-central", "ap-southeast"]
ORDER_STATUSES = ["pending", "processing", "shipped", "delivered", "cancelled"]
SUBSCRIPTION_STATUSES = ["trial", "active", "past_due", "paused", "cancelled"]
TICKET_STATUSES = ["new", "open", "pending", "resolved", "closed"]
EVENT_STATUSES = ["queued", "processing", "completed", "skipped", "failed"]

WORKLOAD_WEIGHTS = {
    "find_by_client": 45,
    "aggregate_by_status": 20,
    "aggregate_by_category": 18,
    "count_by_region": 12,
    "update_status": 5,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=99, help="Random seed for repeatable workload selection.")
    parser.add_argument("--duration-seconds", type=int, default=600, help="Total run duration in seconds.")
    parser.add_argument("--sleep-seconds", type=float, default=0.2, help="Pause between operations.")
    parser.add_argument("--client-count", type=int, default=300, help="Client pool size used by the seed script.")
    parser.add_argument("--recent-days", type=int, default=30, help="Recent time window for filter variation.")
    parser.add_argument("--summary-every", type=int, default=50, help="Print a progress summary every N operations.")
    parser.add_argument(
        "--include-updates",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include light update activity.",
    )
    return parser.parse_args()


def build_client(uri: str, tls_ca_file: str | None) -> MongoClient:
    kwargs: dict[str, Any] = {"retryWrites": False}
    if tls_ca_file:
        kwargs["tls"] = True
        kwargs["tlsCAFile"] = tls_ca_file
    return MongoClient(uri, **kwargs)


def recent_cutoff(rng: random.Random, max_days: int) -> datetime:
    days = rng.randint(1, max_days)
    return datetime.now(UTC) - timedelta(days=days)


def pick_collection(client: MongoClient, rng: random.Random) -> tuple[str, Collection]:
    candidates = [
        ("sales_demo.orders", client["sales_demo"]["orders"]),
        ("sales_demo.subscriptions", client["sales_demo"]["subscriptions"]),
        ("support_demo.tickets", client["support_demo"]["tickets"]),
        ("support_demo.events", client["support_demo"]["events"]),
    ]
    return rng.choice(candidates)


def run_find_by_client(collection: Collection, client_id: str, cutoff: datetime) -> int:
    return len(
        list(
            collection.find(
                {"client_id": client_id, "created_at": {"$gte": cutoff}},
                {"_id": 0, "client_id": 1, "status": 1, "category": 1, "region": 1, "created_at": 1},
            ).limit(25)
        )
    )


def run_aggregate_group(collection: Collection, field_name: str, cutoff: datetime) -> list[dict[str, Any]]:
    pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$group": {"_id": f"${field_name}", "total": {"$sum": 1}}},
        {"$sort": {"total": -1}},
        {"$limit": 10},
    ]
    return list(collection.aggregate(pipeline))


def run_count_by_region(collection: Collection, region: str, cutoff: datetime) -> int:
    return collection.count_documents({"region": region, "created_at": {"$gte": cutoff}})


def eligible_statuses(collection_name: str) -> list[str]:
    if collection_name.endswith("orders"):
        return ORDER_STATUSES
    if collection_name.endswith("subscriptions"):
        return SUBSCRIPTION_STATUSES
    if collection_name.endswith("tickets"):
        return TICKET_STATUSES
    return EVENT_STATUSES


def run_update_status(collection: Collection, collection_name: str, client_id: str, cutoff: datetime, rng: random.Random) -> int:
    result = collection.update_one(
        {"client_id": client_id, "created_at": {"$gte": cutoff}},
        {"$set": {"status": rng.choice(eligible_statuses(collection_name)), "updated_at": datetime.now(UTC)}},
    )
    return result.modified_count


def main() -> int:
    args = parse_args()
    docdb_uri = os.environ.get("DOCDB_URI")
    if not docdb_uri:
        raise SystemExit("DOCDB_URI is required.")

    tls_ca_file = os.environ.get("DOCDB_TLS_CA_FILE")
    rng = random.Random(args.seed)
    clients = [f"client_{index:04d}" for index in range(1, args.client_count + 1)]
    operation_weights = dict(WORKLOAD_WEIGHTS)
    if not args.include_updates:
        operation_weights.pop("update_status")

    client = build_client(docdb_uri, tls_ca_file)
    counters: Counter[str] = Counter()
    start = time.time()
    deadline = start + args.duration_seconds

    try:
        print(
            "Starting workload "
            f"duration_seconds={args.duration_seconds} sleep_seconds={args.sleep_seconds} "
            f"include_updates={args.include_updates} seed={args.seed}"
        )
        while time.time() < deadline:
            collection_name, collection = pick_collection(client, rng)
            op_name = rng.choices(list(operation_weights.keys()), weights=list(operation_weights.values()), k=1)[0]
            client_id = rng.choice(clients)
            cutoff = recent_cutoff(rng, args.recent_days)

            if op_name == "find_by_client":
                run_find_by_client(collection, client_id, cutoff)
            elif op_name == "aggregate_by_status":
                run_aggregate_group(collection, "status", cutoff)
            elif op_name == "aggregate_by_category":
                run_aggregate_group(collection, "category", cutoff)
            elif op_name == "count_by_region":
                run_count_by_region(collection, rng.choice(REGIONS), cutoff)
            else:
                run_update_status(collection, collection_name, client_id, cutoff, rng)

            counters[op_name] += 1
            counters[f"collection:{collection_name}"] += 1

            total_ops = sum(count for key, count in counters.items() if not key.startswith("collection:"))
            if total_ops % args.summary_every == 0:
                elapsed = time.time() - start
                print(
                    f"elapsed={elapsed:.1f}s ops={total_ops} "
                    f"find={counters['find_by_client']} agg_status={counters['aggregate_by_status']} "
                    f"agg_category={counters['aggregate_by_category']} count_region={counters['count_by_region']} "
                    f"updates={counters['update_status']}"
                )

            if args.sleep_seconds > 0:
                time.sleep(args.sleep_seconds)

        total_ops = sum(count for key, count in counters.items() if not key.startswith("collection:"))
        print(f"Completed workload: total_ops={total_ops}")
        for key in sorted(counters):
            print(f"{key}={counters[key]}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
