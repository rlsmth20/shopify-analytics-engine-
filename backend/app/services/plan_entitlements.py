from __future__ import annotations

from typing import Literal

PlanTier = Literal["starter", "growth", "scale"]
PlanId = Literal["none", "trial", "starter", "growth", "scale"]
FeatureKey = Literal[
    "forecast",
    "reorder_pos",
    "supplier_scorecards",
    "bundle_analysis",
    "transfers",
    "liquidation",
]
CapabilityKey = Literal[
    "billing",
    "account",
    "store_sync",
    "contact_feedback",
    "stocky_migration",
    "limited_today",
    "today_basic",
    "action_queue_basic",
    "alerts_basic",
    "alerts_advanced",
    "forecast",
    "projected_stock_health",
    "inventory_health_basic",
    "reports_basic",
    "reports_export",
    "reorder_pos",
    "bundle_opportunities",
    "dead_stock_basic",
    "suppliers_basic",
    "supplier_scorecards",
    "transfers",
    "inventory_rules_advanced",
    "scheduled_reports",
    "team_controls",
    "priority_support",
]

PLAN_ORDER: dict[PlanTier, int] = {
    "starter": 0,
    "growth": 1,
    "scale": 2,
}

FEATURE_MIN_TIER: dict[FeatureKey, PlanTier] = {
    "forecast": "growth",
    "reorder_pos": "growth",
    "supplier_scorecards": "scale",
    "bundle_analysis": "growth",
    "transfers": "scale",
    "liquidation": "starter",
}

PLAN_DISPLAY_NAMES: dict[PlanId, str] = {
    "none": "No active plan",
    "trial": "Trial",
    "starter": "Starter",
    "growth": "Growth",
    "scale": "Scale",
}

CAPABILITY_MIN_PLAN: dict[CapabilityKey, PlanId] = {
    "billing": "none",
    "account": "none",
    "store_sync": "none",
    "contact_feedback": "none",
    "stocky_migration": "none",
    "limited_today": "none",
    "today_basic": "starter",
    "action_queue_basic": "starter",
    "alerts_basic": "starter",
    "alerts_advanced": "growth",
    "forecast": "growth",
    "projected_stock_health": "growth",
    "inventory_health_basic": "starter",
    "reports_basic": "starter",
    "reports_export": "growth",
    "reorder_pos": "growth",
    "bundle_opportunities": "growth",
    "dead_stock_basic": "starter",
    "suppliers_basic": "growth",
    "supplier_scorecards": "scale",
    "transfers": "scale",
    "inventory_rules_advanced": "growth",
    "scheduled_reports": "scale",
    "team_controls": "scale",
    "priority_support": "scale",
}

PLAN_ID_ORDER: dict[PlanId, int] = {
    "none": -1,
    "trial": 99,
    "starter": 0,
    "growth": 1,
    "scale": 2,
}

ALERT_CHANNEL_MIN_TIER: dict[str, PlanTier] = {
    "email": "starter",
    "slack": "starter",
    "sms": "growth",
    "webhook": "growth",
}


def normalize_plan_name(plan: str | None) -> PlanId:
    if not plan or plan == "none":
        return "none"
    normalized = (
        str(plan)
        .strip()
        .lower()
        .replace("skubase", "")
        .replace("-", "_")
        .replace(" ", "_")
    )
    if normalized in {"trial", "trialing"}:
        return "trial"
    if "starter" in normalized:
        return "starter"
    if "growth" in normalized:
        return "growth"
    if "scale" in normalized:
        return "scale"
    return "none"


def plan_to_tier(plan: str | None) -> PlanTier | None:
    plan_id = normalize_plan_name(plan)
    if plan_id in {"starter", "growth", "scale"}:
        return plan_id
    return None


def tier_allows(tier: PlanTier | None, minimum: PlanTier) -> bool:
    if tier is None:
        return False
    return PLAN_ORDER[tier] >= PLAN_ORDER[minimum]


def is_at_least_plan(current_plan: PlanId, required_plan: PlanId) -> bool:
    return PLAN_ID_ORDER[current_plan] >= PLAN_ID_ORDER[required_plan]


def has_capability(current_plan: PlanId, capability: CapabilityKey) -> bool:
    return is_at_least_plan(current_plan, CAPABILITY_MIN_PLAN[capability])


def capabilities_for_plan(current_plan: PlanId) -> list[CapabilityKey]:
    return [
        capability
        for capability in CAPABILITY_MIN_PLAN
        if has_capability(current_plan, capability)
    ]


def get_required_plan_for_capability(capability: CapabilityKey) -> PlanId:
    return CAPABILITY_MIN_PLAN[capability]


def get_plan_display_name(plan: PlanId) -> str:
    return PLAN_DISPLAY_NAMES[plan]


def plan_allows_feature(plan: str | None, feature: FeatureKey) -> bool:
    return tier_allows(plan_to_tier(plan), FEATURE_MIN_TIER[feature])


def plan_allows_alert_channel(plan: str | None, channel: str) -> bool:
    minimum = ALERT_CHANNEL_MIN_TIER.get(channel)
    if minimum is None:
        return False
    return tier_allows(plan_to_tier(plan), minimum)
