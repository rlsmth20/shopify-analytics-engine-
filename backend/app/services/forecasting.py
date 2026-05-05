"""Demand forecasting service.

Uses lightweight statistical methods appropriate for most long-tail SKU histories:

* Centered moving average for noise reduction
* Exponential smoothing (Holt-style level + trend) as the headline method
* Weekly seasonality detection via ratio-to-moving-average
* Trend classification from EMA slope
* Stockout probability via normal approximation on forecast residuals

Everything is deterministic and dependency-free so it can run inline with a
single API request — heavy methods can be swapped in later behind the same
function signatures.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from app.schemas_v2 import (
    ForecastPoint,
    ForecastResult,
    SeasonalityPattern,
    TrendDirection,
)


ALPHA_LEVEL = 0.35  # smoothing constant for level
BETA_TREND = 0.18  # smoothing constant for trend
MIN_HISTORY_DAYS = 14
MAX_HISTORY_DAYS = 120
HORIZON_DAYS = 30


@dataclass(frozen=True)
class ForecastInputs:
    sku_id: str
    daily_history: list[float]  # chronologically ordered, oldest first
    on_hand: int
    start_weekday: int  # 0=Mon ... 6=Sun, the weekday for history[0]


def forecast_sku(inputs: ForecastInputs, horizon_days: int = HORIZON_DAYS) -> ForecastResult:
    history = _clean_history(inputs.daily_history)
    if len(history) < MIN_HISTORY_DAYS:
        return _naive_forecast(inputs, history, horizon_days)

    weekly_index, seasonality_pattern = _detect_weekly_seasonality(
        history, inputs.start_weekday
    )
    deseasonalized = _deseasonalize(history, weekly_index, inputs.start_weekday)

    level, trend = _holt_double_smoothing(deseasonalized)
    residuals = _residuals(deseasonalized, level, trend)
    sigma = statistics.pstdev(residuals) if len(residuals) > 2 else max(level * 0.25, 0.5)

    # Project horizon days, re-applying seasonality
    next_weekday = (inputs.start_weekday + len(history)) % 7
    points: list[ForecastPoint] = []
    for i in range(horizon_days):
        weekday = (next_weekday + i) % 7
        raw = max(level + trend * (i + 1), 0.0)
        mult = weekly_index[weekday] if weekly_index else 1.0
        expected = raw * mult
        band = 1.96 * sigma * mult
        points.append(
            ForecastPoint(
                day_offset=i + 1,
                expected_units=round(expected, 2),
                lower_bound=round(max(expected - band, 0.0), 2),
                upper_bound=round(expected + band, 2),
            )
        )

    projected_30 = _project_future_demand(
        level=level,
        trend=trend,
        weekly_index=weekly_index,
        start_weekday=next_weekday,
        days=30,
    )
    projected_60 = _project_future_demand(
        level=level,
        trend=trend,
        weekly_index=weekly_index,
        start_weekday=next_weekday,
        days=60,
    )
    projected_90 = _project_future_demand(
        level=level,
        trend=trend,
        weekly_index=weekly_index,
        start_weekday=next_weekday,
        days=90,
    )

    trend_label = _classify_trend(trend, level, residuals, sigma)
    confidence = _classify_confidence(len(history), sigma, level)
    stockout_prob = _stockout_probability(
        on_hand=inputs.on_hand,
        mean_30d=projected_30,
        sigma_per_day=sigma,
    )

    return ForecastResult(
        sku_id=inputs.sku_id,
        horizon_days=horizon_days,
        method="seasonal_ema",
        trend=trend_label,
        seasonality=seasonality_pattern,
        weekly_index=[round(x, 3) for x in weekly_index],
        confidence=confidence,
        projected_30_day_demand=round(projected_30, 1),
        projected_60_day_demand=round(projected_60, 1),
        projected_90_day_demand=round(projected_90, 1),
        stockout_probability_30d=round(stockout_prob, 3),
        points=points,
        explain=_build_explanation(
            trend_label=trend_label,
            seasonality=seasonality_pattern,
            projected_30=projected_30,
            on_hand=inputs.on_hand,
            stockout_prob=stockout_prob,
            sigma=sigma,
        ),
    )


def _clean_history(history: list[float]) -> list[float]:
    cleaned = [max(0.0, float(v)) for v in history[-MAX_HISTORY_DAYS:]]
    return cleaned


def _project_future_demand(
    *,
    level: float,
    trend: float,
    weekly_index: list[float],
    start_weekday: int,
    days: int,
) -> float:
    total = 0.0
    for i in range(days):
        weekday = (start_weekday + i) % 7
        multiplier = weekly_index[weekday] if weekly_index else 1.0
        total += max(level + trend * (i + 1), 0.0) * multiplier
    return total


def _naive_forecast(
    inputs: ForecastInputs, history: list[float], horizon_days: int
) -> ForecastResult:
    """Fallback when we don't have enough history for robust statistics."""
    avg = sum(history) / len(history) if history else 0.0
    points = [
        ForecastPoint(
            day_offset=i + 1,
            expected_units=round(avg, 2),
            lower_bound=round(max(avg * 0.6, 0.0), 2),
            upper_bound=round(avg * 1.4, 2),
        )
        for i in range(horizon_days)
    ]
    projected_30 = avg * 30
    return ForecastResult(
        sku_id=inputs.sku_id,
        horizon_days=horizon_days,
        method="naive",
        trend="steady",
        seasonality="unknown",
        weekly_index=[],
        confidence="low",
        projected_30_day_demand=round(projected_30, 1),
        projected_60_day_demand=round(avg * 60, 1),
        projected_90_day_demand=round(avg * 90, 1),
        stockout_probability_30d=round(
            _stockout_probability(
                on_hand=inputs.on_hand,
                mean_30d=projected_30,
                sigma_per_day=max(avg * 0.4, 0.5),
            ),
            3,
        ),
        points=points,
        explain=(
            "Not enough history to detect trend or seasonality — projection is a flat "
            "average of the days we do have."
        ),
    )


