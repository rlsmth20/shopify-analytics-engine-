"""Bounded persistent operator. The planner always considers the next useful action."""
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone

from sqlalchemy import func, select, update

from . import discovery, funnel, learning, messaging
from .service_replies import answer_request, current_request
from .model_router import call_model
from .models import Contact, Evidence, Experiment, Memory, Message, SkillRevision, Usage, Work
from .policy import GrowthError, Policy, REPLY_CLASSES
from .review_calendar import completed_review, review_day
from .skills import active_skill, bootstrap_skills, propose_revision
from .store import claim, context, digest, enqueue, finish, get_memory, heartbeat, record, remember, require_lease

logger = logging.getLogger(__name__)


def bootstrap(factory):
    with factory() as db:
        if not get_memory(db, "strategic", "identity"):
            remember(db, "strategic", "identity", {"name": "Skubase Growth", "mission": "Acquire 10 qualified Skubase users organically", "advertising_budget_usd": 0,
                "qualified_definition": "Distinct verified connected merchants, activated stores or paying customers; intent leads are separate.",
                "started_at": time.time()})
            remember(db, "strategic", "strategy", {"icp": "Hypothesis: Shopify owner/operators with physical inventory, 75–1,000 products, apparel or beauty; verify purchasing responsibility.",
                "positioning": "Free Shopify Inventory Health Check", "priorities": ["merchant inventory pain", "helpful qualified conversations", "store connection and useful analysis"],
                "biggest_uncertainty": "Which merchant segment obtains enough value to pay?", "cash_allocation": 0.5,
                "next_action": "Find recent merchant inventory questions and verify legitimate contact paths."})
            remember(db, "working", "budget", {"spent": "usage ledger"})
            remember(db, "working", "dispatch_lock", {})
            record(db, "historical-reddit-intent", "HISTORICAL_PURCHASE_INTENT", "historical:anonymous-reddit-merchant",
                   {"observation": "Owner reports one Reddit visitor attempted to obtain a Skubase membership.", "sample_size": 1,
                    "payment_verified": False, "date": None, "identity": None, "interpretation": "One purchase-intent observation; not a customer count."}, source="owner_brief")
            remember(db, "channel", "shopify_community", {"read": "public endpoints only", "post": "review required", "affiliation": "Skubase", "restriction_bypass": False})
            remember(db, "channel", "reddit", {"read": "public owner-supplied evidence or approved integration", "post": "review subreddit rules and identity first"})
        bootstrap_skills(db)
        learning.ensure_experiment(db)
        db.commit()


