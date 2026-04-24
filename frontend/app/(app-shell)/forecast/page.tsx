"use client";

import { useEffect, useMemo, useState } from "react";

import {
  ChartPanel,
  ForecastBandChart,
  WeekdayIndexBars,
} from "@/components/charts";
import {
  fetchForecasts,
  percent,
  type ForecastResult,
} from "@/lib/api-v2";

export default function ForecastPage() {
  const [forecasts, setForecasts] = useState<ForecastResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchForecasts(controller.signal)
      .then((res) => {
        setForecasts(res.forecasts);
        setSelectedId(res.forecasts[0]?.sku_id ?? null);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const selected = useMemo(
    () => forecasts.find((f) => f.sku_id === selectedId) ?? null,
    [forecasts, selectedId]
  );

  if (loading && forecasts.length === 0) {
    return <div className="page-loading">Computing forecasts…</div>;
  }
  if (error) return <p className="page-error-copy">{error}</p>;

  return (
    <div className="forecast-page">
      <aside className="forecast-list">
        <h3 className="panel-section-title">SKUs</h3>
        <p className="panel-section-subtitle">Ranked by stockout probability</p>
        <ul className="sku-list">
          {forecasts.map((f) => (
            <li
              key={f.sku_id}
              className={`sku-list-row${
                f.sku_id === selectedId ? " sku-list-row-active" : ""
              }`}
            >
              <button
                type="button"
                onClick={() => setSelectedId(f.sku_id)}
                className="sku-list-button"
              >
                <div className="sku-list-name">{f.sku_id.replace(/^sku_/, "")}</div>
                <div className="sku-list-meta">
                  <span className={`trend-pill trend-${f.trend}`}>{f.trend}</span>
                  <span
                    className={`risk-pill risk-${
                      f.stockout_probability_30d > 0.5
                        ? "high"
                        : f.stockout_probability_30d > 0.2
                        ? "medium"
                        : "low"
                    }`}
                  >
                    {percent(f.stockout_probability_30d, 0)} risk
                  </span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="forecast-detail">
        {selected ? (
          <>
            <div className="forecast-kpis">
              <Kpi label="30-day demand" value={selected.projected_30_day_demand.toFixed(0)} />
              <Kpi label="60-day demand" value={selected.projected_60_day_demand.toFixed(0)} />
              <Kpi label="90-day demand" value={selected.projected_90_day_demand.toFixed(0)} />
              <Kpi
                label="Stockout risk (30d)"
                value={percent(selected.stockout_probability_30d, 0)}
                tone={
                  selected.stockout_probability_30d > 0.5
                    ? "negative"
                    : selected.stockout_probability_30d > 0.2
                    ? "neutral"
                    : "positive"
                }
              />
              <Kpi label="Confidence" value={selected.confidence} />
              <Kpi label="Method" value={selected.method.replace("_", " ")} />
            </div>

            <ChartPanel
              title={`Forecast · ${selected.sku_id.replace(/^sku_/, "")}`}
              subtitle={selected.explain}
              accent="primary"
            >
              <ForecastBandChart points={selected.points} />
            </ChartPanel>

            {selected.weekly_index.length > 0 ? (
              <ChartPanel
                title="Weekly seasonality"
                subtitle={`Detected pattern: ${selected.seasonality.replace("_", " ")}`}
              >
                <WeekdayIndexBars index={selected.weekly_index} />
              </ChartPanel>
            ) : null}
          </>
        ) : (
          <p className="muted">Select a SKU on the left.</p>
        )}
      </section>
    </div>
  );
}

function Kpi({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "positive" | "negative" | "neutral";
}) {
  return (
    <div className={`kpi-card kpi-tone-${tone}`}>
      <p className="kpi-label">{label}</p>
      <p className="kpi-value">{value}</p>
    </div>
  );
}
