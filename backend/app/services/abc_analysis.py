"""ABC / XYZ classification.

ABC splits SKUs by revenue contribution (80/15/5 by default).
XYZ splits SKUs by demand variability (coefficient of variation).

Together they segment a catalog so the operator knows *which* SKUs need tight
forecasting vs loose monitoring:

* AX = top revenue, predictable      → tight safety stock, automate reordering
* AZ = top revenue, erratic          → highest strategic risk, manual attention
* CX = tail, predictable             → candidates for bulk ordering / kitting
* CZ = tail, erratic                 → candidates for discontinuation
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Iterable

from app.schemas import SkuDetail
from app.schemas_v2 import AbcClass, SkuScorecard, XyzClass


@dataclass(frozen=True)
class HistoryProvider:
    """Supplies a daily sales history list per SKU for CV calculation."""
    fn: callable

    def history(self, sku_id: str) -> list[float]:
        return self.fn(sku_id)


def build_scorecards(
    skus: list[SkuDetail],
    history_for_sku: callable,
    cutoff_a_pct: float = 0.80,
    cutoff_b_pct: float = 0.95,
) -> list[SkuScorecard]:
    if not skus:
        return []

    revenue_by_sku: dict[str, float] = {}
    for sku in skus:
        revenue_by_sku[sku.sku_id] = sku.price * sku.last_30_day_sales

    total_revenue = sum(revenue_by_sku.values()) or 1.0
    ranked = sorted(skus, key=lambda s: revenue_by_sku[s.sku_id], reverse=True)

    scorecards: list[SkuScorecard] = []
    cumulative = 0.0
    for sku in ranked:
        contribution = revenue_by_sku[sku.sku_id] / total_revenue
        cumulative += contribution
        abc_class = _classify_abc(cumulative, cutoff_a_pct, cutoff_b_pct)

        history = history_for_sku(sku.sku_id) or []
        xyz_class, cv = _classify_xyz(history)

        scorecards.append(
            SkuScorecard(
                sku_id=sku.sku_id,
                name=sku.name,
                vendor=sku.vendor,
                category=sku.category,
                abc_class=abc_class,
                xyz_class=xyz_class,
                contribution_pct=round(contribution * 100, 2),
                variability_cv=round(cv, 3),
                avg_daily_units=round(sku.last_30_day_sales / 30, 2),
                avg_daily_revenue=round(revenue_by_sku[sku.sku_id] / 30, 2),
                profit_per_unit=round(sku.price - sku.cost, 2),
                sell_through_30d=round(
                    sku.last_30_day_sales / max(sku.inventory + sku.last_30_day_sales, 1),
                    3,
                ),
                inventory_on_hand=sku.inventory,
                classification_note=_note_for_class(abc_class, xyz_class),
            )
        )
    return scorecards


def _classify_abc(cumulative: float, cutoff_a: float, cutoff_b: float) -> AbcClass:
    if cumulative <= cutoff_a:
        return "A"
    if cumulative <= cutoff_b:
        return "B"
    return "C"


def _classify_xyz(history: Iterable[float]) -> tuple[XyzClass, float]:
    values = [max(0.0, float(v)) for v in history]
    if len(values) < 14 or sum(values) == 0:
        return "Z", 1.0
    mean = statistics.mean(values)
    if mean == 0:
        return "Z", 1.0
    stdev = statistics.pstdev(values)
    cv = stdev / mean
    if cv < 0.4:
        return "X", cv
    if cv < 0.9:
        return "Y", cv
    return "Z", cv


def _note_for_class(abc: AbcClass, xyz: XyzClass) -> str:
    mapping = {
        ("A", "X"): "Top revenue, predictable. Automate reordering with tight safety stock.",
        ("A", "Y"): "Top revenue, moderately variable. Keep a human in the loop on buys.",
        ("A", "Z"): "Top revenue, erratic — highest strategic risk. Manual attention each cycle.",
        ("B", "X"): "Mid revenue, predictable. Batch-order on a fixed cadence.",
        ("B", "Y"): "Mid revenue, moderate variability. Standard safety stock applies.",
        ("B", "Z"): "Mid revenue, volatile. Watch for event-driven demand.",
        ("C", "X"): "Long-tail, predictable. Consider bulk buys or kitting opportunities.",
        ("C", "Y"): "Long-tail, moderate variability. Low priority for replenishment work.",
        ("C", "Z"): "Long-tail and erratic. Candidate for discontinuation or liquidation.",
    }
    return mapping.get((abc, xyz), "Standard inventory management rules apply.")
