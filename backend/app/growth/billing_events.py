"""Called only after successful provider signature verification; never from the client."""
import time

from sqlalchemy import select

from app.db.models import Subscription, User
from .funnel import product_event
from .models import Evidence
from .store import enqueue, get_memory, remember


def stripe_event(db, event):
    if event.get("livemode") is not True:
        return
    event_id, kind = event.get("id"), event.get("type")
    if not event_id or kind not in {"invoice.paid", "customer.subscription.deleted"}:
        return
    payload = event.get("data", {}).get("object", {})
    customer = payload.get("customer")
    sub = db.scalar(select(Subscription).where(Subscription.stripe_customer_id == customer).with_for_update()) if customer else None
    if not sub:
        return
    user = db.scalar(select(User).where(User.shop_id == sub.shop_id, User.is_admin.is_(False)))
    if not user or user.email.lower().endswith("@skubase.io"):
        return
    # Keep historical receipts, but never apply another subscription's payment
    # or cancellation to the current contract (including a Shopify replacement).
    subscription_id = (payload.get("subscription") or
                       ((payload.get("parent") or {}).get("subscription_details") or {}).get("subscription"))
    if kind == "customer.subscription.deleted":
        subscription_id = payload.get("id")
    current_contract = bool(subscription_id and subscription_id == sub.stripe_subscription_id)
    if kind == "invoice.paid" and subscription_id and payload.get("paid") is True and payload.get("amount_paid", 0) > 0:
        receipt_id = payload["id"]
        receipt_key = "stripe-payment:" + receipt_id
        if db.scalar(select(Evidence.id).where(Evidence.key == "funnel:" + receipt_key)):
            return
        amount = payload["amount_paid"] / 100
        currency = payload.get("currency", "").upper()
        receipt = product_event(db, "SUBSCRIPTION_PURCHASED", sub.shop_id, receipt_key,
            data={"provider_event_id": event_id, "receipt_id": receipt_id, "amount": amount, "currency": currency,
                  "subscription_id": subscription_id, "tier": sub.plan if current_contract else None,
                  "payment_verified": True}, occurred_at=event.get("created", time.time()))
        if receipt is None:
            return
        # Contract MRR is derived only from recurring line pricing, never a guessed plan price.
        monthly = 0
        known = False
        for line in payload.get("lines", {}).get("data", []):
            price = line.get("price") or {}
            recurring = price.get("recurring") or {}
            if price.get("unit_amount") is None or recurring.get("interval") not in ("month", "year"):
                continue
            periods = recurring.get("interval_count", 1)
            if not isinstance(periods, (int, float)) or periods <= 0:
                continue
            monthly += price["unit_amount"] * line.get("quantity", 1) / 100 / periods / (12 if recurring["interval"] == "year" else 1)
            known = True
        old = get_memory(db, "economics", f"shop:{sub.shop_id}")
        period_end = payload.get("period_end")
        prior_period_end = old.get("billing_period_end")
        # Billing periods describe the receipt, unlike event arrival time. Do not
        # let a late historical invoice replace a later observed contract price.
        older_period = (isinstance(period_end, (int, float)) and isinstance(prior_period_end, (int, float))
                        and period_end < prior_period_end and old.get("subscription_id") == subscription_id)
        if current_contract and sub.status in {"active", "trialing"} and not older_period:
            recurring_usd = monthly if known and currency == "USD" else None
            if (old.get("subscription_id") == subscription_id and old.get("source_receipt") != receipt_id
                    and (period_end is None or prior_period_end is None or period_end == prior_period_end)
                    and old.get("monthly_recurring_usd") != recurring_usd):
                recurring_usd = None  # Conflicting same-period receipts are not an ordering signal.
            remember(db, "economics", f"shop:{sub.shop_id}", {"monthly_recurring_usd": recurring_usd,
                      "currency": currency, "active": True, "source_receipt": receipt_id,
                      "subscription_id": subscription_id, "billing_period_end": period_end,
                      "observed_at": event.get("created", time.time())})
        elif current_contract and sub.status in {"canceled", "incomplete_expired"} and old.get("active"):
            # The subscription commit can precede a retried cancellation projection.
            # A payment arriving in that gap must not leave an obsolete active MRR.
            remember(db, "economics", f"shop:{sub.shop_id}", {**old, "active": False,
                      "monthly_recurring_usd": 0, "subscription_id": subscription_id,
                      "subscription_status": sub.status})
        enqueue(db, f"payment-wake:{receipt_id}", "observe", priority=100)
    elif kind == "customer.subscription.deleted":
        # Honor receipt keys written by the earlier handler during deployment.
        receipt = db.scalar(select(Evidence).where(Evidence.key == "funnel:cancel:" + event_id))
        if receipt is None:
            receipt = product_event(db, "CANCELLATION", sub.shop_id, "stripe-cancel:" + payload["id"],
                          data={"provider_event_id": event_id, "subscription_id": subscription_id,
                                "current_contract": current_contract},
                          occurred_at=event.get("created", time.time()))
        if receipt is not None and current_contract:
            remember(db, "economics", f"shop:{sub.shop_id}", {"monthly_recurring_usd": 0, "active": False,
                      "source_event": receipt.data["provider_event_id"], "subscription_id": subscription_id,
                      "observed_at": receipt.occurred_at})
    db.commit()
