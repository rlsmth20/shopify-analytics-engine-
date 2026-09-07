import type { ForecastResult } from "@/lib/api-v2";

export type ForecastQuickView = "all" | "high-risk" | "at-risk" | "high-confidence";
const nonnegative = (value: unknown): number | null => typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
export const forecastNumber = (value: number | null) => value === null ? "Unknown" : value.toFixed(0);
export const forecastPercent = (value: number | null) => value === null ? "Unknown" : `${Math.round(value * 100)}%`;
export function forecastRiskPercent(value: number | null) {
  if (value === null || !Number.isFinite(value) || value < 0 || value > 1) return "Unknown";
  return Math.round(value * 100) >= 100 ? ">99%" : `${Math.round(value * 100)}%`;
}

export function forecastView(forecast: ForecastResult) {
  // Numeric zero is also the legacy placeholder for missing history. Only
  // explicit backend provenance (or an explicit demo fixture) can validate it.
  const available = forecast.forecast_available === true && forecast.demand_signal !== "missing_history";
  const measure = (value: unknown) => available ? nonnegative(value) : null;
  const risk = measure(forecast.stockout_probability_30d);
  const history = nonnegative(forecast.history_days);
  const backtest = available && forecast.demand_signal === "observed";
  const error = backtest ? nonnegative(forecast.backtest_mape_14d) : null;
  const bias = backtest && ["over_forecast", "under_forecast", "balanced"].includes(forecast.forecast_bias_14d || "")
    ? forecast.forecast_bias_14d : null;
  return {
    available,
    missingHistory: forecast.demand_signal === "missing_history",
    noRecentSales: forecast.demand_signal === "no_recent_sales",
    demand30: measure(forecast.projected_30_day_demand),
    demand60: measure(forecast.projected_60_day_demand),
    demand90: measure(forecast.projected_90_day_demand),
    risk: risk !== null && risk <= 1 ? risk : null,
    confidence: available && ["high", "medium", "low"].includes(forecast.confidence) ? forecast.confidence : "Unknown",
    history: history !== null && Number.isSafeInteger(history) ? `${history} days` : "Unknown",
    error,
    bias: bias?.replaceAll("_", " ") || "Unknown",
  };
}

export function filterForecasts(forecasts: ForecastResult[], quickView: ForecastQuickView, search: string) {
  const needle = search.trim().toLowerCase();
  return forecasts.filter(forecast => {
    if (needle && !forecast.sku_id.toLowerCase().includes(needle)) return false;
    const view = forecastView(forecast);
    if (quickView === "high-risk") return view.risk !== null && view.risk >= 0.5;
    if (quickView === "at-risk") return view.risk !== null && view.risk >= 0.2;
    if (quickView === "high-confidence") return view.available && !view.noRecentSales && view.confidence === "high";
    return true;
  });
}

export function rankForecastsByStockoutRisk(forecasts: ForecastResult[]) {
  return [...forecasts].sort((left, right) => {
    const a = forecastView(left), b = forecastView(right);
    return (b.risk ?? -1) - (a.risk ?? -1)
      || (b.demand30 ?? -1) - (a.demand30 ?? -1) || left.sku_id.localeCompare(right.sku_id);
  });
}
