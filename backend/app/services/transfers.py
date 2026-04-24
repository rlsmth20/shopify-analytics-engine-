"""Multi-location transfer recommendations.

When the same SKU is overstocked at one location while another location is
running out, the cheapest fix is an inter-location transfer rather than a new PO.
This service pairs up imbalanced locations and emits actionable transfer lines.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas_v2 import TransferRecommendation


DAYS_OF_COVER_TARGET = 30.0
DAYS_OF_COVER_MIN = 10.0
DAYS_OF_COVER_MAX = 60.0


@dataclass(frozen=True)
class LocationStock:
    """A SKU's stock + demand at a single fulfillment location."""
    sku_id: str
    name: str
    location: str
    on_hand: int
    daily_velocity: float


def recommend_transfers(
    snapshots: list[LocationStock],
) -> list[TransferRecommendation]:
    by_sku: dict[str, list[LocationStock]] = {}
    for snap in snapshots:
        by_sku.setdefault(snap.sku_id, []).append(snap)

    recommendations: list[TransferRecommendation] = []

    for sku_id, stocks in by_sku.items():
        if len(stocks) < 2:
            continue

        # Rank locations by days of cover
        stocks_sorted = sorted(
            stocks,
            key=lambda s: (s.on_hand / s.daily_velocity) if s.daily_velocity > 0 else float("inf"),
        )
        needy = stocks_sorted[0]
        surplus = stocks_sorted[-1]

        needy_cover = _cover(needy)
        surplus_cover = _cover(surplus)

        if needy_cover >= DAYS_OF_COVER_MIN or surplus_cover <= DAYS_OF_COVER_MAX:
            continue
        if needy.daily_velocity == 0 or surplus.daily_velocity == 0:
            continue

        # Transfer just enough to get needy to target without pulling surplus below target
        needy_gap_units = max(0, int(needy.daily_velocity * DAYS_OF_COVER_TARGET) - needy.on_hand)
        surplus_excess_units = max(
            0, surplus.on_hand - int(surplus.daily_velocity * DAYS_OF_COVER_TARGET)
        )
        transfer_qty = min(needy_gap_units, surplus_excess_units)
        if transfer_qty <= 0:
            continue

        needy_after = (needy.on_hand + transfer_qty) / max(needy.daily_velocity, 0.01)
        surplus_after = (surplus.on_hand - transfer_qty) / max(surplus.daily_velocity, 0.01)

        recommendations.append(
            TransferRecommendation(
                sku_id=sku_id,
                name=surplus.name,
                from_location=surplus.location,
                to_location=needy.location,
                qty=transfer_qty,
                from_days_of_cover_before=round(surplus_cover, 1),
                to_days_of_cover_before=round(needy_cover, 1),
                from_days_of_cover_after=round(surplus_after, 1),
                to_days_of_cover_after=round(needy_after, 1),
                rationale=(
                    f"Move {transfer_qty} units from {surplus.location} "
                    f"({surplus_cover:.0f} days cover) to {needy.location} "
                    f"({needy_cover:.0f} days cover) to rebalance toward a "
                    f"{int(DAYS_OF_COVER_TARGET)}-day target."
                ),
            )
        )

    recommendations.sort(key=lambda r: -r.qty)
    return recommendations


def _cover(snap: LocationStock) -> float:
    if snap.daily_velocity <= 0:
        return 999.0
    return snap.on_hand / snap.daily_velocity


# Demo data for MVP / preview; real ingest will replace this with Shopify location data
DEMO_LOCATION_STOCKS: list[LocationStock] = [
    LocationStock("sku_athletic-tee-black-m", "Athletic Tee / Black / M", "Warehouse A (East)", 24, 4.0),
    LocationStock("sku_athletic-tee-black-m", "Athletic Tee / Black / M", "Warehouse B (West)", 180, 1.5),
    LocationStock("sku_heritage-hoodie-charcoal-l", "Heritage Hoodie / Charcoal / L", "Warehouse A (East)", 9, 2.5),
    LocationStock("sku_heritage-hoodie-charcoal-l", "Heritage Hoodie / Charcoal / L", "Warehouse B (West)", 140, 0.8),
    LocationStock("sku_mesh-short-navy-l", "Mesh Short / Navy / L", "Warehouse A (East)", 65, 2.6),
    LocationStock("sku_mesh-short-navy-l", "Mesh Short / Navy / L", "Warehouse B (West)", 6, 1.9),
    LocationStock("sku_crop-hoodie-rose-s", "Crop Hoodie / Rose / S", "Warehouse A (East)", 6, 2.2),
    LocationStock("sku_crop-hoodie-rose-s", "Crop Hoodie / Rose / S", "Warehouse B (West)", 88, 0.9),
]
