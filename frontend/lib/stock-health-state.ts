export type StockoutRiskLevel = "Critical" | "High" | "Medium" | "Low" | "Unknown";

export function finiteNonnegative(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

export function stockoutRiskLevel(daysLeft: number | null | undefined, leadDays: number | null | undefined): StockoutRiskLevel {
  if (!finiteNonnegative(daysLeft) || !finiteNonnegative(leadDays) || leadDays === 0) return "Unknown";
  if (daysLeft <= leadDays) return "Critical";
  if (daysLeft <= leadDays + 7) return "High";
  if (daysLeft <= leadDays + 14) return "Medium";
  return "Low";
}

export function stockCoverageGeometry(coverDays: number | null, leadDays?: number | null, targetDays?: number | null) {
  if (!finiteNonnegative(coverDays)) return { fill: null, lead: null, target: null };
  const lead = finiteNonnegative(leadDays) ? leadDays : null;
  const target = finiteNonnegative(targetDays) ? targetDays : null;
  const maximum = Math.max(coverDays, lead ?? 0, target ?? 0, 30);
  return {
    fill: coverDays / maximum * 100,
    lead: lead === null ? null : Math.min(lead / maximum * 100, 98),
    target: target === null ? null : Math.min(target / maximum * 100, 98),
  };
}