def schedule(factory):
    now = time.time()
    with factory() as db:
        if get_memory(db, "working", "control").get("paused"):
            return
        enqueue(db, f"observe:{int(now // 300)}", "observe", priority=75)
        if os.getenv("GROWTH_INBOUND_ENABLED") == "true":
            enqueue(db, f"inbox:{int(now // 300)}", "inbox", priority=100)
        window = review_day(now)
        review_key = "review:" + window.key
        completed = completed_review(db, window)
        if not completed:
            enqueue(db, review_key, "daily_review", priority=60, due_at=window.due)
        # Retire legacy UTC jobs and missed days, including blocked jobs. Never
        # repay downtime with a backlog of expensive reviews.
        obsolete = select(Work.id).where(Work.kind == "daily_review",
            Work.status.in_(["ready", "blocked"]))
        if not completed:
            obsolete = obsolete.where(Work.key != review_key)
        db.execute(update(Work).where(Work.id.in_(obsolete)).values(
            status="superseded", error="Pacific review schedule supersedes this wake"))
        executive = {key: value for key, value in get_memory(db, "working", "executive").items()
                     if key != "pending_day"}
        executive.update(timezone="America/Los_Angeles",
                         next_due=window.next_due if completed else window.due)
        if completed:
            executive.update(day=window.day, last_review=completed.occurred_at)
        elif now >= window.due:
            executive["pending_day"] = window.day
        remember(db, "working", "executive", executive)
        if os.getenv("SHOPIFY_PARTNER_API_TOKEN"):
            enqueue(db, f"payments:{int(now // 3600)}", "payments", priority=65)
        # Two decision-directed searches per six hours, no follow-on research fanout.
        if os.getenv("GROWTH_DISCOVERY_ENABLED", "true") == "true":
            since = datetime.fromtimestamp(now - 30 * 86400, timezone.utc).date().isoformat()
            focus = get_memory(db, "strategic", "strategy").get("discovery_focus", "merchant_pain")
            queries = {"merchant_pain": ('"our" "inventory"', '"my" "reorder"'),
                       "cash_exposure": ('"dead stock"', '"excess inventory"'),
                       "stocky_migration": ('"Stocky" "need"', '"Stocky" "our store"')}.get(focus, ('"our" "inventory"', '"my" "reorder"'))
            for index, terms in enumerate(queries):
                query = f"{terms} after:{since} order:latest"
                enqueue(db, f"discover-slot:{int(now // 21600)}:{index}", "discover",
                        {"query": query, "decision": "Which recent merchant question warrants a useful Skubase health-check offer?"}, priority=10)
        # Supersede overdue periodic wakes; downtime is not a debt of research/model calls.
        for kind, horizon in (("observe", 600), ("inbox", 600), ("discover", 21600)):
            db.execute(update(Work).where(Work.kind == kind, Work.status == "ready", Work.created_at < now - horizon)
                       .values(status="superseded", error="Newer periodic wake covers this interval"))
        ready = db.scalar(select(Work).where(Work.status == "ready", Work.due_at <= now)
                          .order_by(Work.priority.desc(), Work.due_at).limit(1))
        remember(db, "working", "next", {"action": ready.kind if ready else "await_next_evidence", "work_id": ready.id if ready else None,
                 "reason": "Highest available priority toward qualified acquisition", "true_idle": False})
        db.commit()


def opportunity(factory, work):
    with factory() as db:
        require_lease(db, work)
        contact = db.get(Contact, work.payload["contact_id"])
        if not contact or contact.suppressed:
            return {"decision": "do_not_contact", "reason": "missing or suppressed contact"}
        if not contact.email or not current_request(db, contact.id):
            record(db, f"contact-gap:{contact.id}", "CONTACT_RESEARCH_NEEDED", contact.id,
                   {"decision": "Verify a legitimate business contact path before offering a health check", "source": contact.source,
                    "reason": "Public participation does not authorize private contact or posting"})
            db.commit()
            if work.payload.get("evidence_id"):
                with factory() as queue_db:
                    enqueue(queue_db, "contact-research:" + str(work.payload["evidence_id"]), "research_contact",
                            {"contact_id": contact.id, "evidence_id": work.payload["evidence_id"]}, priority=35)
                    queue_db.commit()
            return {"decision": "research_contact_path", "source": contact.source}
        experiment = learning.ensure_experiment(db)
        messages = db.scalar(select(func.count()).select_from(Message).where(Message.experiment_id == experiment.id,
                             Message.direction == "out", Message.reply_to_id.is_(None))) or 0
        if messages >= experiment.specification["max_contacts"]:
            return {"decision": "await_experiment_outcomes"}
        message = messaging.draft_first_contact(db, contact, experiment, learning.choose_variant(db, contact, experiment))
        enqueue(db, "send:" + message.id, "send", {"message_id": message.id}, priority=80)
        record(db, f"opportunity-action:{contact.id}:{message.id}", "ACTION_CHOSEN", contact.id,
               {"decision": "test_free_health_check", "message_id": message.id, "expected_value": "Qualified problem and verified contact basis; limited one-contact downside"})
        db.commit()
        return {"decision": "email_queued", "message_id": message.id}


