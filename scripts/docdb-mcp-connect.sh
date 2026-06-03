#!/usr/bin/env bash
set -euo pipefail

# Repo-local launcher for the AWS Labs DocumentDB MCP server.
#
# MCP client example:
# {
#   "mcpServers": {
#     "documentdb": {
#       "command": "bash",
#       "args": ["/Users/tobiasparaiso/TPTech/documentdb-query-planner-warmup/scripts/docdb-mcp-connect.sh"],
#       "env": {
#         "FASTMCP_LOG_LEVEL": "ERROR",
#         "DOCDB_AWS_PROFILE": "personal",
#         "AWS_REGION": "us-east-1",
#         "DOCDB_CLUSTER_IDENTIFIER": "tp-tech-dev-docdb"
#       }
#     }
#   }
# }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

export FASTMCP_LOG_LEVEL="${FASTMCP_LOG_LEVEL:-ERROR}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export DOCDB_CLUSTER_IDENTIFIER="${DOCDB_CLUSTER_IDENTIFIER:-tp-tech-dev-docdb}"
export DOCDB_AWS_PROFILE="${DOCDB_AWS_PROFILE:-${AWS_PROFILE:-personal}}"
export AWS_PROFILE="${AWS_PROFILE:-$DOCDB_AWS_PROFILE}"

if [[ -z "${DOCDB_TLS_CA_FILE:-}" && -f "$REPO_ROOT/global-bundle.pem" ]]; then
  export DOCDB_TLS_CA_FILE="$REPO_ROOT/global-bundle.pem"
fi

log() {
  printf 'docdb-mcp-connect: %s\n' "$*" >&2
}

build_docdb_uri_from_aws() {
  if ! command -v aws >/dev/null 2>&1; then
    log "AWS CLI is not available; cannot auto-discover DOCDB_URI."
    return 1
  fi

  if ! command -v python3 >/dev/null 2>&1; then
    log "python3 is not available; cannot URL-encode the generated DOCDB_URI."
    return 1
  fi

  local cluster_info endpoint port master_username secret_arn secret_json

  if ! cluster_info="$(
    aws docdb describe-db-clusters \
      --db-cluster-identifier "$DOCDB_CLUSTER_IDENTIFIER" \
      --region "$AWS_REGION" \
      --query 'DBClusters[0].[Endpoint,Port,MasterUsername,MasterUserSecret.SecretArn]' \
      --output text 2>/dev/null
  )"; then
    log "Unable to describe DocumentDB cluster $DOCDB_CLUSTER_IDENTIFIER with AWS profile ${AWS_PROFILE:-<not set>}."
    return 1
  fi

  read -r endpoint port master_username secret_arn <<<"$cluster_info"

  if [[ -z "${endpoint:-}" || -z "${port:-}" || -z "${secret_arn:-}" || "$secret_arn" == "None" ]]; then
    log "Cluster metadata did not include endpoint, port, and MasterUserSecret ARN."
    return 1
  fi

  if ! secret_json="$(
    aws secretsmanager get-secret-value \
      --secret-id "$secret_arn" \
      --region "$AWS_REGION" \
      --query SecretString \
      --output text 2>/dev/null
  )"; then
    log "Unable to read DocumentDB master user secret from Secrets Manager."
    return 1
  fi

  DOCDB_ENDPOINT="$endpoint" \
    DOCDB_PORT="$port" \
    DOCDB_MASTER_USERNAME="$master_username" \
    DOCDB_SECRET_JSON="$secret_json" \
    python3 - <<'PY'
import json
import os
import urllib.parse

secret = json.loads(os.environ["DOCDB_SECRET_JSON"])
username = secret.get("username") or os.environ["DOCDB_MASTER_USERNAME"]
password = secret["password"]
endpoint = os.environ["DOCDB_ENDPOINT"]
port = os.environ["DOCDB_PORT"]
tls_ca_file = os.environ.get("DOCDB_TLS_CA_FILE", "")

params = [
    ("tls", "true"),
    ("replicaSet", "rs0"),
    ("readPreference", "secondaryPreferred"),
    ("retryWrites", "false"),
]
if tls_ca_file:
    params.insert(1, ("tlsCAFile", tls_ca_file))

print(
    "mongodb://"
    + urllib.parse.quote(username, safe="")
    + ":"
    + urllib.parse.quote(password, safe="")
    + "@"
    + endpoint
    + ":"
    + str(port)
    + "/?"
    + urllib.parse.urlencode(params)
)
PY
}

has_python_module() {
  python3 -c 'import importlib.util; raise SystemExit(0 if importlib.util.find_spec("awslabs.documentdb_mcp_server.server") else 1)' >/dev/null 2>&1
}

if [[ -z "${DOCDB_URI:-}" && "${DOCDB_AUTO_DISCOVER_URI:-true}" != "false" ]]; then
  if DOCDB_URI="$(build_docdb_uri_from_aws)"; then
    export DOCDB_URI
    log "DOCDB_URI auto-discovered from cluster metadata and Secrets Manager."
  fi
fi

log "AWS profile: ${AWS_PROFILE:-<not set>}"
log "AWS region: $AWS_REGION"
log "DocumentDB cluster: $DOCDB_CLUSTER_IDENTIFIER"
log "DOCDB_URI set: $(if [[ -n "${DOCDB_URI:-}" ]]; then printf 'yes'; else printf 'no'; fi)"

if [[ -n "${DOCDB_TLS_CA_FILE:-}" ]]; then
  log "TLS CA file: $DOCDB_TLS_CA_FILE"
fi

if [[ -z "${DOCDB_URI:-}" ]]; then
  log "DOCDB_URI is not set. Start-up can continue, but the MCP connect tool will need a full DocumentDB connection string."
  log "Do not place database passwords in this script; provide DOCDB_URI through the MCP client environment or a secure secret source."
fi

if command -v uvx >/dev/null 2>&1; then
  log "Starting AWS Labs DocumentDB MCP server via uvx in read-only mode."
  exec uvx awslabs.documentdb-mcp-server@latest "$@"
fi

if has_python_module; then
  log "Starting AWS Labs DocumentDB MCP server via python module in read-only mode."
  exec python3 -m awslabs.documentdb_mcp_server.server "$@"
fi

log "Unable to find uvx or installed Python module awslabs.documentdb_mcp_server.server."
log "Install uv/uvx or install the awslabs.documentdb-mcp-server package before enabling this MCP server."
exit 127