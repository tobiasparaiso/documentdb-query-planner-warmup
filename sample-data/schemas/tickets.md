# `support_demo.tickets`

Purpose: Generic support case records for read-heavy troubleshooting style queries and occasional status changes.

Common fields:
- `client_id`: Reused client key such as `client_0042`
- `status`: `new`, `open`, `pending`, `resolved`, `closed`
- `category`: `billing`, `access`, `incident`, `configuration`, `integration`, `reporting`
- `region`: `us-east`, `us-west`, `eu-west`, `eu-central`, `ap-southeast`
- `created_at`: UTC ticket creation timestamp over the last 90 days

Collection-specific fields:
- `ticket_id`: Stable synthetic ID such as `TCK-00001234`
- `severity`: `low`, `medium`, `high`, `critical`
- `assigned_team`: `ops`, `support`, `billing`, `platform`, `security`
- `resolved_at`: Nullable UTC timestamp for resolved or closed tickets

Example document:

```json
{
  "ticket_id": "TCK-00001234",
  "client_id": "client_0042",
  "status": "resolved",
  "category": "integration",
  "region": "eu-central",
  "created_at": "2026-04-10T15:17:45Z",
  "severity": "high",
  "assigned_team": "platform",
  "resolved_at": "2026-04-11T07:17:45Z"
}
```
