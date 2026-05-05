"""Dead-stock liquidation suggestions.

Translates the vague "dead stock" flag into an actionable markdown plan.
Tactic + markdown are chosen from SKU age, capital exposure, and margin:

* <60 days stale + margin > 50% → modest markdown
* 60-120 days stale                → aggressive markdown or bundle
* 120+ days stale                  → wholesale or write-off
"""
from __future__ import annotations

import math

from app.schemas import SkuDetail
from app.schemas_v2 import LiquidationSuggestion


DEAD_STOCK_THRESHOLD_DAYS = 45
NEVER_SOLD_DAYS = 999


def build_liquidation_plan(skus: list[SkuDetail]) -> list[LiquidationSuggestion]:
    suggestions: list[LiquidationSuggestion] = []

    for sku in skus:
        if sku.days_since_last_sale < DEAD_STOCK_THRESHOLD_DAYS:
            continue
        if sku.inventory <= 0:
            continue

        margin = (sku.price - sku.cost) / max(sku.price, 0.01)
        capital = sku.inventory * sku.cost

        tactic, markdown_pct = _choose_tactic(
            days_stale=sku.days_since_last_sale,
            margin=margin,
            capital=capital,
        )

        suggested_price = round(sku.price * (1 - markdown_pct), 2)
        if tactic == "wholesale":
            suggested_price = round(sku.cost * 1.05, 2)  # cover cost + small margin
        if tactic == "donate_write_off":
            suggested_price = 0.0

        projected_recovery = _projected_recovery(
            sku=sku, suggested_price=suggested_price, tactic=tactic
        )

        suggestions.append(
            LiquidationSuggestion(
                sku_id=sku.sku_id,
                name=sku.name,
                on_hand=sku.inventory,
                days_since_last_sale=sku.days_since_last_sale,
                capital_tied_up=round(capital, 2),
                suggested_markdown_pct=round(markdown_pct * 100, 1),
                suggested_price=suggested_price,
                projected_recovered_capital=round(projected_recovery, 2),
                tactic=tactic,
                rationale=_rationale(sku, tactic, markdown_pct, projected_recovery),
            )
        )

    suggestions.sort(key=lambda s: s.capital_tied_up, reverse=True)
    return suggestions


def _choose_tactic(
    days_stale: int, margin: float, capital: float
) -> tuple[str, float]:
    if days_stale >= 180 and capital < 1500:
        return "donate_write_off", 1.0
    if days_stale >= 150:
        return "wholesale", 0.7
    if days_stale >= 90:
        return "markdown", 0.35 if margin > 0.4 else 0.25
    if days_stale >= 60:
        return "bundle", 0.2
    # 45-59 days: light markdown to test
    return "markdown", 0.15 if margin > 0.35 else 0.1


def _projected_recovery(
    sku: SkuDetail, suggested_price: float, tactic: str
) -> float:
    if tactic == "donate_write_off":
        return 0.0
    # Assume 70% sell-through at the discounted price for markdowns + bundles,
    # 90% for wholesale since a single buyer takes the lot.
    sell_through = 0.9 if tactic == "wholesale" else 0.7
    units_moved = math.floor(sku.inventory * sell_through)
    return units_moved * suggested_price


def _rationale(
    sku: SkuDetail, tactic: str, markdown_pct: float, projected: float
) -> str:
    if tactic == "donate_write_off":
        if sku.days_since_last_sale >= NEVER_SOLD_DAYS:
            return (
                "No sales are recorded for this SKU. Write off or donate for tax "
                "purposes if it is truly unsellable; otherwise verify the sales import "
                "before clearing it."
            )
        return (
            f"Inventory has been stale {sku.days_since_last_sale} days with no movement. "
            "Write off or donate for tax purposes — the shelf space is worth more."
        )
    if tactic == "wholesale":
        return (
            f"Sold at cost+5% to a wholesale buyer; expect to recover ~${projected:,.0f} "
            "and free up shelf space quickly."
        )
    if tactic == "bundle":
        return (
            f"Bundle with a fast-mover at ~{int(markdown_pct * 100)}% off to move volume "
            "without directly marking down the SKU."
        )
    return (
        f"Apply a {int(markdown_pct * 100)}% markdown — projected to recover "
        f"~${projected:,.0f} across the remaining {sku.inventory} units."
    )
