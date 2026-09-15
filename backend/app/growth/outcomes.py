"""Evidence-only acquisition outcomes, derived from existing durable ledgers.

Counts are observed unique merchants/stores, never manufactured funnel progression.
Period cards use event time; cohort cards follow the original first contact over time.
Missing attribution or instrumentation is represented by None, not a failed conversion.
"""
import time
import json
from collections import defaultdict
from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import load_only

from .identity import canonical_identity, owned_identity
from .models import Contact, Evidence, Experiment, FirstContact, Memory, Message, Usage
from .review_calendar import REVIEW_TIMEZONE, review_day
from .store import digest, get_memory

STAGES = ("DISCOVERED", "QUALIFIED", "CONTACT_ATTEMPTED", "CONFIRMED_CONTACT",
          "DELIVERED", "CONFIRMED_FORM_SUBMISSION", "SUBSTANTIVE_RESPONSE", "POSITIVE_RESPONSE",
          "SITE_VISIT", "ACCOUNT_CREATED", "SHOPIFY_CONNECTED", "INVENTORY_ANALYSIS_COMPLETED",
          "ACTIVATED", "PRICING_VIEWED", "TRIAL_STARTED", "CHECKOUT_STARTED", "PAID", "RETAINED")
PRODUCT = {"VISITOR": "SITE_VISIT", "SIGNUP": "ACCOUNT_CREATED", "SHOPIFY_CONNECTION": "SHOPIFY_CONNECTED",
           "INVENTORY_ANALYSIS_COMPLETED": "INVENTORY_ANALYSIS_COMPLETED", "ACTIVATED": "ACTIVATED",
           "PRICING_VIEWED": "PRICING_VIEWED", "TRIAL_STARTED": "TRIAL_STARTED",
           "CHECKOUT_STARTED": "CHECKOUT_STARTED", "SUBSCRIPTION_PURCHASED": "PAID", "RETAINED": "RETAINED"}
# Rendering/delivering an analysis and completing an import prove none of these stages.
SUBSTANTIVE = {"SUBSTANTIVE_POSITIVE", "SUBSTANTIVE_NEUTRAL", "SUBSTANTIVE_NEGATIVE", "QUESTION",
               "positive", "interested/question", "neutral", "objection", "not now", "referral", "hostile/negative"}
POSITIVE = {"SUBSTANTIVE_POSITIVE", "positive", "interested/question"}
NEGATIVE = {"SUBSTANTIVE_NEGATIVE", "objection", "hostile/negative"}
CHANNELS = ("email", "contact_form", "reddit", "shopify_community", "other_forums",
            "organic_search", "free_tools", "inbound", "other")
RANK = ("PAID", "CHECKOUT_STARTED", "TRIAL_STARTED", "SHOPIFY_CONNECTED", "INVENTORY_ANALYSIS_COMPLETED",
        "POSITIVE_RESPONSE", "SUBSTANTIVE_RESPONSE", "ACCOUNT_CREATED", "SITE_VISIT")


def _channel(value):
    return value if value in CHANNELS else "other_forums" if value == "public_community" else "other"


def _ratio(n, d):
    return n / d if n is not None and d else None


def _dimensions(row):
    c = row.cohort or {}
    characteristics = c.get("characteristics") or {}
    qualification = c.get("qualification") or {}
    return {"experiment_id": row.experiment_id, "channel": _channel(row.channel),
            "source": c.get("source"), "icp_segment": c.get("icp"), "industry": c.get("industry", characteristics.get("industry")),
            "shopify_confidence": c.get("shopify_confidence", qualification.get("shopify_confidence")),
            "message": c.get("message_variant", c.get("message_version")), "offer": c.get("offer"),
            "positioning": c.get("positioning"), "cta": c.get("cta"), "contact_method": c.get("contact_method", row.channel),
            "qualification_policy": c.get("qualification_policy", "legacy")}


