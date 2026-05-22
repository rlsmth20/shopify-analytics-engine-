from __future__ import annotations

from typing import Literal

PlanTier = Literal["starter", "growth", "scale"]
FeatureKey = Literal[
    "supplier_scorecards",
    "bundle_analysis",
    "transfers",
    "liquidation",
]

PLAN_ORDER: dict[PlanTier, int] = {
    "starter": 0,
    "growth": 1,
    "scale": 2,
}

FEATURE_MIN_TIER: dict[FeatureKey, PlanTier] = {
    "supplier_scorecards": "growth",
    "bundle_analysis": "growth",
    "transfers": "growth",
    "liquidation": "growth",
}

ALERT_CHANNEL_MIN_TIER: dict[str, PlanTier] = {
    "email": "starter",
    "slack": "starter",
    "sms": "growth",
    "webhook": "growth",
}


def plan_to_tier(plan: str | None) -> PlanTier | None:
    if not plan or plan == "none":
        return None
    if plan.startswith("starter_"):
        return "starter"
    if plan.startswith("growth_"):
        return "growth"
    if plan.startswith("scale_"):
        return "scale"
    return None


def tier_allows(tier: PlanTier | None, minimum: PlanTier) -> bool:
    if tier is None:
        return False
    return PLAN_ORDER[tier] >= PLAN_ORDER[minimum]


def plan_allows_feature(plan: str | None, feature: FeatureKey) -> bool:
    return tier_allows(plan_to_tier(plan), FEATURE_MIN_TIER[feature])


def plan_allows_alert_channel(plan: str | None, channel: str) -> bool:
    minimum = ALERT_CHANNEL_MIN_TIER.get(channel)
    if minimum is None:
        return False
    return tier_allows(plan_to_tier(plan), minimum)
