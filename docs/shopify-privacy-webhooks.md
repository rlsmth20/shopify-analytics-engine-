# Shopify mandatory privacy webhooks

Skubase exposes Shopify's required customer privacy webhooks from the FastAPI
backend. These endpoints verify `X-Shopify-Hmac-Sha256` using
`SHOPIFY_CLIENT_SECRET` and commit the requested work before acknowledging it.

Public backend domain:

```text
https://api.skubase.io
```

## Endpoints

```text
POST /webhooks/customers/data_request
POST /webhooks/customers/redact
POST /webhooks/shop/redact
POST /webhooks/app/uninstalled
```

Compatibility aliases:

```text
POST /webhooks/customers_data_request
POST /webhooks/customers_redact
POST /webhooks/shop_redact
```

## Shopify app config

If registering through Shopify app TOML, use:

```toml
[webhooks]
api_version = "2026-04"

[[webhooks.subscriptions]]
compliance_topics = ["customers/data_request"]
uri = "https://api.skubase.io/webhooks/customers/data_request"

[[webhooks.subscriptions]]
compliance_topics = ["customers/redact"]
uri = "https://api.skubase.io/webhooks/customers/redact"

[[webhooks.subscriptions]]
compliance_topics = ["shop/redact"]
uri = "https://api.skubase.io/webhooks/shop/redact"
```

## Data handling

- `customers/data_request`: Records an idempotent audit receipt with requested
  order identifiers, without retaining customer names, emails, addresses, or
  phone numbers from the webhook. Merchants can list and download matching
  retained order analytics under Settings > Privacy Requests.
- `customers/redact`: Deletes the requested order lines and removes their
  identifiers from previous access-request receipts. Both historical bare order
  IDs and current `order:line` references are matched at exact order boundaries.
- `shop/redact`: Transactionally deletes the matching tenant's records in foreign
  key dependency order, including app users, sessions, connection tokens,
  analytics, settings, billing metadata, legacy channels, and linked signups.
  An interrupted deletion rolls back and returns an error so Shopify can retry.
- `app/uninstalled`: Revokes tokens and local Shopify subscription access while
  preserving analytics until Shopify issues shop redaction.

Tenancy is resolved from the signed payload's shop domain, never its numeric
Shopify shop ID. Event timestamps and installation timestamps protect newer
installations from delayed uninstall/redact deliveries. An active connection
with no original event timestamp is preserved because its installation cannot
be safely distinguished from a reinstall; logs expose preservation counts.

Authenticated exports use `GET /webhooks/customer-data-requests` and
`GET /webhooks/customer-data-requests/{id}`. They are tenant-scoped, use
`Cache-Control: no-store`, and do not require a paid plan. Downloads stay local;
merchants must deliver them to the entitled requester through their own process.

Nine synthetic tests in `backend/tests/test_shopify_privacy.py` cover all current
tenant tables, another tenant's preservation, rollback, repeat delivery,
reinstall protection, signed-domain validation, and export authorization. These
tests do not send webhooks to production. Provider backup retention remains a
separate operational obligation; this handler deletes production database data.

Do not log webhook payloads. Logs include the topic and non-personal result counts.
