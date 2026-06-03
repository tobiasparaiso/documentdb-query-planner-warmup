#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Extract top Amazon DocumentDB read query digests from AWS Performance Insights.

Required inputs can be passed as CLI flags or environment variables:
  --region             AWS region. Env: AWS_REGION
  --db-resource-ids    Comma-separated DB resource IDs. Env: DOCDB_PI_RESOURCE_IDS
  --start-time         ISO-8601 start time. Env: DOCDB_PI_START_TIME
  --end-time           ISO-8601 end time. Env: DOCDB_PI_END_TIME
  --output-dir         Output directory. Env: OUTPUT_DIR. Default: query-warmup/output

Optional:
  --limit              Top query digest limit per instance. Default: 25
  --period-seconds     PI period in seconds. Default: 60
  -h, --help           Show this help.

Example:
  query-warmup/extract_queries.sh \
    --region us-east-1 \
    --db-resource-ids db-AAAA,db-BBBB \
    --start-time 2026-06-01T00:00:00Z \
    --end-time 2026-06-01T01:00:00Z \
    --output-dir query-warmup/output
USAGE
}

REGION="${AWS_REGION:-}"
RESOURCE_IDS="${DOCDB_PI_RESOURCE_IDS:-}"
START_TIME="${DOCDB_PI_START_TIME:-}"
END_TIME="${DOCDB_PI_END_TIME:-}"
OUTPUT_DIR="${OUTPUT_DIR:-query-warmup/output}"
LIMIT=25
PERIOD_SECONDS=60

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)
      REGION="${2:-}"
      shift 2
      ;;
    --db-resource-ids|--db-resource-id)
      RESOURCE_IDS="${2:-}"
      shift 2
      ;;
    --start-time)
      START_TIME="${2:-}"
      shift 2
      ;;
    --end-time)
      END_TIME="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:-}"
      shift 2
      ;;
    --period-seconds)
      PERIOD_SECONDS="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

require_value() {
  local name="$1"
  local value="$2"
  if [[ -z "$value" ]]; then
    echo "ERROR: Missing required input: $name" >&2
    usage >&2
    exit 2
  fi
}

require_value "--region or AWS_REGION" "$REGION"
require_value "--db-resource-ids or DOCDB_PI_RESOURCE_IDS" "$RESOURCE_IDS"
require_value "--start-time or DOCDB_PI_START_TIME" "$START_TIME"
require_value "--end-time or DOCDB_PI_END_TIME" "$END_TIME"

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI is required but was not found in PATH." >&2
  exit 127
fi

if [[ ! "$LIMIT" =~ ^[0-9]+$ ]] || [[ "$LIMIT" -lt 1 ]]; then
  echo "ERROR: --limit must be a positive integer." >&2
  exit 2
fi

if [[ ! "$PERIOD_SECONDS" =~ ^[0-9]+$ ]] || [[ "$PERIOD_SECONDS" -lt 1 ]]; then
  echo "ERROR: --period-seconds must be a positive integer." >&2
  exit 2
fi

RAW_DIR="$OUTPUT_DIR/raw"
mkdir -p "$RAW_DIR"

METRIC_QUERIES="[{\"Metric\":\"db.load.avg\",\"GroupBy\":{\"Group\":\"db.query_tokenized\",\"Limit\":$LIMIT}}]"
MANIFEST="$RAW_DIR/manifest.json"
MANIFEST_TMP="$MANIFEST.tmp"

printf '{\n' > "$MANIFEST_TMP"
printf '  "source": "aws pi get-resource-metrics",\n' >> "$MANIFEST_TMP"
printf '  "service_type": "DOCDB",\n' >> "$MANIFEST_TMP"
printf '  "region": "%s",\n' "$REGION" >> "$MANIFEST_TMP"
printf '  "start_time": "%s",\n' "$START_TIME" >> "$MANIFEST_TMP"
printf '  "end_time": "%s",\n' "$END_TIME" >> "$MANIFEST_TMP"
printf '  "metric": "db.load.avg",\n' >> "$MANIFEST_TMP"
printf '  "group_by": "db.query_tokenized",\n' >> "$MANIFEST_TMP"
printf '  "raw_files": [\n' >> "$MANIFEST_TMP"

IFS=',' read -r -a IDS <<< "$RESOURCE_IDS"
FILE_COUNT=0
for raw_id in "${IDS[@]}"; do
  resource_id="$(printf '%s' "$raw_id" | xargs)"
  if [[ -z "$resource_id" ]]; then
    continue
  fi

  safe_id="$(printf '%s' "$resource_id" | tr -c 'A-Za-z0-9_.-' '_')"
  output_file="$RAW_DIR/$safe_id.json"
  tmp_file="$output_file.tmp"

  echo "Extracting Performance Insights query metrics for $resource_id -> $output_file" >&2
  if ! aws pi get-resource-metrics \
    --region "$REGION" \
    --service-type DOCDB \
    --identifier "$resource_id" \
    --start-time "$START_TIME" \
    --end-time "$END_TIME" \
    --period-in-seconds "$PERIOD_SECONDS" \
    --metric-queries "$METRIC_QUERIES" \
    --output json > "$tmp_file"; then
    rm -f "$tmp_file"
    echo "ERROR: AWS Performance Insights extraction failed for resource ID: $resource_id" >&2
    exit 1
  fi

  python3 - "$resource_id" "$REGION" "$START_TIME" "$END_TIME" "$tmp_file" "$output_file" <<'PY'
import json
import sys
from pathlib import Path

resource_id, region, start_time, end_time, tmp_file, output_file = sys.argv[1:]
payload = json.loads(Path(tmp_file).read_text(encoding="utf-8"))
wrapped = {
    "source": {
        "service": "DOCDB",
        "resource_id": resource_id,
        "region": region,
        "start_time": start_time,
        "end_time": end_time,
        "metric": "db.load.avg",
        "group_by": "db.query_tokenized",
    },
    "performance_insights": payload,
}
Path(output_file).write_text(json.dumps(wrapped, indent=2, sort_keys=True) + "\n", encoding="utf-8")
Path(tmp_file).unlink()
PY

  if [[ "$FILE_COUNT" -gt 0 ]]; then
    printf ',\n' >> "$MANIFEST_TMP"
  fi
  printf '    {"resource_id": "%s", "file": "%s"}' "$resource_id" "$output_file" >> "$MANIFEST_TMP"
  FILE_COUNT=$((FILE_COUNT + 1))
done

if [[ "$FILE_COUNT" -eq 0 ]]; then
  rm -f "$MANIFEST_TMP"
  echo "ERROR: No DB resource IDs were provided after parsing --db-resource-ids." >&2
  exit 2
fi

printf '\n  ]\n' >> "$MANIFEST_TMP"
printf '}\n' >> "$MANIFEST_TMP"
mv "$MANIFEST_TMP" "$MANIFEST"

echo "Wrote raw Performance Insights files under $RAW_DIR" >&2
echo "Wrote manifest $MANIFEST" >&2

