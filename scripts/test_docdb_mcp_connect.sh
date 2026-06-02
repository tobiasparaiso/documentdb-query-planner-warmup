#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cat >"$TMP_DIR/aws" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

if [[ "$1 $2" == "docdb describe-db-clusters" ]]; then
  [[ "${AWS_PROFILE:-}" == "personal" ]] || {
    printf 'expected AWS_PROFILE=personal, got %s\n' "${AWS_PROFILE:-<unset>}" >&2
    exit 10
  }
  printf 'tp-tech-dev-docdb.cluster-example.us-east-1.docdb.amazonaws.com\t27017\tmaster\tarn:aws:secretsmanager:us-east-1:123456789012:secret:test\n'
  exit 0
fi

if [[ "$1 $2" == "secretsmanager get-secret-value" ]]; then
  printf '{"username":"master","password":"pass word/with:special@chars"}\n'
  exit 0
fi

printf 'unexpected aws command: %s\n' "$*" >&2
exit 11
SH

cat >"$TMP_DIR/uvx" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

printf 'AWS_PROFILE=%s\n' "${AWS_PROFILE:-}"
printf 'DOCDB_URI=%s\n' "${DOCDB_URI:-}"
printf 'DOCDB_TLS_CA_FILE=%s\n' "${DOCDB_TLS_CA_FILE:-}"
printf 'ARGS=%s\n' "$*"
SH

chmod +x "$TMP_DIR/aws" "$TMP_DIR/uvx"

OUTPUT="$(
  env -i \
    PATH="$TMP_DIR:/usr/bin:/bin:/usr/sbin:/sbin" \
    HOME="$HOME" \
    bash "$ROOT_DIR/scripts/docdb-mcp-connect.sh"
)"

[[ "$OUTPUT" == *"AWS_PROFILE=personal"* ]]
[[ "$OUTPUT" == *"DOCDB_URI=mongodb://master:pass%20word%2Fwith%3Aspecial%40chars@tp-tech-dev-docdb.cluster-example.us-east-1.docdb.amazonaws.com:27017/"* ]]
[[ "$OUTPUT" == *"tls=true"* ]]
[[ "$OUTPUT" == *"replicaSet=rs0"* ]]
[[ "$OUTPUT" == *"readPreference=secondaryPreferred"* ]]
[[ "$OUTPUT" == *"retryWrites=false"* ]]
[[ "$OUTPUT" == *"DOCDB_TLS_CA_FILE=$ROOT_DIR/global-bundle.pem"* ]]

printf 'ok\n'
