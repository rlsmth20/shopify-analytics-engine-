"""Supplier scorecard service.

Scores vendors on the dimensions most merchants wish they had:
on-time delivery, fill rate, lead-time variance, cost stability.

Each vendor gets a composite 0-100 score and a tier.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Iterable

from app.schemas import SkuDetail
from app.schemas_v2 import SupplierScorecard


@dataclass(frozen=True)
class SupplierObservation:
    """One PO or shipment observation for a vendor."""
    vendor: str
    expected_lead_time_days: int
    actual_lead_time_days: int
    ordered_qty: int
    received_qty: int
    ordered_unit_cost: float
    received_unit_cost: float


def build_supplier_scorecards(
    observations: Iterable[SupplierObservation],
    skus: list[SkuDetail],
) -> list[SupplierScorecard]:
    grouped: dict[str, list[SupplierObservation]] = {}
    for obs in observations:
        grouped.setdefault(obs.vendor, []).append(obs)

    sku_counts: dict[str, int] = {}
    for sku in skus:
        sku_counts[sku.vendor] = sku_counts.get(sku.vendor, 0) + 1

    scorecards: list[SupplierScorecard] = []
    for vendor, obs_list in grouped.items():
        on_time = sum(
            1 for o in obs_list if o.actual_lead_time_days <= o.expected_lead_time_days
        )
        on_time_pct = round(100 * on_time / len(obs_list), 1)

        ordered_total = sum(o.ordered_qty for o in obs_list)
        received_total = sum(o.received_qty for o in obs_list)
        fill_rate = round(
            100 * received_total / ordered_total if ordered_total else 0, 1
        )

        lead_times = [o.actual_lead_time_days for o in obs_list]
        avg_lead = round(statistics.mean(lead_times), 1)
        lead_var = round(statistics.pstdev(lead_times), 1) if len(lead_times) > 1 else 0.0

        cost_ratios = [
            (o.received_unit_cost - o.ordered_unit_cost) / o.ordered_unit_cost
            for o in obs_list if o.ordered_unit_cost > 0
        ]
        cost_stability = round(
            100 * max(0.0, 1 - (statistics.pstdev(cost_ratios) * 2 if len(cost_ratios) > 1 else 0)),
            1,
        ) if cost_ratios else 100.0

        overall = round(
            (on_time_pct * 0.35)
            + (fill_rate * 0.35)
            + (cost_stability * 0.15)
            + (_lead_variance_score(lead_var, avg_lead) * 0.15),
            1,
        )

        tier = _assign_tier(overall, on_time_pct, fill_rate)
        notes = _build_notes(
            on_time_pct=on_time_pct,
            fill_rate=fill_rate,
            lead_var=lead_var,
            avg_lead=avg_lead,
            cost_stability=cost_stability,
        )

        scorecards.append(
            SupplierScorecard(
                vendor=vendor,
                sku_count=sku_counts.get(vendor, 0),
                on_time_pct=on_time_pct,
                fill_rate_pct=fill_rate,
                avg_lead_time_days=avg_lead,
                lead_time_variance_days=lead_var,
                cost_stability_score=cost_stability,
                overall_score=overall,
                tier=tier,
                notes=notes,
            )
        )

    scorecards.sort(key=lambda s: s.overall_score, reverse=True)
    return scorecards


def _lead_variance_score(lead_var: float, avg_lead: float) -> float:
    if avg_lead <= 0:
        return 100.0
    cv = lead_var / avg_lead
    return max(0.0, 100.0 * (1 - cv))


def _assign_tier(overall: float, on_time: float, fill_rate: float) -> str:
    if overall >= 85 and on_time >= 90 and fill_rate >= 95:
        return "preferred"
    if overall >= 65:
        return "acceptable"
    return "at_risk"


def _build_notes(
    *,
    on_time_pct: float,
    fill_rate: float,
    lead_var: float,
    avg_lead: float,
    cost_stability: float,
) -> list[str]:
    notes: list[str] = []
    if on_time_pct >= 95:
        notes.append("Delivers on time consistently — safe to reduce safety stock.")
    elif on_time_pct < 75:
        notes.append(
            "Frequently late — increase safety stock buffer or consider backup vendor."
        )
    if fill_rate < 90:
        notes.append(
            f"Fill rate only {fill_rate:.0f}%. Plan for partial deliveries."
        )
    if avg_lead > 0 and lead_var / avg_lead > 0.4:
        notes.append(
            "Lead times are unpredictable — forecast confidence is lower for these SKUs."
        )
    if cost_stability < 70:
        notes.append(
            "Unit costs have drifted significantly between POs — renegotiate pricing."
        )
    if not notes:
        notes.append("No material concerns in recent POs.")
    return notes