def reply(factory, work, model=call_model):
    with factory() as db:
        message = db.get(Message, work.payload["message_id"])
        if not message:
            return {"missing": True}
        classification = message.classification
        raw = message.body
    if classification == "UNKNOWN":
        try:
            response = model(factory, "classify_reply", {"reply": raw[:4000], "allowed_classes": sorted(REPLY_CLASSES),
                "json_shape": {"classification": "one allowed class", "confidence": "0..1"}}, key="classify:" + message.id)
            if response.get("classification") in REPLY_CLASSES and float(response.get("confidence", 0)) >= .8:
                classification = response["classification"]
        except GrowthError:
            pass  # Uncertainty remains visible; do not convert it into assumed consent.
    with factory() as db:
        require_lease(db, work)
        message = db.get(Message, work.payload["message_id"])
        contact = db.get(Contact, message.contact_id)
        message.classification = classification
        if classification in {"UNSUBSCRIBE", "SUBSTANTIVE_NEGATIVE", "DELIVERY_FAILURE"}:
            contact.suppressed = True
        if message.experiment_id:
            learning.evaluate(db, message.experiment_id)
        event = db.get(Evidence, work.payload.get("evidence_id"))
        service = answer_request(db, contact, event, raw, parent=message) if event and classification in learning.POSITIVE else None
        if service:
            next_action = "Answer the requested service question using verified product knowledge"
        elif classification in learning.POSITIVE and contact.qualification.get("qualified") and not contact.suppressed:
            # One relevant assistance reply; further substantive questions become owner obligations.
            followups = db.scalar(select(func.count()).select_from(Message).where(Message.contact_id == contact.id,
                                  Message.direction == "out", Message.reply_to_id.is_not(None))) or 0
            if followups == 0 and classification == "SUBSTANTIVE_POSITIVE" and current_request(db, contact.id):
                response, _ = insert_once_message(db, message, contact)
                enqueue(db, "send:" + response.id, "send", {"message_id": response.id}, priority=95)
                next_action = "Send requested health-check setup help"
            else:
                record(db, f"reply-obligation:{message.id}", "OWNER_ATTENTION", contact.id,
                       {"priority": "high", "reason": "Merchant has a substantive question requiring a verified answer", "message_id": message.id})
                next_action = "Answer merchant question through the reviewed contact workflow"
        elif classification in learning.POSITIVE and not contact.suppressed:
            record(db, f"inbound-qualification:{message.id}", "OWNER_ATTENTION", contact.id,
                   {"priority": "normal", "reason": "New substantive inbound request needs qualification and a verified answer", "message_id": message.id})
            next_action = "Qualify inbound request before responding"
        else:
            next_action = "Respect suppression or await substantive evidence"
        remember(db, "working", "next", {"action": next_action, "evidence_id": work.payload.get("evidence_id")})
        db.commit()
    return {"classification": classification, "next_action": next_action}


def insert_once_message(db, original, contact):
    from .store import insert_once
    from .service_replies import permit, current_request, service_body
    request = current_request(db, contact.id)
    if not request:
        raise GrowthError("A positive reply alone does not authorize promotional follow-up")
    message, fresh = insert_once(db, Message, key="assistance:" + contact.id, contact_id=contact.id,
        experiment_id=original.experiment_id, direction="out", reply_to_id=original.id,
        subject="Re: Your Shopify inventory health check",
        body=service_body("To continue the Skubase inventory check you requested, connect your store at https://skubase.io/store-sync and start an import for read-only analysis. Please don't email customer data, passwords or tokens. Reply with the step if you encounter a connection error."))
    if fresh:
        permit(db, message, request, "health_check", ["backend/app/api/routes/inventory_risk_snapshot.py"])
    return message, fresh