def _diagnosis(block):
    f, mature = block["funnel"], block["mature_contacts"]
    if (mature >= 75 and f["SUBSTANTIVE_RESPONSE"] == 0
            and block["measurement"].get("response_observation_available")
            and not any(f.get(stage) for stage in ("PAID", "TRIAL_STARTED", "SHOPIFY_CONNECTED", "POSITIVE_RESPONSE"))):
        return {"stage": "contact_to_response", "observation": f"{mature} contacts aged at least 7 days have no recorded substantive response.",
                "recommended_action": "Verify delivery and reply capture, then change the offer, target, message or channel before scaling this approach."}
    for before, after, stage, action in (
        ("PAID", "RETAINED", "retention", "Investigate ongoing value and expectation gaps."),
        ("ACTIVATED", "PAID", "payment", "Investigate demonstrated value, pricing and purchase CTA."),
        ("SHOPIFY_CONNECTED", "ACTIVATED", "activation", "Investigate import/sync, time to value and analysis UX."),
        ("ACCOUNT_CREATED", "SHOPIFY_CONNECTED", "shopify_connection", "Investigate onboarding, Shopify authorization and trust."),
        ("POSITIVE_RESPONSE", "ACCOUNT_CREATED", "signup", "Investigate offer, landing page and signup friction."),
        ("SUBSTANTIVE_RESPONSE", "POSITIVE_RESPONSE", "positive_response", "Test problem selection, value proposition, ICP and CTA.")):
        # A minimum response window prevents same-day replies from creating product diagnoses.
        if mature >= 25 and f[before] is not None and f[before] >= 5 and f[after] is not None and f[after] / f[before] < .2:
            return {"stage": stage, "observation": f"Observed {f[before]} {before.lower()} and {f[after]} {after.lower()}; investigate cohort timing before a causal conclusion.", "recommended_action": action}
    return {"stage": "insufficient_evidence", "observation": "Contact activity alone does not validate demand; missing attribution remains unknown.",
            "recommended_action": "Continue controlled offer/channel cohorts and prioritize genuine replies; review at 25, 50 and 100 confirmed contacts."}


