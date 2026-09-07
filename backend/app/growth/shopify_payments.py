"""Read-only Partner sales receipts; subscription activation alone is never payment."""
import os
import json
import re
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

import requests
from sqlalchemy import select

from app.db.models import Shop, Subscription, User
from .funnel import product_event
from .models import Evidence
from .policy import GrowthError
from .store import digest, get_memory, record, remember

QUERY = """query GrowthReceipts($appId: ID!, $from: DateTime!, $to: DateTime!, $after: String) {
  transactions(first: 50, appId: $appId, createdAtMin: $from, createdAtMax: $to, after: $after) {
    edges { cursor node { __typename ... on AppSubscriptionSale {
      id createdAt chargeId billingInterval app { id } shop { myshopifyDomain }
      grossAmount { amount currencyCode }
    } } }
    pageInfo { hasNextPage }
  }
}"""


def partner_request(variables):
    organization = os.getenv("SHOPIFY_PARTNER_ORGANIZATION_ID", "")
    token = os.getenv("SHOPIFY_PARTNER_API_TOKEN", "")
    if not re.fullmatch(r"\d+", organization) or not token:
        raise GrowthError("Read-only Shopify Partner finance integration is not configured", "configuration")
    try:
        with requests.post(f"https://partners.shopify.com/{organization}/api/2026-07/graphql.json",
            headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
            json={"query": QUERY, "variables": variables}, timeout=20, allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                raise GrowthError(f"Partner API HTTP {response.status_code}", "configuration" if response.status_code in (401, 403) else "transient")
            raw = response.raw.read(512001, decode_content=True)
            if len(raw) > 512000:
                raise GrowthError("Partner receipts exceed bounded response", "permanent")
            payload = json.loads(raw)
        if payload.get("errors"):
            raise GrowthError("Partner API rejected the receipt query", "configuration")
        return payload["data"]["transactions"]
    except (requests.RequestException, ValueError, KeyError):
        raise GrowthError("Partner receipt read failed", "transient") from None


def ingest_sale(db, item, app_id):
    if item.get("__typename") != "AppSubscriptionSale" or item.get("app", {}).get("id") != app_id:
        return False
    amount = item.get("grossAmount") or {}
    try:
        gross = Decimal(amount.get("amount", "0"))
        if not gross.is_finite() or gross <= 0:
            return False
        at = datetime.fromisoformat(item["createdAt"].replace("Z", "+00:00")).timestamp()
    except (InvalidOperation, ValueError, KeyError, TypeError):
        return False
    domain = (item.get("shop") or {}).get("myshopifyDomain", "")
    domain = urlparse(domain if "://" in domain else "https://" + domain).hostname
    shop = db.scalar(select(Shop).where(Shop.shopify_domain == domain))
    if not shop or not db.scalar(select(User.id).where(User.shop_id == shop.id, User.is_admin.is_(False), ~User.email.like("%@skubase.io"))):
        return False
    if not item.get("id"):
        return False
    event = product_event(db, "SUBSCRIPTION_PURCHASED", shop.id, "partner-sale:" + digest(item["id"]),
        data={"receipt_id": item["id"], "charge_id": item.get("chargeId"), "provider": "shopify_partner",
              "amount": float(gross), "currency": amount.get("currencyCode"), "payment_verified": True}, occurred_at=at)
    if not event:
        return False
    old = get_memory(db, "economics", f"shop:{shop.id}")
    if old.get("observed_at", 0) > at:
        return True
    sub = db.scalar(select(Subscription).where(Subscription.shop_id == shop.id))
    active = bool(sub and sub.status in ("active", "trialing"))
    # Collected subscription amounts are not necessarily contract MRR (proration/discounts).
    # Keep the receipt and interval; don't fabricate an undiscounted recurring price.
    remember(db, "economics", f"shop:{shop.id}", {"active": active, "monthly_recurring_usd": None,
        "last_collected_amount": float(gross), "currency": amount.get("currencyCode"),
        "billing_interval": item.get("billingInterval"), "source_receipt": item["id"], "observed_at": at,
        "mrr_limitation": "Collected receipt may be prorated or discounted; contract price not yet attested"})
    return True


def reconcile_payments(factory, provider=partner_request):
    app_id = os.getenv("SHOPIFY_PARTNER_APP_ID", "")
    if not re.fullmatch(r"gid://(?:partners|shopify)/App/\d+", app_id):
        raise GrowthError("Configure the exact Skubase Partner app ID", "configuration")
    now = time.time()
    with factory() as db:
        state = get_memory(db, "working", "partner-receipts")
        start = state.get("from", max(0, get_memory(db, "strategic", "identity").get("started_at", now) - 86400))
        end = state.get("to", now - 60)
    iso = lambda value: datetime.fromtimestamp(value, timezone.utc).isoformat()
    result = provider({"appId": app_id, "from": iso(start), "to": iso(end), "after": state.get("after")})
    edges = result.get("edges", [])[:50]
    with factory() as db:
        count = sum(ingest_sale(db, edge["node"], app_id) for edge in edges)
        if result.get("pageInfo", {}).get("hasNextPage") and edges:
            next_state = {"from": start, "to": end, "after": edges[-1]["cursor"]}
        else:
            next_state = {"from": max(start, end - 86400)}  # overlap protects delayed receipts; keys deduplicate
        remember(db, "working", "partner-receipts", next_state)
        record(db, "partner-reconcile:" + digest([start, end, state.get("after")]), "PAYMENTS_RECONCILED", "billing",
               {"rows_examined": len(edges), "matched_receipts": count, "paid_api_usd": 0})
        db.commit()
    return {"receipts_observed": count, "rows_examined": len(edges)}
