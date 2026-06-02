#!/usr/bin/env python3
"""Generate warm-up candidate JSON from filtered DocumentDB query shapes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Filtered query JSON from filter_queries.py.")
    parser.add_argument("--output", required=True, help="Path for the generated warm-up candidate JSON.")
    return parser.parse_args()


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load_filtered(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"Input file does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON in {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"Expected a JSON object in {path}.")
    if not isinstance(payload.get("queries"), list):
        fail(f"Input file does not contain a queries list: {path}")
    return payload


def extract_segment(query_shape: str, start_keyword: str, following_keywords: tuple[str, ...]) -> str | None:
    pattern = rf"\b{re.escape(start_keyword)}\s+"
    match = re.search(pattern, query_shape, flags=re.IGNORECASE)
    if not match:
        return None
    start = match.end()
    end = len(query_shape)
    for keyword in following_keywords:
        next_match = re.search(rf"\b{re.escape(keyword)}\b", query_shape[start:], flags=re.IGNORECASE)
        if next_match:
            end = min(end, start + next_match.start())
    value = query_shape[start:end].strip()
    return value or None


def operation_body(query_shape: str, operation: str, database: str | None, collection: str | None) -> str | None:
    namespace = ".".join(part for part in (database, collection) if part)
    prefix = f"{operation} {namespace}".strip()
    if query_shape.lower().startswith(prefix.lower()):
        body = query_shape[len(prefix) :].strip()
        return body or None
    return query_shape


def build_candidate(index: int, query: dict[str, Any]) -> dict[str, Any]:
    operation = query.get("operation")
    database = query.get("database")
    collection = query.get("collection")
    query_shape = query.get("query_shape") or ""
    if not operation or not query_shape:
        fail(f"Filtered query at index {index} is missing operation or query_shape.")

    filter_shape = None
    pipeline_shape = None
    if operation in {"find", "count", "distinct"}:
        filter_shape = operation_body(query_shape, str(operation), database, collection)
    elif operation == "aggregate":
        pipeline_shape = operation_body(query_shape, str(operation), database, collection)

    return {
        "id": f"warmup-{index:04d}",
        "database": database,
        "collection": collection,
        "operation": operation,
        "query_shape": query_shape,
        "filter_shape": filter_shape,
        "sort_shape": extract_segment(query_shape, "sort", ("projection", "limit", "skip")),
        "projection_shape": extract_segment(query_shape, "projection", ("sort", "limit", "skip")),
        "pipeline_shape": pipeline_shape,
        "source_metadata": {
            "total_load": query.get("total_load", 0.0),
            "sample_count": query.get("sample_count", 0),
            "source_instances": query.get("source_instances", []),
            "first_seen": query.get("first_seen"),
            "last_seen": query.get("last_seen"),
            "example_query_statement": query.get("example_query_statement"),
        },
    }


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    filtered = load_filtered(input_path)
    queries = filtered["queries"]
    candidates = [build_candidate(index, query) for index, query in enumerate(queries, start=1)]
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": {
            "input": str(input_path),
            "filtered_source": filtered.get("source"),
        },
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(candidates)} warm-up candidates to {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

