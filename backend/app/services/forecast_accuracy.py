"""Forecast backtesting helpers."""
from __future__ import annotations

from dataclasses import dataclass

from app.services.forecasting import ForecastInputs, forecast_sku


@dataclass(frozen=True)
class ForecastBacktest:
    mae_14d: float | None
    mape_14d: float | None
    bias_14d: str | None
    trust_reasons: list[str]


def backtest_forecast(inputs: ForecastInputs, days: int = 14) -> ForecastBacktest:
    history = [max(0.0, float(value)) for value in inputs.daily_history]
    if len(history) < days + 21:
        return ForecastBacktest(
            mae_14d=None,
            mape_14d=None,
            bias_14d=None,
            trust_reasons=["Backtest needs at least 35 days of sales history."],
        )

    training = history[:-days]
    actual = history[-days:]
    forecast = forecast_sku(
        ForecastInputs(
            sku_id=inputs.sku_id,
            daily_history=training,
            on_hand=inputs.on_hand,
            start_weekday=inputs.start_weekday,
        ),
        horizon_days=days,
    )
    predicted = [point.expected_units for point in forecast.points[:days]]
    if not predicted:
        return ForecastBacktest(
            mae_14d=None,
            mape_14d=None,
            bias_14d=None,
            trust_reasons=["Backtest could not produce comparison points."],
        )

    errors = [pred - act for pred, act in zip(predicted, actual)]
    abs_errors = [abs(error) for error in errors]
    mae = sum(abs_errors) / len(abs_errors)
    total_actual = sum(actual)
    mape = sum(abs(error) / max(act, 1.0) for error, act in zip(errors, actual)) / len(errors)
    net_error = sum(errors)
    bias = "balanced"
    if total_actual > 0:
        ratio = net_error / total_actual
        if ratio > 0.15:
            bias = "over_forecast"
        elif ratio < -0.15:
            bias = "under_forecast"

    reasons: list[str] = []
    if mape <= 0.25:
        reasons.append("Backtest error is low over the last 14 days.")
    elif mape <= 0.5:
        reasons.append("Backtest error is moderate; review larger buys.")
    else:
        reasons.append("Backtest error is high; treat this forecast as directional.")
    if bias == "over_forecast":
        reasons.append("Recent backtest over-forecasted demand.")
    elif bias == "under_forecast":
        reasons.append("Recent backtest under-forecasted demand.")
    else:
        reasons.append("Recent backtest bias is balanced.")

    return ForecastBacktest(
        mae_14d=round(mae, 2),
        mape_14d=round(mape, 3),
        bias_14d=bias,
        trust_reasons=reasons,
    )
