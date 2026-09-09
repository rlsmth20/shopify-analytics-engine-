import os
import re
from dataclasses import dataclass
from email.utils import parseaddr


class GrowthError(Exception):
    def __init__(self, message, category="policy"):
        super().__init__(message)
        self.category = category


def number(name, default=0.0):
    try:
        value = float(os.getenv(name, str(default)))
        return value if value >= 0 and value < 1_000_000 else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Policy:
    daily_usd: float = 0
    daily_emails: int = 20  # Legacy compatibility; the shared ledger reads the owner's nullable outreach policy.
    email_unit_usd: float = 0
    sender: str = ""
    postal_address: str = ""
    email_enabled: bool = False
    model_enabled: bool = False
    paid_ads_allowed: bool = False

    @classmethod
    def from_env(cls):
        # No model-provided text is consulted for authority or resource limits.
        return cls(daily_usd=number("GROWTH_DAILY_USD"),
                   daily_emails=20,
                   email_unit_usd=number("GROWTH_EMAIL_UNIT_USD"),
                   sender=os.getenv("GROWTH_MAILBOX", "").strip().lower(),
                   postal_address=os.getenv("GROWTH_POSTAL_ADDRESS", "").strip(),
                   email_enabled=os.getenv("GROWTH_EMAIL_ENABLED") == "true",
                   model_enabled=os.getenv("GROWTH_MODEL_ENABLED") == "true")

    def check_mailbox(self):
        address = parseaddr(self.sender)[1]
        if (not self.email_enabled or address != self.sender or
                not re.fullmatch(r"[a-z0-9._+-]+@skubase\.io", address)):
            raise GrowthError("Configure the approved dedicated @skubase.io mailbox", "configuration")
        if not os.getenv("GROWTH_RESEND_API_KEY"):
            raise GrowthError("Dedicated growth Resend integration is not configured", "configuration")
        if os.getenv("GROWTH_INBOUND_ENABLED") != "true":
            raise GrowthError("Reply ingestion must be configured before sending", "configuration")


PAIN = {
    "cash": ("overstock", "dead stock", "dead inventory", "excess inventory", "cash trapped", "slow moving"),
    "reorder": ("stockout", "stock out", "reorder", "safety stock", "lead time", "forecast", "purchasing", "spreadsheet"),
    "stocky": ("stocky", "inventory planner", "inventory planning"),
}


def qualify(text, *, age_days=0, merchant_verified=False):
    lower = text.lower()
    pains = [key for key, terms in PAIN.items() if any(term in lower for term in terms)]
    intent = any(term in lower for term in ("looking for", "recommend", "alternative", "need", "how do", "help", "pay", "price"))
    fit = merchant_verified or ("shopify" in lower and any(term in lower for term in ("my store", "our store", "we sell", "my shop", "our shop")))
    # A transparent heuristic, not a calibrated conversion probability.
    score = (30 * bool(pains) + 25 * intent + 20 * fit + max(0, 15 - age_days / 2))
    return {"pains": pains, "intent": intent, "fit": fit, "score": round(score, 2),
            "confidence": 0.65 if fit else 0.35, "qualified": bool(pains and intent and fit),
            "reason": "Inventory pain and stated intent; merchant fit " + ("supported" if fit else "unverified"),
            "ranking_factors": {"intent": intent, "fit": fit, "age_days": age_days,
                                "ability_to_help": bool(pains), "engagement": "UNKNOWN",
                                "commercial_value": "UNKNOWN", "cost_usd": 0, "channel_rules": "review_required"}}


REPLY_CLASSES = {"SUBSTANTIVE_POSITIVE", "SUBSTANTIVE_NEUTRAL", "SUBSTANTIVE_NEGATIVE", "QUESTION",
                 "AUTOMATED", "DELIVERY_FAILURE", "UNSUBSCRIBE", "UNKNOWN"}


def classify_reply(text, headers=None):
    headers = {k.lower(): str(v).lower() for k, v in (headers or {}).items()}
    lower = text.lower().replace("\u2019", "'").split("\non ")[0].split("\n>")[0][:4000]
    explicit_opt_out = re.search(
        r"\b(?:stop|cease)\s+(?:emailing|contacting|messaging)\b"
        r"|\bleave\s+(?:me|us)\s+alone\b"
        r"|\b(?:take|remove)\s+(?:me|us)\s+(?:off|from)\b"
        r"|\bno\s+more\s+(?:emails?|messages?|contact)\b", lower)
    if explicit_opt_out or lower.strip() == "stop" or any(t in lower for t in ("unsubscribe", "remove me", "stop emailing", "do not contact", "don't contact")):
        return "UNSUBSCRIBE"
    if any(t in lower for t in ("delivery failed", "undeliverable", "mailbox not found")):
        return "DELIVERY_FAILURE"
    if headers.get("auto-submitted", "no") != "no" or any(t in lower for t in ("out of office", "automatic reply")):
        return "AUTOMATED"
    explicit_decline = re.search(
        r"\b(?:do not|don't|dont)\s+want\b.{0,60}\b(?:health check|demo|offer|service|app)\b", lower)
    if explicit_decline or any(t in lower for t in ("not interested", "no thanks", "no thank you", "not a fit")):
        return "SUBSTANTIVE_NEGATIVE"
    if any(t in lower for t in ("send me", "interested", "health check", "book a demo", "try it", "sign me up")):
        return "SUBSTANTIVE_POSITIVE"
    if "?" in lower:
        return "QUESTION"
    if len(lower.split()) >= 12 and any(t in lower for terms in PAIN.values() for t in terms):
        return "SUBSTANTIVE_NEUTRAL"
    return "UNKNOWN"
