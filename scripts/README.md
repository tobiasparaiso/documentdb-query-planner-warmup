# Scripts

This directory contains helper scripts for optional DocumentDB MCP workflows.

The core warm-up toolkit is in `query-warmup/`. These scripts are not required to extract Performance Insights data, filter query shapes, or generate warm-up candidates.

## `docdb-mcp-connect.sh`

Starts the AWS Labs DocumentDB MCP server in read-oriented inspection mode. The launcher can use a provided `DOCDB_URI` or attempt to discover a connection string from AWS DocumentDB cluster metadata and Secrets Manager.

Required or commonly used environment variables:

- `DOCDB_URI`: full MongoDB connection string. If set, auto-discovery is skipped.
- `DOCDB_AUTO_DISCOVER_URI`: set to `false` to disable AWS-based URI discovery.
- `DOCDB_AWS_PROFILE` or `AWS_PROFILE`: AWS profile for cluster and secret lookup.
- `AWS_REGION`: AWS region. Defaults to `us-east-1`.
- `DOCDB_CLUSTER_IDENTIFIER`: DocumentDB cluster identifier used for auto-discovery.
- `DOCDB_TLS_CA_FILE`: TLS CA bundle path. Defaults to the repo `global-bundle.pem` when present.
- `FASTMCP_LOG_LEVEL`: MCP log level. Defaults to `ERROR`.

Example MCP client command configuration:

```json
{
  "mcpServers": {
    "documentdb": {
      "command": "bash",
      "args": ["/path/to/documentdb-query-planner-warmup/scripts/docdb-mcp-connect.sh"],
      "env": {
        "FASTMCP_LOG_LEVEL": "ERROR",
        "AWS_REGION": "us-east-1",
        "DOCDB_CLUSTER_IDENTIFIER": "example-docdb-cluster"
      }
    }
  }
}
```

Do not hardcode credentials in this script or in committed MCP client config. Use environment variables, AWS profiles, and managed secrets.

## `test_docdb_mcp_connect.sh`

Runs a local shell test for the launcher. It stubs `aws` and `uvx` so it can verify URI construction and default environment handling without contacting AWS or DocumentDB.

```bash
bash scripts/test_docdb_mcp_connect.sh
```

## Safety

The launcher is intended for inspection workflows such as listing databases, collections, indexes, sampling documents, explaining queries, and reviewing generated warm-up candidates through an MCP client. It is separate from the warm-up candidate generator and does not make the generated candidates executable.
