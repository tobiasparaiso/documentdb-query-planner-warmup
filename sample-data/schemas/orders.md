# `sales_demo.orders`

Purpose: Generic sales order records used for client lookups, status aggregations, and regional counts.

Common fields:
- `client_id`: Reused client key such as `client_0042`
- `status`: `pending`, `processing`, `shipped`, `delivered`, `cancelled`
- `category`: `software`, `hardware`, `services`, `analytics`, `storage`, `security`
- `region`: `us-east`, `us-west`, `eu-west`, `eu-central`, `ap-southeast`
- `created_at`: UTC order creation timestamp over the last 90 days

Collection-specific fields:
- `order_id`: Stable synthetic ID such as `ORD-00001234`
- `amount`: Order value in USD
- `channel`: `web`, `sales_rep`, `partner`, `marketplace`
- `priority`: `low`, `medium`, `high`, `urgent`

Example document:

```json
{
  "order_id": "ORD-00001234",
  "client_id": "client_0042",
  "status": "delivered",
  "category": "analytics",
  "region": "eu-west",
  "created_at": "2026-04-03T11:22:33Z",
  "amount": 1499.95,
  "channel": "partner",
  "priority": "medium"
}
```