def daily_review(factory, work, model=call_model):
    now = time.time()
    window = review_day(now)
    if work.key != "review:" + window.key:
        return {"superseded": True, "day": window.day}
    if now < window.due:
        return {"not_due": True, "next_due": window.due}
    with factory() as db:
        prior = completed_review(db, window)
        if prior:
            return {"already_reviewed": True, "evidence_id": prior.id}
    if os.getenv("GROWTH_REVIEW_MODE") == "codex":
        from .executive import export_packet
        with factory() as db:
            packet = export_packet(db)
            if packet.get("already_reviewed") or packet.get("not_due"):
                return packet
            remember(db, "working", "executive", {**get_memory(db, "working", "executive"),
                     "mode": "codex", "pending_day": packet["day"]})
            db.commit()
        return {"awaiting_codex_executive": True, "day": packet["day"], "api_spend_usd": 0}
    with factory() as db:
        skill = active_skill(db, "daily_review")
        evidence = context(db, limit=12)
        strategy = get_memory(db, "strategic", "strategy")
        data = {"skill": skill.specification, "strategy": strategy, "evidence": evidence,
                "funnel": funnel.funnel_counts(db), "bottleneck": funnel.bottleneck(db),
                "available_actions": ["discover", "evaluate", "product_feedback", "opportunity"],
                "json_shape": {"what_happened": "text", "learned": "text", "changed": "text", "failed": "text",
                 "strongest_signal": "text", "biggest_uncertainty": "text", "stop": "text", "more": "text", "icp": "hypothesis text",
                 "positioning": "hypothesis text", "next_action": "one available action", "reason": "text", "evidence_ids": [0]}}
    result = model(factory, "daily_review", data, key=work.key)
    valid_ids = {e["id"] for e in evidence}
    cited = result.get("evidence_ids", [])
    if not isinstance(cited, list) or not cited or any(i not in valid_ids for i in cited):
        raise GrowthError("Daily review must cite retrieved evidence IDs", "permanent")
    action = result.get("next_action")
    if action not in data["available_actions"]:
        raise GrowthError("Review requested an unavailable action", "policy")
    with factory() as db:
        require_lease(db, work)
        if review_day(time.time()).day != window.day:
            return {"superseded": True, "reason": "Review crossed the Pacific day boundary"}
        prior = completed_review(db, window)
        if prior:
            return {"already_reviewed": True, "evidence_id": prior.id}
        # Free-form reasoning is stored as an inference. It never changes limits or permissions.
        event = record(db, "executive-review:" + window.key, "EXECUTIVE_REVIEW", "mission",
                       {**result, "day": window.day, "timezone": "America/Los_Angeles"},
                       source="daily_model_review", epistemic="INFERENCE")
        remember(db, "working", "executive", {"last_review": event.occurred_at,
                 "next_due": window.next_due, "day": window.day,
                 "timezone": "America/Los_Angeles", "mode": "api"})
        remember(db, "strategic", "review", result, source="daily_model_review")
        revised = {**strategy, "icp": str(result.get("icp", strategy["icp"]))[:800],
                   "positioning": str(result.get("positioning", strategy["positioning"]))[:400],
                   "biggest_uncertainty": str(result.get("biggest_uncertainty", "UNKNOWN"))[:500],
                   "next_action": action, "evidence_ids": cited}
        remember(db, "strategic", "strategy", revised, source="daily_model_review")
        proposal = result.get("skill_proposal")
        if isinstance(proposal, dict) and proposal.get("name") in {"email_outreach", "reply_interpretation", "daily_review"}:
            try:
                propose_revision(db, proposal["name"], proposal["specification"], cited)
            except (ValueError, KeyError):
                record(db, "invalid-skill-proposal:" + work.id, "SKILL_PROPOSAL_REJECTED", "skills", {"reason": "invalid specification"})
        if action == "product_feedback":
            enqueue(db, "review-feedback:" + work.id, "product_feedback", {"feedback": data["bottleneck"]}, priority=90)
        elif action == "evaluate":
            for exp in db.scalars(select(Experiment).where(Experiment.status.in_(["active", "observing"])).limit(2)):
                enqueue(db, "review-evaluate:" + work.id + ":" + exp.id, "evaluate", {"experiment_id": exp.id}, priority=60)
        elif action == "opportunity":
            candidate = db.scalar(select(Contact).where(Contact.status == "qualified", Contact.suppressed.is_(False)).limit(1))
            if candidate:
                enqueue(db, "review-opportunity:" + work.id, "opportunity", {"contact_id": candidate.id}, priority=70)
        # Discover uses the existing bounded schedule, not another research wave.
        db.commit()
    return result


