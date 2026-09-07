"""Authoritative product facts and conservative cohort projections."""
import time
from datetime import timezone

from sqlalchemy import func, select

from app.db.models import InventoryRiskSnapshotLead, ShopifyConnection, ShopifySyncRun, Subscription, User, Shop
from .models import Contact, Evidence
from .store import digest, enqueue, get_memory, record, remember

STAGES = ("VISITOR", "SIGNUP", "SHOPIFY_CONNECTION", "INVENTORY_ANALYSIS_VIEWED", "TRIAL_STARTED", "SUBSCRIPTION_PURCHASED")
CLIENT_EVENTS = {"VISITOR", "PRICING_VIEWED", "LANDING_VIEWED", "CALCULATOR_USED", "inventory_snapshot_page_view",
                 "inventory_snapshot_cta_click", "sample_snapshot_view", "sample_snapshot_cta_click",
                 "inventory_snapshot_form_start", "inventory_snapshot_form_submit"}


def timestamp(value):
    if value is None:
        return time.time()
    return value.replace(tzinfo=timezone.utc).timestamp() if value.tzinfo is None else value.timestamp()


def product_event(db, kind, shop_id, key, *, data=None, occurred_at=None):
    import os
    shop = db.get(Shop, shop_id)
    excluded = {s.strip() for s in os.getenv("GROWTH_EXCLUDED_SHOP_DOMAINS", "skubase-test.myshopify.com").split(",")}
    if shop and shop.shopify_domain in excluded:
        return None
    return record(db, "funnel:" + key, kind, f"shop:{shop_id}", {"verified": True, **(data or {})},
                  source="skubase_backend", epistemic="FACT", occurred_at=occurred_at)


def record_view(db, user, kind, usable):
    if user.is_admin or not usable:
        return
    delivered = kind.replace("_VIEWED", "_DELIVERED")
    product_event(db, delivered, user.shop_id, f"{delivered}:{user.shop_id}:{int(time.time() // 3600)}")
    enqueue(db, f"funnel-wake:{int(time.time() // 300)}", "observe", priority=70)
    db.commit()


def reconcile(db, batch_size=200):
    """Forward-only ID cursors for immutable entities; overlap cursor for mutable rows."""
    for model, name in ((User, "users"), (ShopifyConnection, "connections"), (InventoryRiskSnapshotLead, "leads")):
        cursor = get_memory(db, "working", "cursor:" + name).get("id", 0)
        rows = list(db.scalars(select(model).where(model.id > cursor).order_by(model.id).limit(batch_size)))
        for row in rows:
            if isinstance(row, User):
                if row.is_admin or row.email.endswith("@skubase.io"):
                    continue
                product_event(db, "SIGNUP", row.shop_id, f"signup:{row.id}", occurred_at=timestamp(row.created_at))
                if row.trial_ends_at:
                    product_event(db, "TRIAL_STARTED", row.shop_id, f"trial:{row.id}", occurred_at=timestamp(row.created_at))
                contact = db.scalar(select(Contact).where(Contact.email == row.email))
                if contact:
                    contact.shop_id = row.shop_id
            elif isinstance(row, ShopifyConnection):
                user = db.scalar(select(User).where(User.shop_id == row.shop_id, User.is_admin.is_(False)))
                if user and not user.email.endswith("@skubase.io"):
                    product_event(db, "SHOPIFY_CONNECTION", row.shop_id, f"connection:{row.id}", occurred_at=timestamp(row.installed_at))
            else:
                email = row.email.lower()
                contact = db.scalar(select(Contact).where(Contact.email == email))
                if not contact:
                    contact = Contact(identity="email:" + email, email=email, organization=row.company_name,
                        source=row.store_url, contact_basis="requested_health_check", status="high_intent",
                        characteristics={"sku_count": row.approximate_sku_count, "problem": row.biggest_inventory_issue},
                        facts=[{"text": "You requested an inventory risk snapshot", "source": "skubase_form", "verified": True}],
                        qualification={"qualified": True, "fit": True, "score": 95, "confidence": 0.8,
                                       "pains": ["cash" if "stock" in row.biggest_inventory_issue.lower() else "reorder"]})
                    db.add(contact)
                    db.flush()
                record(db, f"health-check-request:{row.id}", "ACCESS_REQUESTED", contact.id,
                       {"issue": row.biggest_inventory_issue, "utm_source": row.utm_source, "utm_campaign": row.utm_campaign,
                        "verified": True}, source="skubase_form", occurred_at=timestamp(row.created_at))
                enqueue(db, f"health-check:{contact.id}", "opportunity", {"contact_id": contact.id}, priority=95)
        if rows:
            remember(db, "working", "cursor:" + name, {"id": rows[-1].id})
    # Run IDs have immutable starts; completion is reconciled through a durable pending set.
    cursor = get_memory(db, "working", "cursor:sync", {"id": 0, "pending": []})
    rows = list(db.scalars(select(ShopifySyncRun).where(ShopifySyncRun.id > cursor["id"])
                          .order_by(ShopifySyncRun.id).limit(batch_size)))
    pending_ids = cursor.get("pending", [])
    pending = list(db.scalars(select(ShopifySyncRun).where(ShopifySyncRun.id.in_(pending_ids)))) if pending_ids else []
    remaining = []
    for row in rows + pending:
        user = db.scalar(select(User).where(User.shop_id == row.shop_id, User.is_admin.is_(False)))
        if not user or user.email.endswith("@skubase.io"):
            continue
        product_event(db, "IMPORT_STARTED", row.shop_id, f"import-start:{row.id}", occurred_at=timestamp(row.started_at))
        if row.status == "succeeded":
            product_event(db, "IMPORT_COMPLETED", row.shop_id, f"import-end:{row.id}", occurred_at=timestamp(row.finished_at))
        elif row.status in ("failed", "partial"):
            product_event(db, "IMPORT_FAILED", row.shop_id, f"import-error:{row.id}", data={"status": row.status}, occurred_at=timestamp(row.finished_at))
        else:
            remaining.append(row.id)
    remember(db, "working", "cursor:sync", {"id": rows[-1].id if rows else cursor["id"], "pending": remaining})
    # Mirrors attest a subscription initiation/status, not a captured payment.
    cursor = get_memory(db, "working", "cursor:subscriptions")
    since = cursor.get("at", 0)
    from datetime import datetime
    since_dt = datetime.fromtimestamp(since, timezone.utc)
    rows = list(db.scalars(select(Subscription).where((Subscription.updated_at > since_dt) |
                          ((Subscription.updated_at == since_dt) & (Subscription.id > cursor.get("id", 0))))
                          .order_by(Subscription.updated_at, Subscription.id).limit(batch_size)))
    for row in rows:
        user = db.scalar(select(User).where(User.shop_id == row.shop_id, User.is_admin.is_(False)))
        if not user or user.email.endswith("@skubase.io"):
            continue
        at = timestamp(row.updated_at)
        signature = digest([row.id, row.status, row.plan, at])
        previous = get_memory(db, "working", f"subscription-status:{row.id}")
        ended = row.status in ("canceled", "cancelled", "inactive")
        economic = get_memory(db, "economics", f"shop:{row.shop_id}")
        if economic and ended:
            remember(db, "economics", f"shop:{row.shop_id}", {**economic, "active": False, "monthly_recurring_usd": 0})
        if not ended or previous.get("status") in ("active", "trialing"):
            kind = "CANCELLATION" if ended else "SUBSCRIPTION_STARTED"
            product_event(db, kind, row.shop_id, f"subscription:{signature}",
                          data={"status": row.status, "tier": row.plan, "payment_verified": False}, occurred_at=at)
            product_event(db, "SUBSCRIPTION_TIER", row.shop_id, f"tier:{signature}", data={"tier": row.plan}, occurred_at=at)
        remember(db, "working", f"subscription-status:{row.id}", {"status": row.status})
    if rows:
        remember(db, "working", "cursor:subscriptions", {"at": timestamp(rows[-1].updated_at), "id": rows[-1].id})