def _holt_double_smoothing(series: list[float]) -> tuple[float, float]:
    """Simple double-exponential smoothing. Returns final level + trend."""
    if not series:
        return 0.0, 0.0

    level = series[0]
    trend = series[1] - series[0] if len(series) > 1 else 0.0

    for value in series[1:]:
        prev_level = level
        level = ALPHA_LEVEL * value + (1 - ALPHA_LEVEL) * (level + trend)
        trend = BETA_TREND * (level - prev_level) + (1 - BETA_TREND) * trend

    return level, trend


def _residuals(series: list[float], level: float, trend: float) -> list[float]:
    """One-step-ahead residuals — cheap proxy for forecast error stddev."""
    residuals: list[float] = []
    running_level = series[0]
    running_trend = 0.0 if len(series) < 2 else series[1] - series[0]
    for i, value in enumerate(series[1:], start=1):
        prediction = running_level + running_trend
        residuals.append(value - prediction)
        prev_level = running_level
        running_level = ALPHA_LEVEL * value + (1 - ALPHA_LEVEL) * (running_level + running_trend)
        running_trend = BETA_TREND * (running_level - prev_level) + (1 - BETA_TREND) * running_trend
    return residuals


def _detect_weekly_seasonality(
    history: list[float], start_weekday: int
) -> tuple[list[float], SeasonalityPattern]:
    """Returns (weekly_index, pattern). Index is 7-long Mon..Sun multipliers."""
    if len(history) < 14:
        return [], "unknown"

    totals = [0.0] * 7
    counts = [0] * 7
    for i, value in enumerate(history):
        weekday = (start_weekday + i) % 7
        totals[weekday] += value
        counts[weekday] += 1

    means = [
        totals[i] / counts[i] if counts[i] else 0.0 for i in range(7)
    ]
    overall = sum(means) / 7 if sum(means) > 0 else 0.0
    if overall <= 0:
        return [1.0] * 7, "flat"

    index = [m / overall if overall else 1.0 for m in means]

    weekend_avg = (index[5] + index[6]) / 2  # Sat + Sun
    weekday_avg = sum(index[0:5]) / 5  # Mon..Fri
    if weekend_avg > weekday_avg * 1.15:
        pattern = "weekend_heavy"
    elif weekday_avg > weekend_avg * 1.15:
        pattern = "weekday_heavy"
    else:
        pattern = "flat"

    return index, pattern


def _deseasonalize(
    history: list[float], weekly_index: list[float], start_weekday: int
) -> list[float]:
    if not weekly_index:
        return history
    result: list[float] = []
    for i, value in enumerate(history):
        idx = weekly_index[(start_weekday + i) % 7]
        result.append(value / idx if idx > 0 else value)
    return result


def _classify_trend(
    trend: float, level: float, residuals: list[float], sigma: float
) -> TrendDirection:
    if level <= 0:
        return "steady"
    relative = trend / max(level, 0.5)

    # If noise dominates the trend, call it volatile
    if sigma > max(level, 1.0) * 0.8:
        return "volatile"

    if relative > 0.02:
        return "rising"
    if relative < -0.02:
        return "declining"
    return "steady"


def _classify_confidence(
    history_days: int, sigma: float, level: float
) -> str:
    if history_days < 21:
        return "low"
    cv = sigma / max(level, 0.5)
    if cv < 0.35 and history_days >= 60:
        return "high"
    if cv < 0.7:
        return "medium"
    return "low"


def _stockout_probability(on_hand: int, mean_30d: float, sigma_per_day: float) -> float:
    """Probability that 30-day demand exceeds on-hand, under a normal approximation."""
    if mean_30d <= 0:
        return 0.0
    sigma_30d = max(sigma_per_day * math.sqrt(30), 0.01)
    z = (on_hand - mean_30d) / sigma_30d
    return max(0.0, min(1.0, 1 - _phi(z)))


def _phi(z: float) -> float:
    """Standard normal CDF via the Abramowitz & Stegun 26.2.17 approximation."""
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _build_explanation(
    *,
    trend_label: TrendDirection,
    seasonality: SeasonalityPattern,
    projected_30: float,
    on_hand: int,
    stockout_prob: float,
    sigma: float,
) -> str:
    trend_text = {
        "rising": "Demand is trending up",
        "declining": "Demand is trending down",
        "steady": "Demand is stable",
        "volatile": "Demand is noisy and unpredictable",
    }[trend_label]

    season_text = {
        "weekend_heavy": "with stronger weekend sales",
        "weekday_heavy": "with stronger weekday sales",
        "flat": "without strong day-of-week bias",
        "unknown": "",
    }[seasonality]

    coverage_msg = (
        f"On-hand of {on_hand} covers ~{on_hand / max(projected_30 / 30, 0.01):.1f} days of expected demand."
    )
    risk_msg = (
        f"Stockout probability in the next 30 days is {stockout_prob * 100:.0f}%."
    )
    return " ".join(s for s in [trend_text + " " + season_text, coverage_msg, risk_msg] if s).strip()
