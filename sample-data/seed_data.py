#!/usr/bin/env python3
"""Seed a demo Amazon DocumentDB cluster with fake multi-database data."""

from __future__ import annotations

import argparse
import os
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection

DEFAULT_COUNTS = {
    "orders": 20_000,
    "subscriptions": 5_000,
    "tickets": 10_000,
    "events": 25_000,
}

REGIONS = ["us-east", "us-west", "eu-west", "eu-central", "ap-southeast"]
ORDER_STATUSES = ["pending", "processing", "shipped", "delivered", "cancelled"]
SUBSCRIPTION_STATUSES = ["trial", "active", "past_due", "paused", "cancelled"]
TICKET_STATUSES = ["new", "open", "pending", "resolved", "closed"]
EVENT_STATUSES = ["queued", "processing", "completed", "skipped", "failed"]
ORDER_CATEGORIES = ["software", "hardware", "services", "analytics", "storage", "security"]
SUBSCRIPTION_CATEGORIES = ["starter", "growth", "enterprise", "support", "backup"]
TICKET_CATEGORIES = ["billing", "access", "incident", "configuration", "integration", "reporting"]
EVENT_CATEGORIES = ["login", "sync", "webhook", "export", "alert", "billing", "audit"]
CHANNELS = ["web", "sales_rep", "partner", "marketplace"]
PRIORITIES = ["low", "medium", "high", "urgent"]
PLAN_TIERS = ["basic", "standard", "premium", "enterprise"]
BILLING_CYCLES = ["monthly", "quarterly", "annual"]
SEVERITIES = ["low", "medium", "high", "critical"]
ASSIGNED_TEAMS = ["ops", "support", "billing", "platform", "security"]
EVENT_TYPES = ["create", "update", "delete", "retry", "notify"]
SOURCES = ["api", "scheduler", "mobile_app", "backoffice", "partner_sync"]


@dataclass(frozen=True)
class CollectionPlan:
    database: str
    collection: str
    count_key: str
    builder: Callable[[random.Random, int, list[str], datetime], dict[str, Any]]
    indexes: list[tuple[str, list[tuple[str, int]]]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42, help="Random seed for repeatable data generation.")
    parser.add_argument("--batch-size", type=int, default=1_000, help="Insert batch size.")
    parser.add_argument("--client-count", type=int, default=300, help="Reusable client_id pool size.")
    parser.add_argument("--orders", type=int, default=DEFAULT_COUNTS["orders"], help="Documents in sales_demo.orders.")
    parser.add_argument(
        "--subscriptions",
        type=int,
        default=DEFAULT_COUNTS["subscriptions"],
        help="Documents in sales_demo.subscriptions.",
    )
    parser.add_argument("--tickets", type=int, default=DEFAULT_COUNTS["tickets"], help="Documents in support_demo.tickets.")
    parser.add_argument("--events", type=int, default=DEFAULT_COUNTS["events"], help="Documents in support_demo.events.")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate the target collections before seeding.",
    )
    return parser.parse_args()


def build_client(uri: str, tls_ca_file: str | None) -> MongoClient:
    kwargs: dict[str, Any] = {"retryWrites": False}
    if tls_ca_file:
        kwargs["tls"] = True
        kwargs["tlsCAFile"] = tls_ca_file
    return MongoClient(uri, **kwargs)


def biased_timestamp(rng: random.Random, now: datetime) -> datetime:
    """Bias timestamps toward more recent days while spanning roughly 90 days."""
    days_back = int(rng.random() ** 2 * 90)
    seconds_back = rng.randint(0, 24 * 60 * 60 - 1)
    return now - timedelta(days=days_back, seconds=seconds_back)


def build_orders(rng: random.Random, index: int, clients: list[str], now: datetime) -> dict[str, Any]:
    created_at = biased_timestamp(rng, now)
    return {
        "order_id": f"ORD-{index:08d}",
        "client_id": rng.choice(clients),
        "status": rng.choices(ORDER_STATUSES, weights=[12, 15, 18, 45, 10], k=1)[0],
        "category": rng.choice(ORDER_CATEGORIES),
        "region": rng.choice(REGIONS),
        "created_at": created_at,
        "amount": round(rng.uniform(49.0, 7500.0), 2),
        "channel": rng.choice(CHANNELS),
        "priority": rng.choices(PRIORITIES, weights=[30, 45, 20, 5], k=1)[0],
    }


def build_subscriptions(rng: random.Random, index: int, clients: list[str], now: datetime) -> dict[str, Any]:
    created_at = biased_timestamp(rng, now)
    cycle = rng.choices(BILLING_CYCLES, weights=[55, 20, 25], k=1)[0]
    renewal_offset = {"monthly": 30, "quarterly": 90, "annual": 365}[cycle]
    return {
        "subscription_id": f"SUB-{index:08d}",
        "client_id": rng.choice(clients),
        "status": rng.choices(SUBSCRIPTION_STATUSES, weights=[8, 62, 12, 8, 10], k=1)[0],
        "category": rng.choice(SUBSCRIPTION_CATEGORIES),
        "region": rng.choice(REGIONS),
        "created_at": created_at,
        "plan_tier": rng.choices(PLAN_TIERS, weights=[30, 35, 25, 10], k=1)[0],
        "billing_cycle": cycle,
        "renewal_date": created_at + timedelta(days=renewal_offset),
    }