def snapshot(db, now=None):
    """Read-only full-history projection. No writes, models, inferred backfills or sends."""
    now = time.time() if now is None else now
    aliases = {m.value.get("identity"): m.value.get("merchant_key") for m in db.scalars(
        select(Memory).where(Memory.namespace == "merchant_alias"))}
    controlled = get_memory(db, "strategic", "controlled_email_tests").get("accounts", {})
    contacts = {c.id: c for c in db.scalars(select(Contact).where(Contact.created_at <= now))
                if not owned_identity(c.identity) and canonical_identity(c.identity) not in controlled
                and (c.email or "").lower() not in controlled}
    def merchant(cid):
        c = contacts[cid]
        return aliases.get(canonical_identity(c.identity)) or (f"shop:{c.shop_id}" if c.shop_id is not None else cid)
    rows = [r for r in db.scalars(select(FirstContact).where(FirstContact.reserved_at <= now)
            .order_by(FirstContact.sent_at, FirstContact.reserved_at)) if r.contact_id in contacts]
    messages = list(db.scalars(select(Message).where(Message.contact_id.in_(list(contacts)), Message.created_at <= now)
        .options(load_only(Message.id, Message.contact_id, Message.experiment_id, Message.direction, Message.status,
                           Message.provider_id, Message.reply_to_id, Message.classification, Message.created_at, Message.sent_at)))) if contacts else []
    by_message = {m.id: m for m in messages}
    by_merchant_message = defaultdict(list)
    for m in messages:
        by_merchant_message[merchant(m.contact_id)].append(m)
    kinds = tuple(PRODUCT) + ("REPLY_RECEIVED", "ACCESS_REQUESTED", "FIRST_CONTACT_RESULT",
        "PROVIDER_EVENT", "HISTORICAL_PURCHASE_INTENT", "PURCHASE_INTENT_EVIDENCE", "CONTACT_ATTEMPTED", "CANCELLATION", "IDENTITY_LINK", "OUTREACH_SUPPRESSED")
    evidence = list(db.scalars(select(Evidence).where(Evidence.kind.in_(kinds), Evidence.occurred_at <= now)))
    visitor_shops = defaultdict(set)
    for e in evidence:
        if e.kind == "IDENTITY_LINK" and e.source == "authenticated_session" and e.subject.startswith("visitor:") and type(e.data.get("shop_id")) is int:
            visitor_shops[e.subject].add(e.data["shop_id"])
    visitor_links = {visitor: f"shop:{next(iter(shops))}" for visitor, shops in visitor_shops.items() if len(shops) == 1}
    by_subject, provider_events = defaultdict(list), defaultdict(list)
    for e in evidence:
        key = merchant(e.subject) if e.subject in contacts else visitor_links.get(e.subject, e.subject)
        by_subject[key].append(e)
        if e.kind == "OUTREACH_SUPPRESSED":
            for cid in e.data.get("contact_ids", []):
                if cid in contacts and merchant(cid) != key:
                    by_subject[merchant(cid)].append(e)
        if e.kind == "PROVIDER_EVENT" and e.source == "resend_signed_webhook":
            provider_events[(e.data.get("data") or {}).get("email_id")].append(e)
    economics = {m.key: m.value for m in db.scalars(select(Memory).where(Memory.namespace == "economics"))}
    usage = list(db.scalars(select(Usage).where(Usage.created_at <= now, Usage.category.in_(["model", "api", "codex_subscription"]),
                                               Usage.task != "acquisition_deliverability", ~Usage.task.startswith("warmup"))))
    coverage = get_memory(db, "strategic", "outcome_instrumentation")
    complete_stages = set(coverage.get("complete_stages", []))
    safety = get_memory(db, "working", "browser_safety_check")
    monitor = db.get(Evidence, safety.get("evidence_id")) if safety.get("evidence_id") else None
    monitored = bool(monitor and monitor.kind == "CHANNEL_MONITOR" and monitor.source == "authenticated_browser_executor"
                     and now - 3600 <= monitor.occurred_at <= now and monitor.data.get("mailbox") == "info@skubase.io"
                     and monitor.data.get("requires_attention") is False)
    shop_ids_by_merchant = defaultdict(set)
    for c in contacts.values():
        if c.shop_id is not None:
            shop_ids_by_merchant[merchant(c.id)].add(c.shop_id)
    records = []
    confirmed_merchants = set()
    for row in rows:
        mid = merchant(row.contact_id)
        confirmed = row.status == "sent" and row.sent_at is not None and row.sent_at <= now
        # Historical linked identities must not become multiple acquired customers/first contacts.
        if confirmed and mid in confirmed_merchants:
            continue
        if confirmed:
            confirmed_merchants.add(mid)
        record = {"row": row, "merchant": mid, "dimensions": _dimensions(row), "stages": defaultdict(list),
                  "negative": [], "unsubscribed": [], "bounced": [], "evidence_ids": set(), "paid_shops": set()}
        stages = record["stages"]
        if confirmed:
            stages["CONFIRMED_CONTACT"].append((mid, row.sent_at))
            stages["CONTACT_ATTEMPTED"].append((mid, row.sent_at))
            if row.channel == "contact_form":
                stages["CONFIRMED_FORM_SUBMISSION"].append((mid, row.sent_at))
        events = by_subject[mid]
        for e in events:
            if e.kind == "CONTACT_ATTEMPTED" or (e.kind == "FIRST_CONTACT_RESULT" and e.data.get("outcome") in {"sent", "uncertain", "failed"}):
                if e.data.get("reservation_id") in (None, row.id):
                    stages["CONTACT_ATTEMPTED"].append((mid, e.occurred_at))
                    record["evidence_ids"].add(e.id)
        if not confirmed:
            records.append(record)
            continue
        related = by_merchant_message[mid]
        def matches_message(m):
            if m.experiment_id not in (None, row.experiment_id):
                return False
            if m.reply_to_id:
                parent = by_message.get(m.reply_to_id)
                return bool(parent and parent.direction == "out" and parent.experiment_id == row.experiment_id
                            and merchant(parent.contact_id) == mid)
            return m.experiment_id == row.experiment_id
        incoming = [m for m in related if m.direction == "in" and row.sent_at <= m.created_at and matches_message(m)]
        classifications = [(m.classification, m.created_at) for m in incoming]
        incoming_ids = {m.id for m in incoming}
        for e in events:
            if e.occurred_at < row.sent_at or e.data.get("experiment_id") not in (None, row.experiment_id):
                continue
            if e.kind == "REPLY_RECEIVED" and e.data.get("message_id") not in by_message and e.data.get("experiment_id") == row.experiment_id:
                classifications.append((e.data.get("classification"), e.occurred_at))
                record["evidence_ids"].add(e.id)
            if e.kind == "REPLY_RECEIVED" and e.data.get("message_id") in incoming_ids:
                record["evidence_ids"].add(e.id)
            if e.kind == "ACCESS_REQUESTED" and e.data.get("verified") is True:
                classifications.append(("SUBSTANTIVE_POSITIVE", e.occurred_at))
                record["evidence_ids"].add(e.id)
            if e.kind == "OUTREACH_SUPPRESSED":
                destination = {"bounce": "bounced", "unsubscribe": "unsubscribed", "declined": "negative", "complaint": "negative"}.get(e.data.get("reason"))
                if destination and (destination != "bounced" or row.channel == "email"):
                    record[destination].append((mid, e.occurred_at))
                    record["evidence_ids"].add(e.id)
        for classification, at in classifications:
            if classification in SUBSTANTIVE:
                stages["SUBSTANTIVE_RESPONSE"].append((mid, at))
            if classification in POSITIVE:
                stages["POSITIVE_RESPONSE"].append((mid, at))
            if classification in NEGATIVE:
                record["negative"].append((mid, at))
            if classification in {"UNSUBSCRIBE", "unsubscribe"}:
                record["unsubscribed"].append((mid, at))
            if row.channel == "email" and classification in {"DELIVERY_FAILURE", "bounce"}:
                record["bounced"].append((mid, at))
        if row.channel == "email":
            for m in related:
                if (m.direction != "out" or m.reply_to_id or m.experiment_id != row.experiment_id
                        or m.sent_at is None or abs(m.sent_at - row.sent_at) > 600):
                    continue
                # A later replied status is not delivery evidence. Signed provider events retain delivery history.
                if m.status == "delivered":
                    stages["DELIVERED"].append((mid, m.sent_at))
                if m.status == "bounced":
                    record["bounced"].append((mid, m.sent_at))
                for e in provider_events[m.provider_id]:
                    if e.occurred_at < row.sent_at:
                        continue
                    if e.data.get("type") == "email.delivered":
                        stages["DELIVERED"].append((mid, e.occurred_at))
                    if e.data.get("type") == "email.bounced":
                        record["bounced"].append((mid, e.occurred_at))
                    record["evidence_ids"].add(e.id)
        shop_ids = shop_ids_by_merchant[mid]
        product_events = events + [e for shop in shop_ids for e in by_subject[f"shop:{shop}"] if mid != f"shop:{shop}"]
        for e in product_events:
            if e.kind not in PRODUCT or e.occurred_at < row.sent_at or e.data.get("experiment_id") not in (None, row.experiment_id):
                continue
            linked_client = (e.kind in {"VISITOR", "PRICING_VIEWED"} and e.source == "first_party_browser"
                             and e.subject in visitor_links)
            if e.data.get("verified") is not True and not linked_client:
                continue
            if e.kind == "SUBSCRIPTION_PURCHASED" and e.data.get("payment_verified") is not True:
                continue
            if e.kind in {"SIGNUP", "SHOPIFY_CONNECTION", "SUBSCRIPTION_PURCHASED", "TRIAL_STARTED"} and any(
                prior.kind == e.kind and prior.subject == e.subject and prior.data.get("verified") is True
                and prior.occurred_at < row.sent_at for prior in product_events):
                continue
            outcome_id = visitor_links.get(e.subject, e.subject if e.subject.startswith("shop:") else mid)
            stages[PRODUCT[e.kind]].append((outcome_id, e.occurred_at))
            record["evidence_ids"].add(e.id)
            if e.kind == "SUBSCRIPTION_PURCHASED":
                record["paid_shops"].add(outcome_id)
        records.append(record)

    # Inbound/organic demand is acquisition evidence even when nobody was sent
    # a first-contact message. These in-memory rows never touch the send ledger.
    experiments = list(db.scalars(select(Experiment)))
    campaign_map = {label: exp for exp in experiments for label in (exp.id, exp.key)}
    requests = sorted((e for e in evidence if e.kind == "ACCESS_REQUESTED" and e.data.get("verified") is True
                       and e.subject in contacts), key=lambda e: (e.occurred_at, e.id))
    demand_seen = set(confirmed_merchants)
    for request in requests:
        mid = merchant(request.subject)
        if mid in demand_seen:
            continue
        demand_seen.add(mid)
        exp = campaign_map.get(request.data.get("utm_campaign"))
        if exp and request.occurred_at < exp.started_at:
            exp = None
        spec = exp.specification if exp else {}
        channel = spec.get("channel") if spec.get("channel") in {"organic_search", "free_tools"} else "inbound"
        row = SimpleNamespace(contact_id=request.subject, status="observed", sent_at=None, reserved_at=request.occurred_at)
        r = {"row": row, "merchant": mid, "dimensions": {"experiment_id": exp.id if exp else None, "channel": channel,
             "source": request.source, "icp_segment": spec.get("target_customer"), "industry": None, "shopify_confidence": None,
             "message": spec.get("message_variant"), "offer": spec.get("offer", "requested_inventory_health_check"),
             "positioning": spec.get("positioning"), "cta": spec.get("cta"), "contact_method": "inbound_request",
             "qualification_policy": "explicit_merchant_request"}, "stages": defaultdict(list), "negative": [], "unsubscribed": [],
             "bounced": [], "evidence_ids": {request.id}, "paid_shops": set()}
        for stage in ("SUBSTANTIVE_RESPONSE", "POSITIVE_RESPONSE"):
            r["stages"][stage].append((mid, request.occurred_at))
        shop_ids = shop_ids_by_merchant[mid]
        subsequent = by_subject[mid] + [e for shop in shop_ids for e in by_subject[f"shop:{shop}"] if mid != f"shop:{shop}"]
        for e in subsequent:
            if e.kind not in PRODUCT or e.occurred_at < request.occurred_at:
                continue
            linked_client = e.kind in {"VISITOR", "PRICING_VIEWED"} and e.source == "first_party_browser" and e.subject in visitor_links
            if e.data.get("verified") is not True and not linked_client:
                continue
            if e.kind == "SUBSCRIPTION_PURCHASED" and e.data.get("payment_verified") is not True:
                continue
            if any(prior.kind == e.kind and prior.subject == e.subject and prior.data.get("verified") is True
                   and prior.occurred_at < request.occurred_at for prior in subsequent) and e.kind in {"SIGNUP", "SHOPIFY_CONNECTION", "SUBSCRIPTION_PURCHASED", "TRIAL_STARTED"}:
                continue
            outcome_id = visitor_links.get(e.subject, e.subject if e.subject.startswith("shop:") else mid)
            r["stages"][PRODUCT[e.kind]].append((outcome_id, e.occurred_at))
            r["evidence_ids"].add(e.id)
            if e.kind == "SUBSCRIPTION_PURCHASED":
                r["paid_shops"].add(outcome_id)
        records.append(r)

    def block(items, since=0, include_discovery=False, include_cost=False):
        def ids(values):
            return {key for key, at in values if since <= at <= now}
        observed = {stage: len(ids(v for r in items for v in r["stages"][stage])) for stage in STAGES}
        f = dict(observed)
        linked_population = bool(items) and all(shop_ids_by_merchant[r["merchant"]] for r in items)
        if not f["DELIVERED"]:
            f["DELIVERED"] = None
        for stage in PRODUCT.values():
            if not f[stage] and (stage not in complete_stages or not linked_population):
                f[stage] = None
        f["DISCOVERED"] = len({merchant(c.id) for c in contacts.values() if c.created_at >= since}) if include_discovery else None
        # Current qualification has no reliable historical transition timestamp.
        f["QUALIFIED"] = None
        confirmed = [r for r in items if r["stages"]["CONFIRMED_CONTACT"] and r["row"].sent_at >= since]
        counts = defaultdict(int)
        for r in confirmed:
            counts[r["dimensions"]["channel"]] += 1
        unresolved = [r for r in items if r["row"].reserved_at >= since and r["row"].status in {"reserved", "uncertain"}]
        uncertain = sum(r["row"].status == "uncertain" or r["row"].reserved_at + 600 <= now for r in unresolved)
        bounced = len(ids(v for r in items for v in r["bounced"]))
        negative = len(ids(v for r in items for v in r["negative"]))
        unsubscribed = len(ids(v for r in items for v in r["unsubscribed"]))
        paid_shops = ids(v for r in items for v in r["stages"]["PAID"])
        values = [economics.get(shop) for shop in paid_shops]
        mrr = (sum(v.get("monthly_recurring_usd", 0) if v.get("active") else 0 for v in values)
               if values and all(v and v.get("monthly_recurring_usd") is not None for v in values) else None)
        window_usage = [u for u in usage if u.created_at >= since] if include_cost else []
        spend = sum(u.estimated_usd for u in window_usage) if window_usage and all(u.estimated_usd is not None for u in window_usage) else None
        metrics = {"paying_customers": f["PAID"], "mrr": mrr, "trials": f["TRIAL_STARTED"], "shopify_connections": f["SHOPIFY_CONNECTED"],
                   "positive_responses": f["POSITIVE_RESPONSE"], "substantive_responses": f["SUBSTANTIVE_RESPONSE"], "confirmed_contacts": f["CONFIRMED_CONTACT"]}
        accounting = {"confirmed_contacts": f["CONFIRMED_CONTACT"], "uncertain_submissions": uncertain,
            "pending_reservations": len(unresolved) - uncertain,
            "failed_attempts": sum(r["row"].status == "failed" and r["row"].reserved_at >= since for r in items),
            "delivered_emails": f["DELIVERED"],
            "bounced_emails": bounced, "email_delivery_unknown": max(0, counts["email"] - observed["DELIVERED"] - bounced),
            "form_submissions": counts["contact_form"], "email_contacts": counts["email"], "reddit_contacts": counts["reddit"],
            "community_contacts": counts["shopify_community"], "other_contacts": sum(counts[c] for c in CHANNELS if c not in {"email", "contact_form", "reddit", "shopify_community"}),
            "negative_responses": negative, "unsubscribes": unsubscribed}
        rates = {"contact_to_" + name: _ratio(f[stage], f["CONFIRMED_CONTACT"]) for name, stage in (
            ("substantive_response", "SUBSTANTIVE_RESPONSE"), ("positive_response", "POSITIVE_RESPONSE"), ("site_visit", "SITE_VISIT"),
            ("signup", "ACCOUNT_CREATED"), ("shopify_connection", "SHOPIFY_CONNECTED"), ("activation", "ACTIVATED"), ("paid", "PAID"))}
        rates.update(positive_response_to_connection=_ratio(f["SHOPIFY_CONNECTED"], f["POSITIVE_RESPONSE"]),
                     shopify_connection_to_paid=_ratio(f["PAID"], f["SHOPIFY_CONNECTED"]),
                     bounce_rate=_ratio(bounced, counts["email"]), unsubscribe_rate=_ratio(unsubscribed, f["CONFIRMED_CONTACT"]),
                     negative_response_rate=_ratio(negative, f["CONFIRMED_CONTACT"]))
        # Period cards are activity timelines; yesterday's prospect may reply
        # today. Their conversion denominator is not today's new contacts.
        if since:
            rates = {key: None for key in rates}
        else:
            stage_merchants = {stage: {r["merchant"] for r in items if r["stages"][stage]} for stage in STAGES}
            for name, stage in (("substantive_response", "SUBSTANTIVE_RESPONSE"), ("positive_response", "POSITIVE_RESPONSE"),
                ("site_visit", "SITE_VISIT"), ("signup", "ACCOUNT_CREATED"), ("shopify_connection", "SHOPIFY_CONNECTED"),
                ("activation", "ACTIVATED"), ("paid", "PAID")):
                rates["contact_to_" + name] = (_ratio(len(stage_merchants["CONFIRMED_CONTACT"] & stage_merchants[stage]), len(stage_merchants["CONFIRMED_CONTACT"])) if f[stage] is not None else None)
            rates["positive_response_to_connection"] = (_ratio(len(stage_merchants["POSITIVE_RESPONSE"] & stage_merchants["SHOPIFY_CONNECTED"]), len(stage_merchants["POSITIVE_RESPONSE"])) if f["SHOPIFY_CONNECTED"] is not None else None)
            rates["shopify_connection_to_paid"] = (_ratio(len(stage_merchants["SHOPIFY_CONNECTED"] & stage_merchants["PAID"]), len(stage_merchants["SHOPIFY_CONNECTED"])) if f["PAID"] is not None else None)
        costs = {"model_api_cost": spend, "known_model_api_cost": sum(u.estimated_usd or 0 for u in window_usage) if include_cost else None,
                 "unknown_cost_records": sum(u.estimated_usd is None for u in window_usage) if include_cost else None,
                 "cac": None, "arpu": _ratio(mrr, f["PAID"]), "churn": None}
        for key, denominator in (("discovered_merchant", f["DISCOVERED"]), ("confirmed_contact", f["CONFIRMED_CONTACT"]),
            ("substantive_response", f["SUBSTANTIVE_RESPONSE"]), ("positive_response", f["POSITIVE_RESPONSE"]),
            ("connected_shopify_store", f["SHOPIFY_CONNECTED"]), ("customer", f["PAID"])):
            costs["cost_per_" + key] = _ratio(spend, denominator)
        mature = sum(r["row"].sent_at <= now - 7 * 86400 for r in confirmed)
        return {"metrics": metrics, "funnel": f, "observed_counts": observed, "accounting": accounting, "rates": rates, "costs": costs,
                "mature_contacts": mature, "evidence_ids": sorted({e for r in items for e in r["evidence_ids"]})[-100:],
                "measurement": {"response_basis": "recorded attributed merchant responses", "missing_product_evidence": "UNKNOWN",
                                "rate_basis": "event-period rates unavailable; use lifetime cohort rates" if since else "original cohort and observed subsequent results",
                                "response_observation_available": monitored and all(r["dimensions"]["channel"] in {"email", "contact_form", "reddit"} for r in items),
                                "product_linkage_complete": all(contacts[r["row"].contact_id].shop_id is not None for r in confirmed) if confirmed else False}}

    day = review_day(now)
    week = (datetime.fromtimestamp(day.start, REVIEW_TIMEZONE) - timedelta(days=6)).timestamp()
    periods = {name: block(records, since, True, True) for name, since in (("today", day.start), ("last_7_days", week), ("all_time", 0))}
    groups = defaultdict(list)
    for r in records:
        # Merchant URLs and confidence observations belong to the receipt, not
        # the experimental grouping key: otherwise every contact is a cohort.
        group_dimensions = {k: v for k, v in r["dimensions"].items() if k not in {"source", "shopify_confidence"}}
        groups[digest(group_dimensions)].append(r)
    cohorts = []
    for key, items in groups.items():
        value = {"id": key, **items[0]["dimensions"], **block(items)}
        value["source"] = None
        value["shopify_confidence"] = None
        value["sources"] = list(dict.fromkeys(r["dimensions"]["source"] for r in items if r["dimensions"]["source"]))[:10]
        n = value["metrics"]["confirmed_contacts"]
        value["maturity"] = "STRONGER_DECISION" if n >= 100 else "REVIEW" if n >= 50 else "EARLY_SIGNAL" if n >= 25 else "ACCUMULATING"
        value["bottleneck"] = _diagnosis(value)
        cohorts.append(value)
    channels = [{"channel": c, **block([r for r in records if r["dimensions"]["channel"] == c])} for c in CHANNELS]
    def strongest(items):
        eligible = [c for c in items if any((c["funnel"].get(stage) or 0) > 0 for stage in RANK)]
        return max(eligible, key=lambda c: tuple(c["funnel"].get(stage) or 0 for stage in RANK), default=None)
    winner = strongest(cohorts)
    channel_winner = strongest(channels)
    best = {"channel": channel_winner["channel"] if channel_winner else None,
            **{key: winner.get(key) if winner else None for key in ("icp_segment", "offer", "message")}}
    total = periods["all_time"]
    n = total["metrics"]["confirmed_contacts"]
    target = (n // 100 + 1) * 100
    historical = [e for e in evidence if e.kind in {"HISTORICAL_PURCHASE_INTENT", "PURCHASE_INTENT_EVIDENCE"}]
    signal = ({"kind": next(stage for stage in RANK if winner["funnel"].get(stage)), "cohort_id": winner["id"],
               "evidence_ids": winner["evidence_ids"], "interpretation": "Observed attributed result, not proof of a repeatable acquisition path."} if winner else
              {"kind": "PURCHASE_INTENT_EVIDENCE", "sample_size": 1, "evidence_ids": [e.id for e in historical],
               "interpretation": "One historical owner-reported Reddit membership-intent observation; not a paid customer."} if historical else
              {"kind": "UNKNOWN", "interpretation": "No verified downstream acquisition result recorded."})
    active = list(db.scalars(select(Experiment).where(Experiment.status == "active", Experiment.stop_at > now).order_by(Experiment.started_at.desc())))
    return {"generated_at": now, "north_star": "PAYING_CUSTOMERS_AND_MRR", "day_timezone": "America/Los_Angeles",
            "periods": periods, "cohorts": cohorts, "channels": channels, "best": best, "best_signal": signal,
            "bottleneck": _diagnosis(total), "current_experiment": active[0].id if active else None,
            "next_decision_point": {"confirmed_contacts": n, "target": target, "remaining": max(0, target - n),
                "guidance": "25 early signal / 50 review / 100 stronger decision per cohort; assess response time and earlier strong negative or positive evidence."},
            "limitations": ["Periods count events occurring in the window; cohort rates use original first contacts and subsequent observed outcomes.",
                "Missing conversion linkage/instrumentation is UNKNOWN; observed_counts exposes only recorded evidence, not measured absence.",
                "Current MRR is the known active recurring value of stores with acquisition-attributed payments in the selected window, not revenue earned in that window.",
                "Organic/free-tool attribution requires a verified inventory request with an exact experiment campaign tag. Other verified requests are inbound; unlinked tool traffic never becomes a merchant or customer.",
                "No delivery inferred from send, no analysis/activation inferred from import or rendering, and no payment inferred from subscription initiation.",
                "Best means strongest observed downstream signal, not a statistically established winner. Retention, CAC and churn require further evidence."]}


def review_context(db, now=None):
    """Complete checkpoint contract; callers cache review work instead of rereading raw history."""
    s = snapshot(db, now)
    return {"north_star": s["north_star"], **{k: s["periods"]["all_time"][k] for k in ("metrics", "funnel", "accounting", "rates", "costs")},
            "cohorts": [{"id": c["id"], "experiment_id": c["experiment_id"], "channel": c["channel"],
                "confirmed_contacts": c["metrics"]["confirmed_contacts"], "mature_contacts": c["mature_contacts"],
                "substantive_responses": c["metrics"]["substantive_responses"], "positive_responses": c["metrics"]["positive_responses"],
                "paid": c["metrics"]["paying_customers"], "shopify_connected": c["metrics"]["shopify_connections"],
                "bounced": c["accounting"]["bounced_emails"], "unsubscribed": c["accounting"]["unsubscribes"],
                "negative_responses": c["accounting"]["negative_responses"], "evidence_ids": c["evidence_ids"][-12:],
                "maturity": c["maturity"], "measurement": c["measurement"],
                "response_observation_available": c["measurement"]["response_observation_available"]} for c in s["cohorts"]],
            **{k: s[k] for k in ("bottleneck", "next_decision_point", "best", "best_signal", "current_experiment")}}


def decision_context(db, now=None):
    """Bounded planner context: downstream signals dominate, never fill context with history."""
    value = review_context(db, now)
    candidates = sorted(value.pop("cohorts"), key=lambda c: (c["paid"] or 0, c["positive_responses"], c["mature_contacts"]), reverse=True)
    for key in ("funnel", "accounting", "rates", "costs"):
        value.pop(key, None)
    value["best"] = {k: str(v)[:160] if v is not None else None for k, v in value["best"].items()}
    value["best_signal"] = {k: v[:12] if k == "evidence_ids" else str(v)[:400] if isinstance(v, str) else v
                            for k, v in value["best_signal"].items()}
    value["cohorts"] = []
    for c in candidates:
        compact = {k: c[k] for k in ("id", "experiment_id", "confirmed_contacts", "mature_contacts", "substantive_responses", "positive_responses", "paid", "maturity")}
        if len(json.dumps({**value, "cohorts": value["cohorts"] + [compact]}, default=str)) > 3900:
            break
        value["cohorts"].append(compact)
    value["cohorts_omitted"] = len(candidates) - len(value["cohorts"])
    return value
