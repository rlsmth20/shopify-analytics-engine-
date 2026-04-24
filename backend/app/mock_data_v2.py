"""Extended mock data to power v2 features.

Adds:
* 90-day daily sales history per SKU (with weekly seasonality + trend)
* Supplier PO observations (for scorecards)
* Deterministic data — same output every run
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from app.mock_data import MOCK_SKUS
from app.services.supplier_scoring import SupplierObservation


@dataclass(frozen=True)
class SkuSalesPattern:
    sku_id: str
    mean_daily: float
    trend_per_day: float  # e.g., 0.02 = 2% growth per day
    weekly_index: tuple[float, float, float, float, float, float, float]
    noise_scale: float
    dead_after_day: int | None = None  # For dead-stock SKUs, sales stop after this day


# Pre-computed patterns per SKU. Values align with the classifications each
# mock SKU is expected to produce in the v1 engine.
_SKU_PATTERNS: dict[str, SkuSalesPattern] = {
    # Urgent SKUs — strong recent velocity
    "sku_athletic-tee-black-m": SkuSalesPattern(
        sku_id="sku_athletic-tee-black-m",
        mean_daily=4.0,
        trend_per_day=0.012,
        weekly_index=(0.9, 0.9, 0.95, 1.0, 1.15, 1.25, 0.85),
        noise_scale=0.35,
    ),
    "sku_ribbed-tank-ivory-s": SkuSalesPattern(
        sku_id="sku_ribbed-tank-ivory-s",
        mean_daily=3.0,
        trend_per_day=0.008,
        weekly_index=(1.0, 1.0, 1.0, 0.95, 1.1, 1.25, 0.7),
        noise_scale=0.3,
    ),
    "sku_heritage-hoodie-charcoal-l": SkuSalesPattern(
        sku_id="sku_heritage-hoodie-charcoal-l",
        mean_daily=2.5,
        trend_per_day=0.015,
        weekly_index=(0.95, 1.0, 1.0, 1.0, 1.1, 1.2, 0.75),
        noise_scale=0.4,
    ),
    "sku_crop-hoodie-rose-s": SkuSalesPattern(
        sku_id="sku_crop-hoodie-rose-s",
        mean_daily=2.2,
        trend_per_day=0.02,
        weekly_index=(0.9, 1.0, 1.05, 1.0, 1.1, 1.3, 0.65),
        noise_scale=0.45,
    ),
    # Optimize SKUs — strong but steady
    "sku_mesh-short-navy-l": SkuSalesPattern(
        sku_id="sku_mesh-short-navy-l",
        mean_daily=2.6,
        trend_per_day=0.002,
        weekly_index=(0.95, 0.95, 1.0, 1.0, 1.05, 1.2, 0.85),
        noise_scale=0.3,
    ),
    "sku_fleece-jogger-stone-m": SkuSalesPattern(
        sku_id="sku_fleece-jogger-stone-m",
        mean_daily=1.5,
        trend_per_day=-0.005,
        weekly_index=(1.0, 1.0, 1.0, 0.95, 1.05, 1.15, 0.85),
        noise_scale=0.35,
    ),
    "sku_canvas-tote-olive": SkuSalesPattern(
        sku_id="sku_canvas-tote-olive",
        mean_daily=1.0,
        trend_per_day=-0.008,
        weekly_index=(1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 0.9),
        noise_scale=0.5,
    ),
    "sku_wool-beanie-rust": SkuSalesPattern(
        sku_id="sku_wool-beanie-rust",
        mean_daily=0.6,
        trend_per_day=-0.02,
        weekly_index=(1.0, 1.0, 1.0, 0.95, 1.0, 1.15, 0.9),
        noise_scale=0.7,
    ),
    "sku_vintage-cap-forest": SkuSalesPattern(
        sku_id="sku_vintage-cap-forest",
        mean_daily=0.4,
        trend_per_day=-0.015,
        weekly_index=(1.0, 1.0, 1.0, 1.0, 1.1, 1.15, 0.75),
        noise_scale=0.9,
    ),
    # Dead-stock SKUs — sales taper to zero
    "sku_longline-tee-white-xl": SkuSalesPattern(
        sku_id="sku_longline-tee-white-xl",
        mean_daily=0.25,
        trend_per_day=-0.03,
        weekly_index=(1.0, 1.0, 1.0, 1.0, 1.0, 1.05, 0.95),
        noise_scale=0.8,
        dead_after_day=68,
    ),
    "sku_sherpa-vest-sand-xl": SkuSalesPattern(
        sku_id="sku_sherpa-vest-sand-xl",
        mean_daily=0.15,
        trend_per_day=-0.04,
        weekly_index=(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
        noise_scale=1.0,
        dead_after_day=35,
    ),
    "sku_archived-crew-sage-xs": SkuSalesPattern(
        sku_id="sku_archived-crew-sage-xs",
        mean_daily=0.0,
        trend_per_day=0.0,
        weekly_index=(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
        noise_scale=0.0,
        dead_after_day=0,
    ),
}


def daily_history_for_sku(sku_id: str, days: int = 90) -> list[float]:
    """Return a deterministic 90-day daily sales history."""
    pattern = _SKU_PATTERNS.get(sku_id)
    if pattern is None:
        # Fallback: flat 1 unit/day average, low noise.
        rng = random.Random(hash(sku_id) & 0xFFFFFFFF)
        return [max(0.0, 1.0 + rng.uniform(-0.3, 0.3)) for _ in range(days)]

    rng = random.Random(hash(sku_id) & 0xFFFFFFFF)
    out: list[float] = []
    for day_index in range(days):
        if pattern.dead_after_day is not None and day_index >= pattern.dead_after_day:
            out.append(0.0)
            continue
        base = pattern.mean_daily * math.exp(pattern.trend_per_day * (day_index - days / 2))
        weekday = day_index % 7  # 0=Mon..6=Sun
        seasonal = pattern.weekly_index[weekday]
        noise = 1 + rng.uniform(-pattern.noise_scale, pattern.noise_scale) * 0.5
        out.append(max(0.0, base * seasonal * noise))
    return out


def start_weekday_for_history() -> int:
    """Anchor weekday for the oldest day in a 90-day window.

    Held constant so forecasts are deterministic across runs.
    """
    return 2  # Wednesday


def recent_daily_revenue(days: int = 30) -> list[tuple[int, float]]:
    """Day-offset + total revenue across all SKUs for dashboard trends."""
    daily_totals: list[float] = [0.0] * days
    for sku in MOCK_SKUS:
        history = daily_history_for_sku(sku.sku_id, days=days)
        for i, units in enumerate(history):
            daily_totals[i] += units * sku.price
    return [(i - (days - 1), round(total, 2)) for i, total in enumerate(daily_totals)]


def supplier_observations() -> list[SupplierObservation]:
    """Deterministic sample PO observations for scorecard demo."""
    return [
        # Strong performer
        SupplierObservation("Harbor Goods", 11, 11, 200, 200, 14.0, 14.0),
        SupplierObservation("Harbor Goods", 11, 12, 180, 180, 14.0, 14.5),
        SupplierObservation("Harbor Goods", 11, 10, 220, 220, 14.0, 14.0),
        SupplierObservation("Harbor Goods", 11, 11, 150, 148, 14.5, 14.5),
        # Acceptable
        SupplierObservation("Coastal Basics", 14, 16, 150, 145, 9.0, 9.2),
        SupplierObservation("Coastal Basics", 14, 14, 120, 120, 9.0, 9.0),
        SupplierObservation("Coastal Basics", 14, 18, 150, 140, 9.0, 9.4),
        # At risk — frequently late, fill rate dropping
        SupplierObservation("Summit Sportswear", 19, 26, 100, 85, 24.0, 25.0),
        SupplierObservation("Summit Sportswear", 19, 24, 120, 95, 24.0, 26.5),
        SupplierObservation("Summit Sportswear", 19, 22, 90, 80, 24.0, 25.5),
        SupplierObservation("Summit Sportswear", 19, 28, 100, 70, 24.0, 27.0),
        # Preferred
        SupplierObservation("Northstar Apparel", 16, 15, 240, 240, 11.0, 11.0),
        SupplierObservation("Northstar Apparel", 16, 16, 200, 200, 11.0, 11.0),
        SupplierObservation("Northstar Apparel", 16, 15, 180, 180, 11.0, 11.0),
        # Mid
        SupplierObservation("Atlas Carry", 12, 13, 200, 190, 13.0, 13.0),
        SupplierObservation("Atlas Carry", 12, 14, 200, 195, 13.0, 13.2),
        # Slipping
        SupplierObservation("Trailhead Accessories", 22, 30, 80, 70, 8.0, 8.8),
        SupplierObservation("Trailhead Accessories", 22, 28, 80, 60, 8.0, 9.0),
        # Niche / small batch
        SupplierObservation("Peak Outerwear", 18, 20, 50, 48, 34.0, 34.5),
        SupplierObservation("Civic Merch", 10, 10, 100, 100, 10.0, 10.0),
        SupplierObservation("Open Loom", 15, 17, 60, 55, 12.0, 12.4),
        SupplierObservation("Legacy Mills", 25, 32, 80, 70, 21.0, 22.5),
    ]