def build_tickets(rng: random.Random, index: int, clients: list[str], now: datetime) -> dict[str, Any]:
    created_at = biased_timestamp(rng, now)
    status = rng.choices(TICKET_STATUSES, weights=[10, 32, 18, 25, 15], k=1)[0]
    resolved_at = None
    if status in {"resolved", "closed"}:
        resolved_at = created_at + timedelta(hours=rng.randint(2, 120))
    return {
        "ticket_id": f"TCK-{index:08d}",
        "client_id": rng.choice(clients),
        "status": status,
        "category": rng.choice(TICKET_CATEGORIES),
        "region": rng.choice(REGIONS),
        "created_at": created_at,
        "severity": rng.choices(SEVERITIES, weights=[25, 40, 25, 10], k=1)[0],
        "assigned_team": rng.choice(ASSIGNED_TEAMS),
        "resolved_at": resolved_at,
    }


def build_events(rng: random.Random, index: int, clients: list[str], now: datetime) -> dict[str, Any]:
    created_at = biased_timestamp(rng, now)
    processed_at = created_at + timedelta(minutes=rng.randint(1, 240))
    return {
        "event_id": f"EVT-{index:08d}",
        "client_id": rng.choice(clients),
        "status": rng.choices(EVENT_STATUSES, weights=[12, 18, 48, 8, 14], k=1)[0],
        "category": rng.choice(EVENT_CATEGORIES),
        "region": rng.choice(REGIONS),
        "created_at": created_at,
        "event_type": rng.choice(EVENT_TYPES),
        "source": rng.choice(SOURCES),
        "processed_at": processed_at,
    }


PLANS = [
    CollectionPlan(
        database="sales_demo",
        collection="orders",
        count_key="orders",
        builder=build_orders,
        indexes=[
            ("client_id_1", [("client_id", ASCENDING)]),
            ("region_1", [("region", ASCENDING)]),
            ("status_1_created_at_-1", [("status", ASCENDING), ("created_at", DESCENDING)]),
            ("category_1_created_at_-1", [("category", ASCENDING), ("created_at", DESCENDING)]),
        ],
    ),
    CollectionPlan(
        database="sales_demo",
        collection="subscriptions",
        count_key="subscriptions",
        builder=build_subscriptions,
        indexes=[
            ("client_id_1", [("client_id", ASCENDING)]),
            ("region_1", [("region", ASCENDING)]),
            ("status_1_created_at_-1", [("status", ASCENDING), ("created_at", DESCENDING)]),
            ("plan_tier_1_created_at_-1", [("plan_tier", ASCENDING), ("created_at", DESCENDING)]),
        ],
    ),
    CollectionPlan(
        database="support_demo",
        collection="tickets",
        count_key="tickets",
        builder=build_tickets,
        indexes=[
            ("client_id_1", [("client_id", ASCENDING)]),
            ("region_1", [("region", ASCENDING)]),
            ("status_1_created_at_-1", [("status", ASCENDING), ("created_at", DESCENDING)]),
            ("category_1_created_at_-1", [("category", ASCENDING), ("created_at", DESCENDING)]),
        ],
    ),
    CollectionPlan(
        database="support_demo",
        collection="events",
        count_key="events",
        builder=build_events,
        indexes=[
            ("client_id_1", [("client_id", ASCENDING)]),
            ("region_1", [("region", ASCENDING)]),
            ("status_1_created_at_-1", [("status", ASCENDING), ("created_at", DESCENDING)]),
            ("source_1_created_at_-1", [("source", ASCENDING), ("created_at", DESCENDING)]),
        ],
    ),
]


def collection_target_count(args: argparse.Namespace, plan: CollectionPlan) -> int:
    return int(getattr(args, plan.count_key))


def recreate_collection(collection: Collection, enabled: bool) -> None:
    if enabled:
        collection.drop()


def ensure_indexes(collection: Collection, plan: CollectionPlan) -> None:
    for name, keys in plan.indexes:
        collection.create_index(keys, name=name)


def insert_documents(
    collection: Collection,
    builder: Callable[[random.Random, int, list[str], datetime], dict[str, Any]],
    total: int,
    batch_size: int,
    rng: random.Random,
    clients: list[str],
    now: datetime,
) -> None:
    batch: list[dict[str, Any]] = []
    for index in range(total):
        batch.append(builder(rng, index + 1, clients, now))
        if len(batch) >= batch_size:
            collection.insert_many(batch, ordered=False)
            batch.clear()
    if batch:
        collection.insert_many(batch, ordered=False)


def main() -> int:
    args = parse_args()
    docdb_uri = os.environ.get("DOCDB_URI")
    if not docdb_uri:
        raise SystemExit("DOCDB_URI is required.")

    tls_ca_file = os.environ.get("DOCDB_TLS_CA_FILE")
    rng = random.Random(args.seed)
    now = datetime.now(UTC).replace(microsecond=0)
    clients = [f"client_{index:04d}" for index in range(1, args.client_count + 1)]

    client = build_client(docdb_uri, tls_ca_file)
    try:
        print(f"Seeding DocumentDB with seed={args.seed}, client_count={args.client_count}, batch_size={args.batch_size}")
        for plan in PLANS:
            database = client[plan.database]
            collection = database[plan.collection]
            recreate_collection(collection, args.recreate)
            total = collection_target_count(args, plan)
            insert_documents(
                collection=collection,
                builder=plan.builder,
                total=total,
                batch_size=args.batch_size,
                rng=rng,
                clients=clients,
                now=now,
            )
            ensure_indexes(collection, plan)
            print(f"{plan.database}.{plan.collection}: inserted={total} count={collection.count_documents({})}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
