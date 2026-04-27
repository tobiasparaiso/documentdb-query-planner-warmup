# `sales_demo.subscriptions`

Purpose: Generic recurring subscription records that complement orders with a different status and lifecycle profile.

Common fields:
- `client_id`: Reused client key such as `client_0042`
- `status`: `trial`, `active`, `past_due`, `paused`, `cancelled`
- `category`: `starter`, `growth`, `enterprise`, `support`, `backup`
- `region`: `us-east`, `us-west`, `eu-west`, `eu-central`, `ap-southeast`
- `created_at`: UTC subscription creation timestamp over the last 90 days

Collection-specific fields:
- `subscription_id`: Stable synthetic ID such as `SUB-00001234`
- `plan_tier`: `basic`, `standard`, `premium`, `enterprise`
- `billing_cycle`: `monthly`, `quarterly`, `annual`
- `renewal_date`: Future UTC renewal timestamp based on the billing cycle

Example document:

```json
{
  "subscription_id": "SUB-00001234",
  "client_id": "client_0042",
  "status": "active",
  "category": "growth",
  "region": "us-east",
  "created_at": "2026-03-28T08:05:00Z",
  "plan_tier": "premium",
  "billing_cycle": "annual",
  "renewal_date": "2027-03-28T08:05:00Z"
}
```