def funnel_counts(db, since=0):
    rows = db.execute(select(Evidence.kind, func.count(func.distinct(Evidence.subject)))
                      .where(Evidence.kind.in_(STAGES), Evidence.occurred_at >= since)
                      .group_by(Evidence.kind)).all()
    return {kind: dict(rows).get(kind, 0) for kind in STAGES}


def bottleneck(db):
    # Only mature accounts enter onboarding denominators; pre-instrumentation imports do not prove a view.
    cutoff = time.time() - 3 * 86400
    signups = set(db.scalars(select(Evidence.subject).where(Evidence.kind == "SIGNUP", Evidence.occurred_at <= cutoff)))
    connected = set(db.scalars(select(Evidence.subject).where(Evidence.kind == "SHOPIFY_CONNECTION")))
    activated = set(db.scalars(select(Evidence.subject).where(Evidence.kind == "INVENTORY_ANALYSIS_VIEWED")))
    if len(signups) >= 5 and len(signups & connected) / len(signups) < 0.5:
        return {"stage": "shopify_connection", "observation": f"{len(signups & connected)} of {len(signups)} accounts aged at least 3 days connected a store.",
                "hypothesis": "Connection friction or trust may suppress activation.",
                "recommended_action": "Investigate the Shopify connection flow before increasing acquisition volume."}
    instrumented_since = get_memory(db, "strategic", "identity").get("started_at", time.time())
    mature_connections = set(db.scalars(select(Evidence.subject).where(Evidence.kind == "SHOPIFY_CONNECTION",
                             Evidence.occurred_at <= cutoff, Evidence.occurred_at >= instrumented_since)))
    if len(mature_connections) >= 5 and len(mature_connections & activated) / len(mature_connections) < 0.5:
        return {"stage": "activation", "observation": f"{len(mature_connections & activated)} of {len(mature_connections)} mature connected stores viewed useful analysis.",
                "hypothesis": "Import reliability or first-value friction may suppress activation; historical views may be uninstrumented.",
                "recommended_action": "Review import failures and first-analysis experience before scaling outreach."}
    return {"stage": "insufficient_evidence", "observation": "Too little mature cohort evidence to identify a reliable downstream bottleneck.",
            "hypothesis": "The initial ICP and health-check offer remain hypotheses.", "recommended_action": "Run a small, qualified organic experiment."}
