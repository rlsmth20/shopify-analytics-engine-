"""Bounded public research. No authenticated scraping, proxy fallback or link crawling."""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape

from sqlalchemy import select, update

from .models import Contact, Evidence, Memory, Work
from .policy import GrowthError, qualify
from .store import digest, enqueue, get_memory, record, remember, require_lease

PUBLIC_HOSTS = {"community.shopify.com"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise GrowthError("Public source redirected; channel review required", "policy")


def public_json(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in PUBLIC_HOSTS or parsed.port or parsed.username:
        raise GrowthError("Unapproved public research host", "policy")
    request = urllib.request.Request(url, headers={"User-Agent": "SkubaseGrowth/1.0 (+https://skubase.io; info@skubase.io)", "Accept": "application/json"})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=15) as response:
            raw = response.read(512001)
        if len(raw) > 512000:
            raise GrowthError("Source exceeds bounded read", "permanent")
        return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raise GrowthError(f"Source HTTP {exc.code}; no restriction bypass",
                          "policy" if exc.code in (401, 403, 429) else "transient") from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise GrowthError("Public source unavailable", "transient") from None


def clean_text(value):
    return unescape(re.sub(r"<[^>]+>", " ", value)).strip()[:5000]


def ingest_opportunity(db, *, url, text, published_at=None, author=None, channel="shopify_community", organization="Unknown"):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Evidence requires an HTTPS source URL")
    canonical = urllib.parse.urlunparse(("https", parsed.netloc.lower(), parsed.path.rstrip("/"), "", "", ""))
    topic = re.search(r"/t/(?:[^/]+/)?(\d+)", parsed.path)
    if topic and parsed.hostname == "community.shopify.com":
        canonical = f"https://community.shopify.com/t/{topic.group(1)}"
    source_url = urllib.parse.urlunparse(("https", parsed.netloc.lower(), parsed.path.rstrip("/"), "", "", ""))
    evidence_key = "opportunity:" + digest([canonical, author, clean_text(text)])
    existing = db.scalar(select(Evidence).where(Evidence.key == evidence_key))
    if existing:
        return existing
    now = time.time()
    age = max(0, (now - published_at) / 86400) if published_at else 365
    q = qualify(text, age_days=age)
    vendor = any(term in text.lower() for term in ("we built", "our app", "i built", "try our", "i'm the founder of", "i am the founder of"))
    if vendor:
        q = {**q, "qualified": False, "fit": False, "reason": "Vendor promotion is not merchant buying evidence", "vendor_promotion": True}
    identity = f"{channel}:{author}" if author else canonical
    contact = db.scalar(select(Contact).where(Contact.identity == identity))
    if not contact:
        contact = Contact(identity=identity, organization=organization, source=canonical,
                          characteristics={"channel": channel}, qualification=q)
        db.add(contact)
        db.flush()
    event = record(db, evidence_key, "OPPORTUNITY", contact.id,
                   {"text": text[:5000], "published_at": published_at, "author": author,
                    "channel": channel, "qualification": q, "channel_permission": "research_only"}, source=source_url)
    if q["qualified"] and age <= 30:
        contact.qualification = q
        contact.status = "qualified"
        enqueue(db, f"opportunity-decision:{event.id}", "opportunity", {"contact_id": contact.id, "evidence_id": event.id}, priority=q["score"])
    elif not vendor and q["pains"] and q["intent"] and age <= 30:
        # At most two deeper investigations per six-hour period, no recursive fanout.
        bucket = int(now // 21600)
        pending = list(db.scalars(select(Work.id).where(Work.key.like(f"targeted-research:{bucket}:%"))))
        if len(pending) < 2:
            enqueue(db, f"targeted-research:{bucket}:{event.id}", "research_contact",
                    {"contact_id": contact.id, "evidence_id": event.id}, priority=35)
    return event


def discover(factory, *, decision, query, fetch=public_json):
    if not decision.strip() or len(query) > 180:
        raise GrowthError("Research needs a bounded query and the decision it will change", "policy")
    cache_key = digest(query)
    with factory() as db:
        cached = get_memory(db, "channel", "query:" + cache_key)
        if cached.get("next_at", 0) > time.time():
            return {"cached": True, "decision": decision}
        db.execute(update(Memory).where(Memory.namespace == "working", Memory.key == "budget")
                   .values(version=Memory.version + 1))
        bucket = int(time.time() // 21600)
        attempted_queries = {e.data.get("query") for e in db.scalars(select(Evidence).where(
            Evidence.kind.in_(["DISCOVERY_FETCH_INTENT", "DISCOVERY_RESULT"]), Evidence.occurred_at >= bucket * 21600))}
        if len(attempted_queries) >= 2:
            return {"decision": "discovery_cap_reached", "next_window": (bucket + 1) * 21600}
        record(db, f"discovery-intent:{bucket}:{cache_key}", "DISCOVERY_FETCH_INTENT", "mission", {"query": query, "decision": decision})
        # Persist before IO so failures/restarts cannot cause a research wave.
        remember(db, "channel", "query:" + cache_key, {"query": query, "decision": decision, "next_at": time.time() + 21600})
        db.commit()
    url = "https://community.shopify.com/search.json?" + urllib.parse.urlencode({"q": query})
    payload = fetch(url)
    topics = {t["id"]: t for t in payload.get("topics", [])}
    count = 0
    with factory() as db:
        for post in payload.get("posts", [])[:20]:
            topic = topics.get(post.get("topic_id"), {})
            if not topic:
                continue
            raw_date = post.get("created_at") or topic.get("created_at")
            try:
                published = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).timestamp() if raw_date else None
            except (ValueError, TypeError):
                published = None
            source = f"https://community.shopify.com/t/{topic.get('slug', 'topic')}/{topic['id']}/{post.get('post_number', 1)}"
            ingest_opportunity(db, url=source, text=clean_text(topic.get("title", "") + "\n" + post.get("blurb", "")),
                               published_at=published, author=post.get("username"))
            count += 1
        record(db, f"discovery:{cache_key}:{int(time.time() // 21600)}", "DISCOVERY_RESULT", "mission",
               {"decision": decision, "query": query, "results_examined": count, "cost_usd": 0}, source=url)
        db.commit()
    return {"results_examined": count, "decision": decision}


def research_contact(factory, work, fetch=public_json):
    with factory() as db:
        require_lease(db, work)
        event = db.get(Evidence, work.payload.get("evidence_id"))
        if not event or event.kind != "OPPORTUNITY":
            raise GrowthError("Research requires an observed opportunity", "permanent")
        parsed = urllib.parse.urlparse(event.source)
        topic = re.search(r"/t/(?:[^/]+/)?(\d+)", parsed.path)
        if parsed.hostname != "community.shopify.com" or not topic:
            return {"decision": "channel_integration_required", "source": event.source}
        cache = get_memory(db, "channel", "topic:" + topic.group(1))
        if cache.get("next_at", 0) > time.time():
            return {"cached": True}
        # Every entry point shares this persisted cap, including executive review.
        db.execute(update(Memory).where(Memory.namespace == "working", Memory.key == "budget")
                   .values(version=Memory.version + 1))
        bucket = int(time.time() // 21600)
        used = list(db.scalars(select(Evidence.id).where(Evidence.kind == "RESEARCH_FETCH_INTENT",
                    Evidence.occurred_at >= bucket * 21600)))
        if len(used) >= 2:
            return {"decision": "research_cap_reached", "next_window": (bucket + 1) * 21600}
        record(db, "research-fetch:" + work.id, "RESEARCH_FETCH_INTENT", event.subject,
               {"decision": "Verify merchant context before choosing a response", "source_evidence_id": event.id})
        remember(db, "channel", "topic:" + topic.group(1), {"next_at": time.time() + 21600,
                 "decision": "Is the original poster a merchant with a problem Skubase can help solve?"})
        author, source, contact_id = event.data.get("author"), event.source, event.subject
        db.commit()
    result = fetch(f"https://community.shopify.com/t/{topic.group(1)}.json")
    posts = result.get("post_stream", {}).get("posts", [])[:20]
    source_post = re.search(r"/(\d+)$", parsed.path[topic.end():])
    matching = [p for p in posts if p.get("username") == author and
                (not source_post or p.get("post_number") == int(source_post.group(1)))]
    if not matching:
        return {"decision": "author_not_in_bounded_source", "source": source}
    text = clean_text(matching[0].get("cooked", ""))
    merchant = any(term in text.lower() for term in ("my store", "our store", "we sell", "our inventory", "our stock", "we run", "i run"))
    vendor = any(term in text.lower() for term in ("our app", "we built", "i built", "try our"))
    q = qualify(text, merchant_verified=merchant and not vendor)
    with factory() as db:
        require_lease(db, work)
        contact = db.get(Contact, contact_id)
        if not contact:
            return {"decision": "contact_erased"}
        observation = record(db, "research:" + digest([source, text]), "PROSPECT_RESEARCHED", contact.id,
            {"text": text, "qualification": q, "vendor_promotion": vendor,
             "contact_path": source, "contact_path_type": "public_conversation",
             "email_permission": False, "posting_permission": "unconfigured_business_identity"}, source=source)
        useful_reply = q["qualified"] and not vendor and "reorder" in q["pains"]
        if q["qualified"] and not vendor:
            contact.qualification = q
            contact.status = "qualified"
            contact.facts = [{"text": text[:180], "source": source, "verified": True, "verification_scope": "public statement, not independent merchant identity"}]
        if useful_reply:
            # A reorder answer must match the observed problem, not just mention Stocky.
            body = ("I work on Skubase. A useful starting check is to separate repeated-selling SKUs from seasonal or one-off products. "
                    "For a repeat SKU, compare inventory position (on hand + confirmed incoming - commitments not already deducted) "
                    "with average daily demand × supplier lead time + your safety-stock buffer. "
                    "Check arrival dates before relying on incoming stock; a late order will not cover an earlier stockout. "
                    "Are the affected products repeat purchases, or seasonal items you cannot reorder?")
            record(db, "community-draft:" + str(observation.id), "COMMUNITY_RESPONSE_DRAFTED", contact.id,
                {"body": body, "source_evidence_id": observation.id, "destination": source,
                 "status": "awaiting_business_channel_identity_and_rules", "affiliation_disclosed": True,
                 "expected_outcome": "Substantive merchant problem clarification"})
        remember(db, "customer", "research:" + contact.id, {"source_evidence_id": observation.id,
                 "stated_merchant_context": merchant, "vendor_promotion": vendor,
                 "qualified": bool(q["qualified"] and not vendor), "source": source})
        db.commit()
        return {"decision": "helpful_response_prepared" if useful_reply else "qualified_problem_requires_specific_response" if q["qualified"] and not vendor else "not_qualified",
                "evidence_id": observation.id, "source": source}
