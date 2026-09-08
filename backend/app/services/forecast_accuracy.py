"""Forecast backtesting helpers."""
from __future__ import annotations

from dataclasses import dataclass

from app.services.forecasting import ForecastInputs, forecast_sku, observed_history


@dataclass(frozen=True)
class ForecastBacktest:
    mae_14d: float | None
    mape_14d: float | None
    bias_14d: str | None
    trust_reasons: list[str]


def backtest_forecast(inputs: ForecastInputs, days: int = 14) -> ForecastBacktest:
    if inputs.identity_ambiguous:
        return ForecastBacktest(None, None, None, [inputs.identity_warning or "SKU identity needs review before backtesting."])
    history, start_weekday = observed_history(inputs)
    if len(history) < days + 21:
        return ForecastBacktest(
            mae_14d=None,
            mape_14d=None,
            bias_14d=None,
            trust_reasons=[f"Backtest needs at least {days + 21} days of observed sales history; unobserved days are not zero-sales evidence."],
        )

    training = history[:-days]
    actual = history[-days:]
    forecast = forecast_sku(
        ForecastInputs(
            sku_id=inputs.sku_id,
            daily_history=training,
            on_hand=inputs.on_hand,
            start_weekday=start_weekday,
            observed_history_days=len(training),
            source_warnings=inputs.source_warnings,
        ),
        horizon_days=days,
    )
    predicted = [point.expected_units for point in forecast.points[:days]]
    if not forecast.forecast_available or not predicted:
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
    if total_actual <= 0:
        return ForecastBacktest(mae_14d=round(mae, 2), mape_14d=None, bias_14d=None,
            trust_reasons=["The observed comparison window has no recorded sales. Absolute error is descriptive; percentage accuracy and directional bias are unavailable."])
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
    if inputs.source_warnings:
        reasons.extend(inputs.source_warnings)
        reasons.append("Backtest uses imported history whose coverage needs review; these errors do not verify current demand.")
    elif sum(value > 0 for value in history) / len(history) < 0.2:
        reasons.append("Observed demand is sparse; these errors do not establish reliable forecast accuracy.")
    elif mape <= 0.25:
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
