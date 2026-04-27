# `support_demo.events`

Purpose: Generic operational event records that add higher-volume documents and varied aggregate patterns.

Common fields:
- `client_id`: Reused client key such as `client_0042`
- `status`: `queued`, `processing`, `completed`, `skipped`, `failed`
- `category`: `login`, `sync`, `webhook`, `export`, `alert`, `billing`, `audit`
- `region`: `us-east`, `us-west`, `eu-west`, `eu-central`, `ap-southeast`
- `created_at`: UTC event creation timestamp over the last 90 days

Collection-specific fields:
- `event_id`: Stable synthetic ID such as `EVT-00001234`
- `event_type`: `create`, `update`, `delete`, `retry`, `notify`
- `source`: `api`, `scheduler`, `mobile_app`, `backoffice`, `partner_sync`
- `processed_at`: UTC timestamp showing downstream processing completion

Example document:

```json
{
  "event_id": "EVT-00001234",
  "client_id": "client_0042",
  "status": "completed",
  "category": "webhook",
  "region": "us-west",
  "created_at": "2026-04-15T21:09:30Z",
  "event_type": "notify",
  "source": "scheduler",
  "processed_at": "2026-04-15T21:42:30Z"
}
```