def handle(factory, work, *, provider=messaging.resend_request, fetch=discovery.public_json, model=call_model):
    if work.kind == "send":
        return messaging.send(factory, work, provider=provider)
    if work.kind == "inbox":
        return messaging.poll_replies(factory, provider=provider)
    if work.kind == "opportunity":
        return opportunity(factory, work)
    if work.kind == "reply":
        return reply(factory, work, model=model)
    if work.kind == "discover":
        return discovery.discover(factory, **work.payload, fetch=fetch)
    if work.kind == "research_contact":
        return discovery.research_contact(factory, work, fetch=fetch)
    if work.kind == "daily_review":
        return daily_review(factory, work, model=model)
    if work.kind == "payments":
        from .shopify_payments import reconcile_payments
        return reconcile_payments(factory)
    with factory() as db:
        require_lease(db, work)
        if work.kind == "observe":
            funnel.reconcile(db)
            feedback = funnel.bottleneck(db)
            if feedback["stage"] != "insufficient_evidence":
                enqueue(db, "product-feedback:" + digest(feedback), "product_feedback", {"feedback": feedback}, priority=90)
            for exp in db.scalars(select(Experiment).where(Experiment.status.in_(["active", "observing"])).limit(5)):
                learning.evaluate(db, exp.id)
            result = {"funnel": funnel.funnel_counts(db), "bottleneck": feedback}
        elif work.kind == "evaluate":
            result = learning.evaluate(db, work.payload["experiment_id"])
        elif work.kind == "product_feedback":
            result = work.payload["feedback"]
            record(db, "feedback:" + digest(result), "PRODUCT_FEEDBACK", "product", result, epistemic="HYPOTHESIS")
            remember(db, "strategic", "bottleneck", result)
            # Pause new outbound while preserving reply obligations.
            remember(db, "working", "acquisition_hold", {"reason": result, "requires_product_review": True})
        else:
            raise GrowthError("Unknown work type", "permanent")
        db.commit()
        return result


def run_once(factory, *, schedule_wakes=True, **adapters):
    if schedule_wakes:
        schedule(factory)
    with factory() as db:
        if get_memory(db, "working", "control").get("paused"):
            return False
    work = claim(factory)
    if not work:
        return False
    with factory() as db:
        remember(db, "working", "activity", {"activity": work.kind, "last_wake": time.time(), "work_id": work.id,
                 "model": "gpt-6-astra" if work.kind == "daily_review" and os.getenv("GROWTH_REVIEW_MODE") != "codex" else None, "health": "working"})
        db.commit()
    stopped = threading.Event()
    def beat():
        while not stopped.wait(25):
            if not heartbeat(factory, work.id, work.lease_token):
                return
    thread = threading.Thread(target=beat, daemon=True)
    thread.start()
    try:
        result = handle(factory, work, **adapters)
        finish(factory, work, result=result)
    except GrowthError as exc:
        finish(factory, work, error=str(exc), failure_class=exc.category)
    except Exception as exc:
        logger.error("Growth work failed: %s", type(exc).__name__)
        if str(exc) != "lease_lost":
            finish(factory, work, error=type(exc).__name__, failure_class="transient")
    finally:
        stopped.set()
        thread.join(timeout=2)
        with factory() as db:
            remember(db, "working", "activity", {"activity": "await_next_action", "last_wake": time.time(), "model": None, "health": "running"})
            db.commit()
    return True
