#!/usr/bin/env python3
"""Regression tests for the DocumentDB query warm-up toolkit."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main


REPO_ROOT = Path(__file__).resolve().parents[1]
FILTER_SCRIPT = REPO_ROOT / "query-warmup" / "filter_queries.py"
CANDIDATE_SCRIPT = REPO_ROOT / "query-warmup" / "generate_warmup_candidates.py"


class QueryWarmupPipelineTest(TestCase):
    def test_filters_and_deduplicates_pi_query_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            raw_dir = workdir / "raw"
            raw_dir.mkdir()
            filtered_path = workdir / "filtered_queries.json"
            candidates_path = workdir / "warmup_candidates.json"

            raw_payload = {
                "MetricList": [
                    {
                        "Key": {
                            "Metric": "db.load.avg",
                            "Dimensions": {
                                "db.query_tokenized": (
                                    "find sales_demo.orders "
                                    '{"client_id":"client_0001","created_at":{"$gte":"2026-06-01T00:00:00Z"}} '
                                    'projection {"_id":0,"client_id":1} sort {"created_at":-1}'
                                ),
                                "db.name": "sales_demo",
                            },
                        },
                        "DataPoints": [
                            {"Timestamp": "2026-06-01T00:00:00Z", "Value": 1.5},
                            {"Timestamp": "2026-06-01T00:01:00Z", "Value": 2.5},
                        ],
                    },
                    {
                        "Key": {
                            "Metric": "db.load.avg",
                            "Dimensions": {
                                "db.query_tokenized": (
                                    "find sales_demo.orders "
                                    '{"client_id":"client_9999","created_at":{"$gte":"2026-05-31T00:00:00Z"}} '
                                    'projection {"_id":0,"client_id":1} sort {"created_at":-1}'
                                ),
                                "db.name": "sales_demo",
                            },
                        },
                        "DataPoints": [{"Timestamp": "2026-06-01T00:02:00Z", "Value": 3.0}],
                    },
                    {
                        "Key": {
                            "Metric": "db.load.avg",
                            "Dimensions": {
                                "db.query_tokenized": (
                                    "aggregate support_demo.events "
                                    '[{"$match":{"region":"us-east"}},{"$group":{"_id":"$status","total":{"$sum":1}}}]'
                                ),
                                "db.name": "support_demo",
                            },
                        },
                        "DataPoints": [{"Timestamp": "2026-06-01T00:03:00Z", "Value": 4.0}],
                    },
                    {
                        "Key": {
                            "Metric": "db.load.avg",
                            "Dimensions": {
                                "db.query_tokenized": (
                                    'count support_demo.tickets {"region":"eu-west","created_at":{"$gte":"2026-06-01T00:00:00Z"}}'
                                ),
                                "db.name": "support_demo",
                            },
                        },
                        "DataPoints": [{"Timestamp": "2026-06-01T00:03:30Z", "Value": 2.0}],
                    },
                    {
                        "Key": {
                            "Metric": "db.load.avg",
                            "Dimensions": {
                                "db.query_tokenized": 'update sales_demo.orders {"status":"pending"}',
                                "db.name": "sales_demo",
                            },
                        },
                        "DataPoints": [{"Timestamp": "2026-06-01T00:04:00Z", "Value": 10.0}],
                    },
                    {
                        "Key": {
                            "Metric": "db.load.avg",
                            "Dimensions": {
                                "db.query_tokenized": "hello admin.$cmd",
                                "db.name": "admin",
                            },
                        },
                        "DataPoints": [{"Timestamp": "2026-06-01T00:05:00Z", "Value": 10.0}],
                    },
                ]
            }
            (raw_dir / "db-ONE.json").write_text(json.dumps(raw_payload), encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(FILTER_SCRIPT),
                    "--input-dir",
                    str(raw_dir),
                    "--output",
                    str(filtered_path),
                ],
                check=True,
            )

            filtered = json.loads(filtered_path.read_text(encoding="utf-8"))
            self.assertEqual(filtered["query_count"], 3)
            self.assertEqual(filtered["source"]["input_dir"], str(raw_dir))

            find_entry = next(item for item in filtered["queries"] if item["operation"] == "find")
            self.assertEqual(find_entry["database"], "sales_demo")
            self.assertEqual(find_entry["collection"], "orders")
            self.assertEqual(find_entry["total_load"], 7.0)
            self.assertEqual(find_entry["sample_count"], 3)
            self.assertIn("<string>", find_entry["query_shape"])
            self.assertEqual(find_entry["source_instances"], ["db-ONE"])

            subprocess.run(
                [
                    sys.executable,
                    str(CANDIDATE_SCRIPT),
                    "--input",
                    str(filtered_path),
                    "--output",
                    str(candidates_path),
                ],
                check=True,
            )

            candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
            self.assertEqual(candidates["candidate_count"], 3)
            first = candidates["candidates"][0]
            self.assertEqual(first["operation"], "find")
            self.assertEqual(first["database"], "sales_demo")
            self.assertEqual(first["collection"], "orders")
            self.assertIn("query_shape", first)
            self.assertIn("source_metadata", first)

    def test_filters_actual_pi_json_command_statements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            raw_dir = workdir / "raw"
            raw_dir.mkdir()
            filtered_path = workdir / "filtered_queries.json"

            raw_payload = {
                "MetricList": [
                    {
                        "Key": {
                            "Metric": "db.load.avg",
                            "Dimensions": {
                                "db.query_tokenized.db_id": "pi-3422852797",
                                "db.query_tokenized.id": "DB8CC33B37EB31A94E02AB5C44EAEB3A0A72AF1B",
                                "db.query_tokenized.statement": (
                                    '{"find":"tickets","filter":{"client_id":"?",'
                                    '"created_at":{"$gte":{"$date":{"$numberLong":"?"}}}},'
                                    '"projection":{"_id":{"$numberInt":"0"},"client_id":{"$numberInt":"1"}},'
                                    '"limit":{"$numberInt":"?"},"$db":"support_demo",'
                                    '"$readPreference":{"mode":"secondaryPreferred"}}'
                                ),
                            },
                        },
                        "DataPoints": [{"Timestamp": "2026-06-02T04:00:00Z", "Value": 1.25}],
                    },
                    {
                        "Key": {
                            "Metric": "db.load.avg",
                            "Dimensions": {
                                "db.query_tokenized.id": "024B9E13169A4B046C62337655D95F1438D7B597",
                                "db.query_tokenized.statement": (
                                    '{"aggregate":"tickets","pipeline":[{"$match":{"created_at":'
                                    '{"$gte":{"$date":{"$numberLong":"?"}}}}},{"$group":{"_id":"?",'
                                    '"total":{"$sum":{"$numberInt":"?"}}}}],"cursor":{},'
                                    '"$db":"support_demo","$readPreference":{"mode":"secondaryPreferred"}}'
                                ),
                            },
                        },
                        "DataPoints": [{"Timestamp": "2026-06-02T04:01:00Z", "Value": 2.5}],
                    },
                ]
            }
            (raw_dir / "db-ACTUAL.json").write_text(json.dumps(raw_payload), encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(FILTER_SCRIPT),
                    "--input-dir",
                    str(raw_dir),
                    "--output",
                    str(filtered_path),
                ],
                check=True,
            )

            filtered = json.loads(filtered_path.read_text(encoding="utf-8"))
            self.assertEqual(filtered["query_count"], 2)
            operations = {item["operation"] for item in filtered["queries"]}
            self.assertEqual(operations, {"find", "aggregate"})
            collections = {item["collection"] for item in filtered["queries"]}
            self.assertEqual(collections, {"tickets"})


if __name__ == "__main__":
    main()
