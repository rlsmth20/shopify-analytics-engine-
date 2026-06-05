# Shopify mandatory privacy webhooks

Skubase exposes Shopify's required customer privacy webhooks from the FastAPI
backend. These endpoints verify `X-Shopify-Hmac-Sha256` using
`SHOPIFY_CLIENT_SECRET` and return quickly.

Public backend domain:

```text
https://api.skubase.io
```

## Endpoints

```text
POST /webhooks/customers/data_request
POST /webhooks/customers/redact
POST /webhooks/shop/redact
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
topics = ["customers/data_request"]
uri = "https://api.skubase.io/webhooks/customers/data_request"

[[webhooks.subscriptions]]
topics = ["customers/redact"]
uri = "https://api.skubase.io/webhooks/customers/redact"

[[webhooks.subscriptions]]
topics = ["shop/redact"]
uri = "https://api.skubase.io/webhooks/shop/redact"
```

## Data handling

- `customers/data_request`: Skubase acknowledges the request. Skubase does not
  store Shopify customer profiles, customer emails, addresses, or customer
  account records in its inventory analytics tables.
- `customers/redact`: Skubase acknowledges the request. There is no customer
  profile table to redact today.
- `shop/redact`: Skubase clears any stored Shopify access token for the shop
  and marks the Shopify connection as uninstalled. Longer retention/deletion
  policy work should run outside the webhook response path.

Do not log webhook payloads. Logs should include only topic, shop domain,
webhook id, and success/failure.
