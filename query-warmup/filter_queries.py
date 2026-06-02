#!/usr/bin/env python3
"""Filter raw DocumentDB Performance Insights query metrics into read query shapes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

READ_OPERATIONS = {"find", "aggregate", "count", "distinct"}
WRITE_OR_ADMIN_OPERATIONS = {
    "insert",
    "update",
    "delete",
    "drop",
    "create",
    "createindexes",
    "listindexes",
    "serverstatus",
    "hello",
    "ismaster",
    "buildinfo",
    "connpoolstats",
}
STATEMENT_DIMENSION_KEYS = (
    "db.query_tokenized",
    "db.query_tokenized.statement",
    "db.query.tokenized.statement",
    "db.query.statement",
    "db.statement",
    "statement",
    "query",
)
DATABASE_DIMENSION_KEYS = ("db.name", "db", "database", "db.query.database")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, help="Directory containing raw PI JSON files.")
    parser.add_argument("--output", required=True, help="Path for the cleaned JSON output.")
    return parser.parse_args()


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON in {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"Expected a JSON object in {path}.")
    return payload


def raw_payload(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("performance_insights")
    if isinstance(nested, dict):
        return nested
    return payload


def source_metadata(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    source = payload.get("source")
    if isinstance(source, dict):
        resource_id = str(source.get("resource_id") or path.stem)
        return {
            "resource_id": resource_id,
            "region": source.get("region"),
            "start_time": source.get("start_time"),
            "end_time": source.get("end_time"),
            "raw_file": str(path),
        }
    return {
        "resource_id": path.stem,
        "region": None,
        "start_time": None,
        "end_time": None,
        "raw_file": str(path),
    }


def statement_from_dimensions(dimensions: dict[str, Any]) -> str:
    for key in STATEMENT_DIMENSION_KEYS:
        value = dimensions.get(key)
        if value is not None:
            return str(value).strip()
    return ""


def database_from_dimensions(dimensions: dict[str, Any]) -> str | None:
    for key in DATABASE_DIMENSION_KEYS:
        value = dimensions.get(key)
        if value:
            return str(value)
    return None


def canonical_operation(operation: str) -> str:
    return re.sub(r"[^a-z]", "", operation.lower())


def parse_statement(statement: str, dimension_database: str | None) -> dict[str, str | None]:
    stripped = " ".join(statement.strip().split())
    if not stripped:
        return {"operation": None, "database": dimension_database, "collection": None}

    command = parse_json_command(stripped)
    if command:
        return command

    match = re.match(r"^(?P<operation>[A-Za-z_][A-Za-z0-9_]*)\s+(?P<namespace>[A-Za-z0-9_$.-]+)?", stripped)
    if not match:
        return {"operation": None, "database": dimension_database, "collection": None}

    operation = match.group("operation").lower()
    namespace = match.group("namespace") or ""
    database = dimension_database
    collection: str | None = None

    if "." in namespace:
        first, rest = namespace.split(".", 1)
        database = database or first
        collection = rest
    elif namespace and namespace not in {"{}", "[]"}:
        collection = namespace

    return {"operation": operation, "database": database, "collection": collection}


def parse_json_command(statement: str) -> dict[str, str | None] | None:
    try:
        command = json.loads(statement)
    except json.JSONDecodeError:
        return None
    if not isinstance(command, dict):
        return None

    for operation in ("find", "aggregate", "count", "distinct", "insert", "update", "delete"):
        collection = command.get(operation)
        if collection is not None:
            return {
                "operation": operation,
                "database": str(command.get("$db")) if command.get("$db") else None,
                "collection": str(collection) if collection else None,
            }

    for operation in ("hello", "isMaster", "serverStatus", "buildInfo", "connPoolStats", "listIndexes", "createIndexes"):
        for key in command:
            if key.lower() == operation.lower():
                return {
                    "operation": operation,
                    "database": str(command.get("$db")) if command.get("$db") else None,
                    "collection": None,
                }
    return None


def is_system_or_non_read(statement: str, operation: str | None, database: str | None, collection: str | None) -> bool:
    lowered = statement.lower()
    canonical = canonical_operation(operation or "")
    if not statement.strip() or not operation:
        return True
    if canonical in WRITE_OR_ADMIN_OPERATIONS:
        return True
    if canonical.startswith("replset"):
        return True
    if operation not in READ_OPERATIONS:
        return True
    if (database or "").lower() in {"admin", "config", "local"}:
        return True
    if "admin.$cmd" in lowered or ".$cmd" in lowered:
        return True
    if "system." in lowered:
        return True
    return collection is None


def normalize_statement(statement: str) -> str:
    json_shape = normalize_json_statement(statement)
    if json_shape:
        return json_shape

    normalized = statement.strip()
    normalized = re.sub(r"ObjectId\([^)]+\)", 'ObjectId("<object_id>")', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"ISODate\([^)]+\)", 'ISODate("<date>")', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'(?<!\\)"(?:\\.|[^"\\])*"', '"<string>"', normalized)
    normalized = re.sub(r"(?<!\\)'(?:\\.|[^'\\])*'", "'<string>'", normalized)
    normalized = re.sub(r"\b-?\d+(?:\.\d+)?\b", "<number>", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def normalize_json_statement(statement: str) -> str | None:
    try:
        command = json.loads(statement)
    except json.JSONDecodeError:
        return None
    if not isinstance(command, dict):
        return None
    return json.dumps(normalize_json_value(command), sort_keys=True, separators=(",", ":"))


def normalize_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): normalize_json_value(child) for key, child in value.items()}
    if isinstance(value, list):
        return [normalize_json_value(child) for child in value]
    if isinstance(value, str):
        return "?"
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int | float):
        return 0
    return "?"


def datapoint_summary(metric: dict[str, Any]) -> dict[str, Any]:
    datapoints = metric.get("DataPoints")
    if not isinstance(datapoints, list):
        datapoints = []

    total_load = 0.0
    timestamps: list[str] = []
    for point in datapoints:
        if not isinstance(point, dict):
            continue
        value = point.get("Value")
        if isinstance(value, int | float):
            total_load += float(value)
        timestamp = point.get("Timestamp")
        if timestamp is not None:
            timestamps.append(str(timestamp))

    return {
        "total_load": round(total_load, 6),
        "sample_count": len(datapoints),
        "first_seen": min(timestamps) if timestamps else None,
        "last_seen": max(timestamps) if timestamps else None,
    }


def query_entries(input_dir: Path) -> list[dict[str, Any]]:
    if not input_dir.exists():
        fail(f"Input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        fail(f"Input path is not a directory: {input_dir}")

    entries: list[dict[str, Any]] = []
    for path in sorted(input_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        envelope = load_json(path)
        payload = raw_payload(envelope)
        source = source_metadata(path, envelope)
        metric_list = payload.get("MetricList")
        if not isinstance(metric_list, list):
            continue

        for metric in metric_list:
            if not isinstance(metric, dict):
                continue
            key = metric.get("Key") if isinstance(metric.get("Key"), dict) else {}
            dimensions = key.get("Dimensions") if isinstance(key.get("Dimensions"), dict) else {}
            statement = statement_from_dimensions(dimensions)
            parsed = parse_statement(statement, database_from_dimensions(dimensions))
            operation = parsed["operation"]
            database = parsed["database"]
            collection = parsed["collection"]
            if is_system_or_non_read(statement, operation, database, collection):
                continue

            summary = datapoint_summary(metric)
            entries.append(
                {
                    "operation": operation,
                    "database": database,
                    "collection": collection,
                    "query_statement": statement,
                    "query_shape": normalize_statement(statement),
                    "dimensions": dimensions,
                    "total_load": summary["total_load"],
                    "sample_count": summary["sample_count"],
                    "first_seen": summary["first_seen"],
                    "last_seen": summary["last_seen"],
                    "source": source,
                }
            )
    return entries


def merge_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str | None, str | None, str], dict[str, Any]] = {}
    sources_by_key: dict[tuple[str, str | None, str | None, str], set[str]] = defaultdict(set)

    for entry in entries:
        key = (entry["operation"], entry["database"], entry["collection"], entry["query_shape"])
        sources_by_key[key].add(entry["source"]["resource_id"])
        if key not in grouped:
            grouped[key] = {
                "operation": entry["operation"],
                "database": entry["database"],
                "collection": entry["collection"],
                "query_shape": entry["query_shape"],
                "example_query_statement": entry["query_statement"],
                "total_load": 0.0,
                "sample_count": 0,
                "first_seen": entry["first_seen"],
                "last_seen": entry["last_seen"],
                "raw_dimensions": [entry["dimensions"]],
                "source_metadata": [entry["source"]],
            }
        else:
            grouped[key]["raw_dimensions"].append(entry["dimensions"])
            grouped[key]["source_metadata"].append(entry["source"])

        grouped[key]["total_load"] = round(grouped[key]["total_load"] + entry["total_load"], 6)
        grouped[key]["sample_count"] += entry["sample_count"]
        if entry["first_seen"] and (not grouped[key]["first_seen"] or entry["first_seen"] < grouped[key]["first_seen"]):
            grouped[key]["first_seen"] = entry["first_seen"]
        if entry["last_seen"] and (not grouped[key]["last_seen"] or entry["last_seen"] > grouped[key]["last_seen"]):
            grouped[key]["last_seen"] = entry["last_seen"]

    merged = []
    for key, entry in grouped.items():
        entry["source_instances"] = sorted(sources_by_key[key])
        merged.append(entry)
    return sorted(merged, key=lambda item: (-item["total_load"], item["database"] or "", item["collection"] or ""))


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output = Path(args.output)
    entries = merge_entries(query_entries(input_dir))
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": {"input_dir": str(input_dir)},
        "query_count": len(entries),
        "queries": entries,
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} filtered query shapes to {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
