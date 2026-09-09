"""Source-backed forum learning on existing evidence/memory tables; no model calls."""
import json
import re
import time
from collections import Counter, defaultdict
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select

from .models import Memory
from .store import digest, get_memory, record, remember

POSTS = "community_post"
BATCH_SIZE = 10
Level = Literal["HIGH", "MEDIUM", "LOW"]
State = Literal["YES", "NO", "UNKNOWN"]


def location(url):
    parsed = urlsplit(url)
    match = re.fullmatch(r"/t/(?:[^/]*[^\d/][^/]*/)?(\d+)(?:/(\d+))?/?", parsed.path)
    if parsed.scheme != "https" or parsed.netloc != "community.shopify.com" or not match:
        raise ValueError("Use the actual Shopify Community topic/post HTTPS permalink")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")), match[1], match[2] or "1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CitedStatement(StrictModel):
    url: str = Field(max_length=1000)
    quote: str = Field(min_length=1, max_length=500)

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        return location(value)[0]


class Competitor(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    appearance: CitedStatement
    role: Literal["SELF_PROMOTION", "ORGANIC_RECOMMENDATION", "MENTION", "UNKNOWN"]
    affiliation_evidence: CitedStatement | None
    claimed_problems: list[str] = Field(max_length=8)
    praise: list[CitedStatement] = Field(max_length=4)
    complaints: list[CitedStatement] = Field(max_length=4)
    unmet_capabilities: list[CitedStatement] = Field(max_length=4)
    pricing_complaints: list[CitedStatement] = Field(max_length=4)

    @model_validator(mode="after")
    def attributed(self):
        if self.role == "SELF_PROMOTION" and not self.affiliation_evidence:
            raise ValueError("Self-promotion classification needs explicit affiliation evidence")
        return self


class Discussion(StrictModel):
    url: str = Field(max_length=1000)
    posted_date: str | None = Field(max_length=40)
    merchant_store: str | None = Field(max_length=200)
    problem: str = Field(min_length=1, max_length=400)
    underlying_need: CitedStatement
    categories: list[str] = Field(min_length=1, max_length=5)
    shopify: State
    commercial_relevance: State
    competitors: list[Competitor] = Field(max_length=12)
    existing_solution_limitations: list[CitedStatement] = Field(max_length=8)
    solution_status: Literal["MERCHANT_CONFIRMED", "PROPOSED_UNCONFIRMED", "UNRESOLVED", "UNKNOWN"]
    solution_evidence: CitedStatement | None
    skubase_fit: Literal["VERIFIED", "PARTIAL", "GAP", "UNKNOWN", "NOT_RELEVANT"]
    capability_evidence: str | None = Field(max_length=500)
    potential_missing_feature: str | None = Field(max_length=300)
    acquisition_potential: Level
    strategic_learning_value: Level
    vendor_crowding: Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
    useful_answer: str | None = Field(max_length=600)
    response_decision: Literal["ANSWER", "ANSWER_WITH_BRIEF_SKUBASE", "LEARN_ONLY"]

    @field_validator("categories")
    @classmethod
    def normalize_categories(cls, values):
        result = sorted({re.sub(r"\s+", " ", v.strip().casefold()) for v in values})
        if any(not v or len(v) > 80 for v in result):
            raise ValueError("Use short meaningful problem categories; new categories are welcome")
        return result

    @model_validator(mode="after")
    def grounded(self):
        self.url, thread, _ = location(self.url)
        if location(self.underlying_need.url)[1] != thread:
            raise ValueError("The merchant need must be cited from the same discussion")
        if self.solution_status == "MERCHANT_CONFIRMED" and not self.solution_evidence:
            raise ValueError("A proposed answer is not a merchant-confirmed solution")
        if self.skubase_fit in {"VERIFIED", "PARTIAL", "GAP"} and not self.capability_evidence:
            raise ValueError("Verify product capability before claiming fit or a gap")
        if self.response_decision != "LEARN_ONLY" and not self.useful_answer:
            raise ValueError("A reply must have value even with the Skubase reference removed")
        if self.response_decision == "ANSWER_WITH_BRIEF_SKUBASE" and self.skubase_fit not in {"VERIFIED", "PARTIAL"}:
            raise ValueError("Mention Skubase only for a verified relevant capability")
        return self


def retain(db, payload):
    """Record one actual read, deduplicate retries, retain previous versions."""
    item = Discussion.model_validate(payload).model_dump()
    if len(json.dumps(item)) > 16000:
        raise ValueError("Keep each discussion record compact")
    _, thread, post = location(item["url"])
    key = f"{thread}:{post}"
    previous = get_memory(db, POSTS, key)
    fingerprint = digest(item)
    if previous.get("fingerprint") == fingerprint:
        return {"evidence_id": previous["evidence_id"], "unchanged": True, "synthesis": None}
    event = record(db, f"community-post:{key}:{fingerprint}", "COMMUNITY_DISCUSSION", key,
                   item, source=item["url"])
    remember(db, POSTS, key, {**item, "fingerprint": fingerprint, "evidence_id": event.id,
                              "observed_at": event.occurred_at, "thread_id": thread})
    cursor = get_memory(db, "working", "community_batch")
    pending = set(cursor.get("pending_threads", [])) | {thread}
    remember(db, "working", "community_batch", {**cursor, "pending_threads": sorted(pending)})
    db.flush()
    summary = synthesize(db) if len(pending) >= BATCH_SIZE else None
    return {"evidence_id": event.id, "unchanged": False, "batch_threads": len(pending), "synthesis": summary}


def synthesize(db):
    """Rebuild counters only after ten changed threads; aliases remain evidence-led."""
    rows = [m.value for m in db.scalars(select(Memory).where(Memory.namespace == POSTS).order_by(Memory.updated_at))]
    categories, unresolved, requested = defaultdict(set), defaultdict(set), defaultdict(set)
    competitors = {}
    now = time.time()
    recent, prior = defaultdict(set), defaultdict(set)
    prospects, terminology = [], []
    for row in rows:
        thread = row["thread_id"]
        for category in row["categories"]:
            categories[category].add(thread)
            if row["solution_status"] == "UNRESOLVED":
                unresolved[category].add(thread)
            if row["potential_missing_feature"]:
                requested[row["potential_missing_feature"]].add(thread)
            age = now - row["observed_at"]
            if age < 7 * 86400:
                recent[category].add(thread)
            elif age < 14 * 86400:
                prior[category].add(thread)
        if row["acquisition_potential"] == "HIGH":
            prospects.append({k: row[k] for k in ("url", "merchant_store", "problem", "evidence_id")})
        terminology.append({"quote": row["underlying_need"]["quote"], "url": row["underlying_need"]["url"]})
        for app in row["competitors"]:
            name = app["name"].casefold()
            group = competitors.setdefault(name, {"name": app["name"], "appearances": {}, "claims": set(),
                "praise": {}, "complaints": {}, "unmet_capabilities": {}, "pricing_complaints": {}})
            _, mention_thread, mention_post = location(app["appearance"]["url"])
            group["appearances"].setdefault((mention_thread, mention_post), set()).add(app["role"])
            group["claims"].update(app["claimed_problems"])
            for field in ("praise", "complaints", "unmet_capabilities", "pricing_complaints"):
                for statement in app[field]:
                    group[field][digest(statement)] = statement
    counts = lambda groups: sorted(({"problem": k, "threads": len(v)} for k, v in groups.items()),
                                    key=lambda x: (-x["threads"], x["problem"]))
    app_summary = []
    for group in competitors.values():
        # Conflicting attribution is unknown, never counted as both organic and self-promotion.
        roles = Counter(next(iter(roles)) if len(roles) == 1 else "UNKNOWN"
                        for roles in group["appearances"].values())
        app_summary.append({"name": group["name"], "appearances": len(group["appearances"]),
            "self_promotions": roles["SELF_PROMOTION"], "organic_recommendations": roles["ORGANIC_RECOMMENDATION"],
            "unknown_or_mentions": roles["UNKNOWN"] + roles["MENTION"], "claimed_problems": sorted(group["claims"]),
            **{k: list(group[k].values())[:8] for k in ("praise", "complaints", "unmet_capabilities", "pricing_complaints")}})
    summary = {"threads": len({r["thread_id"] for r in rows}), "posts": len(rows),
        "common_problems": counts(categories), "unresolved_problems": counts(unresolved),
        "requested_features": counts(requested),
        "solution_status_counts": dict(Counter(r["solution_status"] for r in rows)),
        "existing_solution_limitations": [{"evidence_id": r["evidence_id"], **s}
            for r in rows for s in r["existing_solution_limitations"]][-20:],
        "observed_trends": [{"problem": k, "last_7_days": len(recent[k]), "previous_7_days": len(prior[k])}
                            for k in categories],
        "competitors": sorted(app_summary, key=lambda a: (-a["appearances"], a["name"])),
        "prospects": prospects[-10:], "merchant_terminology": terminology[-10:],
        "evidence_ids": [r["evidence_id"] for r in rows],
        "interpretation": "Observed discussion sample, not market share or market growth. Trends reflect observation dates and search coverage. Vendor claims are not merchant outcomes. Unconfirmed solutions are not proven failures.",
        "hypothesis_to_evaluate": "Which repeated, consequential and poorly served need could Skubase solve exceptionally well? Verify business consequences and existing-solution gaps before recommending a positioning or roadmap change."}
    event = record(db, "community-synthesis:" + digest(summary), "COMMUNITY_SYNTHESIS", "shopify-community",
                   summary, epistemic="OBSERVATION")
    remember(db, "community", "synthesis", {**summary, "evidence_id": event.id})
    # The planner's bounded learning context gets counts and a pointer, not raw history.
    remember(db, "learning", "shopify-community", {"evidence_id": event.id, "threads": summary["threads"],
        "common_problems": summary["common_problems"][:5], "unresolved_problems": summary["unresolved_problems"][:5],
        "next_decision": summary["hypothesis_to_evaluate"], "details": "community-export"})
    remember(db, "working", "community_batch", {"pending_threads": [], "synthesis_evidence_id": event.id})
    return {"evidence_id": event.id, "threads": summary["threads"], "details": "community-export"}


def export(db):
    return {"synthesis": get_memory(db, "community", "synthesis"),
            "batch": get_memory(db, "working", "community_batch"),
            "recent_posts": [r.value for r in db.scalars(select(Memory).where(Memory.namespace == POSTS)
                             .order_by(Memory.updated_at.desc()).limit(10))]}
