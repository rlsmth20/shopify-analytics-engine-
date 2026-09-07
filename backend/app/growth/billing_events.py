"""Called only after successful provider signature verification; never from the client."""
import time

from sqlalchemy import select

from app.db.models import Subscription, User
from .funnel import product_event
from .store import enqueue, record, remember


def stripe_event(db, event):
    if event.get("livemode") is not True:
        return
    payload = event.get("data", {}).get("object", {})
    customer = payload.get("customer")
    sub = db.scalar(select(Subscription).where(Subscription.stripe_customer_id == customer)) if customer else None
    if not sub:
        return
    user = db.scalar(select(User).where(User.shop_id == sub.shop_id, User.is_admin.is_(False)))
    if not user or user.email.endswith("@skubase.io"):
        return
    event_id, kind = event.get("id"), event.get("type")
    if not event_id:
        return
    if kind == "invoice.paid" and payload.get("paid") is True and payload.get("amount_paid", 0) > 0:
        amount = payload["amount_paid"] / 100
        currency = payload.get("currency", "").upper()
        product_event(db, "SUBSCRIPTION_PURCHASED", sub.shop_id, "stripe-payment:" + payload["id"],
            data={"provider_event_id": event_id, "receipt_id": payload["id"], "amount": amount, "currency": currency,
                  "tier": sub.plan, "payment_verified": True}, occurred_at=event.get("created", time.time()))
        # Contract MRR is derived only from recurring line pricing, never a guessed plan price.
        monthly = 0
        known = False
        for line in payload.get("lines", {}).get("data", []):
            price = line.get("price") or {}
            recurring = price.get("recurring") or {}
            if price.get("unit_amount") is None or recurring.get("interval") not in ("month", "year"):
                continue
            periods = recurring.get("interval_count", 1)
            monthly += price["unit_amount"] * line.get("quantity", 1) / 100 / periods / (12 if recurring["interval"] == "year" else 1)
            known = True
        remember(db, "economics", f"shop:{sub.shop_id}", {"monthly_recurring_usd": monthly if known and currency == "USD" else None,
                  "currency": currency, "active": True, "source_receipt": payload["id"], "observed_at": event.get("created", time.time())})
        enqueue(db, f"payment-wake:{event_id}", "observe", priority=100)
    elif kind == "customer.subscription.deleted":
        product_event(db, "CANCELLATION", sub.shop_id, "cancel:" + event_id,
                      data={"provider_event_id": event_id}, occurred_at=event.get("created", time.time()))
        remember(db, "economics", f"shop:{sub.shop_id}", {"monthly_recurring_usd": 0, "active": False, "source_event": event_id})
    db.commit()
