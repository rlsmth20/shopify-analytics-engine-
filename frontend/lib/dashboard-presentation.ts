import type { DashboardSeriesPoint } from "@/lib/api-v2";

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

export function formatDashboardMoney(value: number): string {
  return Number.isFinite(value) ? money.format(value) : "Unavailable";
}

export function formatForecastVariance(value: number): string {
  if (!Number.isFinite(value)) return "Unavailable";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

// The dashboard API returns completed UTC days as positive day offsets,
// oldest first. Anchor labels to the response, never to the viewer's clock.
export function labelRevenueDays(points: DashboardSeriesPoint[], generatedAt: string): DashboardSeriesPoint[] {
  const generated = new Date(generatedAt);
  if (!Number.isFinite(generated.getTime())) return points;
  const anchor = Date.UTC(generated.getUTCFullYear(), generated.getUTCMonth(), generated.getUTCDate());
  const formatter = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  return points.map((point) => {
    const offset = Number(point.label);
    if (!/^\d+$/.test(point.label) || !Number.isInteger(offset) || offset < 1 || offset > 366) return point;
    return { ...point, label: formatter.format(new Date(anchor - offset * 86_400_000)) };
  });
}

export function dashboardKpiNote(label: string): string {
  const notes: Record<string, string> = {
    "Revenue (30d)": "30-day units sold × current catalog prices",
    "Inventory value": "Current on-hand inventory at cost",
    "Cash tied up": "Capital in optimize and dead-stock items",
    "Profit at risk": "Estimated exposure from urgent items",
    "Urgent SKUs": "Items requiring replenishment review",
    "Dead SKUs": "Stale inventory requiring recovery review",
  };
  return notes[label] ?? "Current inventory snapshot";
}
