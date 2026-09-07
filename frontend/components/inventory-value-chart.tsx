"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AreaLineChart } from "@/components/charts";
import { ChartCard } from "@/components/chart-card";
import { API_BASE_URL } from "@/lib/api-base";
import { currencyFormatter, numberFormatter } from "@/lib/app-helpers";
import { authenticatedFetch, isDemoActive } from "@/lib/shopify-embedded";
import { exportReportRowsCsv } from "@/lib/report-export";

type ValuePoint = { date: string; cost_value: number; retail_value: number; total_units: number };
type Metric = "cost_value" | "retail_value" | "total_units";
const METRICS: Record<Metric, string> = { cost_value: "Recorded-cost subtotal", retail_value: "At retail", total_units: "Units on hand" };

export function InventoryValueChart() {
  const [days, setDays] = useState(90);
  const [metric, setMetric] = useState<Metric>("cost_value");
  const [points, setPoints] = useState<ValuePoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sample, setSample] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const demo = isDemoActive();
    setSample(demo);
    setLoading(true);
    setError(null);
    setPoints([]);
    if (demo) {
      // Explicit sample workspace only; never used as a fallback for live data.
      const today = new Date().toISOString().slice(0, 10);
      setPoints(Array.from({ length: Math.min(days, 90) }, (_, index) => {
        const date = new Date(`${today}T00:00:00Z`);
        date.setUTCDate(date.getUTCDate() - Math.min(days, 90) + index + 1);
        const age = Math.min(days, 90) - index - 1;
        const units = Math.round(3120 + age * 7 + Math.sin(age / 8) * 80);
        return { date: date.toISOString().slice(0, 10), cost_value: units * 20, retail_value: units * 50, total_units: units };
      }));
      setLoading(false);
      return () => controller.abort();
    }
    void authenticatedFetch(`${API_BASE_URL}/analytics/inventory-value?days=${days}`, {
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(20_000)]),
    }).then(async (response) => {
      const body = await response.json().catch(() => null);
      if (!response.ok || !Array.isArray(body?.points)) throw new Error(typeof body?.detail === "string" ? body.detail : "Inventory history is temporarily unavailable.");
      if (!controller.signal.aborted) setPoints(body.points);
    }).catch(() => {
      if (!controller.signal.aborted) setError("We couldn't load inventory history. Please try again.");
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [days, attempt]);

  const format = (value: number) => metric === "total_units" ? numberFormatter.format(value) : currencyFormatter.format(value);
  const first = points[0]?.[metric];
  const latest = points.at(-1)?.[metric];
  const change = points.length > 1 && first !== undefined && first !== 0 && latest !== undefined ? (latest - first) / Math.abs(first) * 100 : null;

  return <ChartCard title="Inventory value over time" description="Track how much capital is held in stock. Switch between cost, retail value, and units to understand the change.">
    <div className="inventory-chart-controls">
      <div className="filter-row" role="group" aria-label="Inventory history period">
        {[7, 30, 90, 365].map((period) => <button key={period} type="button" className={`filter-chip${days === period ? " filter-chip-active" : ""}`} aria-pressed={days === period} onClick={() => setDays(period)}>{period === 365 ? "1 year" : `${period} days`}</button>)}
      </div>
      <label className="field-label field-label-inline"><span>Measure</span>
        <select className="input-control" value={metric} onChange={(event) => setMetric(event.target.value as Metric)}>
          {Object.entries(METRICS).map(([key, value]) => <option key={key} value={key}>{value}</option>)}
        </select>
      </label>
      <button type="button" className="button button-secondary" disabled={loading || !!error || points.length === 0} onClick={() => exportReportRowsCsv({
        filename: `skubase-inventory-${days}d${sample ? '-sample' : ''}.csv`, rows: points,
        columns: [{ label: "Date (UTC)", value: (point) => point.date }, { label: "Recorded-cost subtotal (USD)", value: (point) => point.cost_value },
          { label: "Retail value", value: (point) => point.retail_value }, { label: "Units on hand", value: (point) => point.total_units }],
      })}>Export CSV</button>
    </div>
    {sample ? <p className="section-copy">Sample inventory history · illustration only</p> : null}
    {loading ? <p className="section-copy" role="status">Loading inventory history…</p> : error ? <div role="alert"><p>{error}</p><button type="button" className="button button-secondary" onClick={() => setAttempt((previous) => previous + 1)}>Retry history</button></div> : points.length === 0 ?
      <div className="chart-history-empty"><strong>Your history starts with your first sync.</strong><p>Daily snapshots appear here once you have inventory. Past dates are not filled with estimates.</p><Link href="/store-sync" className="button button-primary">Sync Shopify inventory</Link></div> : <>
        <div className="inventory-history-summary">
          <div><span>Latest · {METRICS[metric]}</span><strong>{format(latest ?? 0)}</strong></div>
          <div><span>Change across available history</span><strong>{change === null ? "Not enough history" : `${change > 0 ? "+" : ""}${change.toFixed(1)}%`}</strong></div>
          <div><span>Daily snapshots</span><strong>{points.length}</strong></div>
        </div>
        <AreaLineChart key={`${metric}-${days}`} points={points.map((point) => ({ label: point.date, value: point[metric], x: Date.parse(`${point.date}T00:00:00Z`) }))} yFormatter={format} label={`Inventory ${METRICS[metric].toLowerCase()}`} showDataTable />
        <p className="section-copy">{points[0].date} to {points[points.length - 1].date} · UTC dates. {metric === "retail_value" ? "Retail value is potential selling value, not realized revenue." : metric === "cost_value" ? "Subtotal includes only recorded costs. Historical snapshots do not retain missing-cost coverage, so this may understate total capital and changes may reflect newly recorded costs." : "Includes the on-hand quantities captured in each snapshot."}</p>
      </>}
  </ChartCard>;
}
