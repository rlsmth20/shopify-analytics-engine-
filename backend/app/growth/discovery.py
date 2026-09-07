"""Bounded public research. No authenticated scraping, proxy fallback or link crawling."""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape

from sqlalchemy import select

from .models import Contact, Evidence
from .policy import GrowthError, qualify
from .store import digest, enqueue, get_memory, record, remember

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
    return event


def discover(factory, *, decision, query, fetch=public_json):
    if not decision.strip() or len(query) > 180:
        raise GrowthError("Research needs a bounded query and the decision it will change", "policy")
    cache_key = digest(query)
    with factory() as db:
        cached = get_memory(db, "channel", "query:" + cache_key)
        if cached.get("next_at", 0) > time.time():
            return {"cached": True, "decision": decision}
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
