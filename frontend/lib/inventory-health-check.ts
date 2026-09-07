/** Browser-only diagnostic. This deliberately does not place or size purchase orders. */
export const HEALTH_CHECK_MAX_BYTES = 500_000;
export const HEALTH_CHECK_MAX_ROWS = 1_000;
export const HEALTH_CHECK_TEMPLATE = "sku,on_hand,units_sold,unit_cost,lead_time_days,safety_stock\nEXAMPLE-FAST,18,90,12,14,5\nEXAMPLE-SLOW,180,12,8,21,5\nEXAMPLE-NO-SALES,24,0,,14,0\n";

export type HealthSettings = { salesDays: number; defaultLeadDays: number; targetCoverDays: number };
export type HealthStatus = "stockout_risk" | "reorder_review" | "excess_stock" | "no_recent_sales" | "within_range";
export type HealthRow = {
  sku: string; onHand: number; unitsSold: number; unitCost: number | null; leadDays: number; safetyStock: number;
  dailySales: number; daysCover: number | null; reorderPoint: number; excessUnits: number | null;
  excessCost: number | null; status: HealthStatus;
};
export type HealthResult = { rows: HealthRow[]; errors: string[] };

export const HEALTH_STATUS: Record<HealthStatus, { label: string; priority: number; action: string }> = {
  stockout_risk: { label: "Stockout risk", priority: 0, action: "Current stock may run out before a normal replenishment arrives. Check incoming delivery dates and current demand." },
  reorder_review: { label: "Review a reorder", priority: 1, action: "At or below the reorder trigger. Check open orders, committed stock and supplier minimums before purchasing." },
  excess_stock: { label: "Above target cover", priority: 2, action: "Stock exceeds your chosen cover target. Review demand changes and planned promotions before buying more." },
  no_recent_sales: { label: "No recorded sales", priority: 3, action: "Check whether this is a new, seasonal or previously unavailable item. Zero recorded sales alone do not prove dead stock." },
  within_range: { label: "Within chosen range", priority: 4, action: "Keep monitoring sales and lead times. This result does not account for future promotions or demand changes." },
};

function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [], value = "", quoted = false, closed = false;
  const source = text.replace(/^\uFEFF/, "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  for (let i = 0; i < source.length; i++) {
    const char = source[i];
    if (quoted) {
      if (char === '"' && source[i + 1] === '"') { value += '"'; i++; }
      else if (char === '"') { quoted = false; closed = true; }
      else value += char;
    } else if (char === '"') {
      if (value.trim() || closed) throw new Error("Unexpected quote. Use a CSV export with quoted fields escaped correctly.");
      value = ""; quoted = true;
    } else if (char === "," || char === "\n") {
      row.push(value.trim()); value = ""; closed = false;
      if (char === "\n") { if (row.some(Boolean)) rows.push(row); row = []; }
    } else {
      if (closed && char.trim()) throw new Error("Unexpected text after a closing quote.");
      value += char;
    }
  }
  if (quoted) throw new Error("A quoted field is unfinished. Check the CSV and try again.");
  row.push(value.trim());
  if (row.some(Boolean)) rows.push(row);
  return rows;
}

function numeric(value: string | undefined, optional = false): number | null {
  if (!value?.trim()) return optional ? null : NaN;
  if (!/^\d+(?:\.\d+)?$/.test(value)) return NaN;
  const number = Number(value);
  return Number.isFinite(number) && number <= 10_000_000 ? number : NaN;
}

export function analyzeInventoryHealth(csv: string, settings: HealthSettings): HealthResult {
  const failure = (message: string): HealthResult => ({ rows: [], errors: [message] });
  if (new TextEncoder().encode(csv).byteLength > HEALTH_CHECK_MAX_BYTES) return failure("Use a CSV smaller than 500 KB.");
  if (![settings.salesDays, settings.defaultLeadDays, settings.targetCoverDays].every(n => Number.isInteger(n) && n >= 1 && n <= 3650)) {
    return failure("Enter a sales period, lead time and cover target in whole days from 1 to 3,650.");
  }
  if (settings.targetCoverDays < settings.defaultLeadDays) return failure("Target cover must be at least your default supplier lead time.");
  let input: string[][];
  try { input = parseCsv(csv); } catch (error) { return failure(error instanceof Error ? error.message : "Could not read this CSV."); }
  if (input.length < 2) return failure("Paste your header and at least one SKU, or try the sample data.");
  if (input.length - 1 > HEALTH_CHECK_MAX_ROWS) return failure("Check up to 1,000 SKUs at a time.");
  const headers = input[0].map(s => s.toLowerCase().replace(/\s+/g, "_"));
  if (new Set(headers).size !== headers.length) return failure("Each CSV column needs a unique header.");
  for (const required of ["sku", "on_hand", "units_sold"]) {
    if (!headers.includes(required)) return failure(`Missing ${required} column. Use the summary template; raw order exports need to be aggregated first.`);
  }
  const rows: HealthRow[] = [], errors: string[] = [], seen = new Set<string>();
  for (const [index, cells] of input.slice(1).entries()) {
    const field = (name: string) => cells[headers.indexOf(name)];
    const sku = field("sku") || "";
    const onHand = numeric(field("on_hand")), unitsSold = numeric(field("units_sold"));
    const unitCost = numeric(field("unit_cost"), true);
    const leadDays = numeric(field("lead_time_days"), true) ?? settings.defaultLeadDays;
    const safetyStock = numeric(field("safety_stock"), true) ?? 0;
    let issue = "";
    if (cells.length !== headers.length) issue = "column count does not match the header";
    else if (!sku || sku.length > 120) issue = "SKU must contain 1–120 characters";
    else if (seen.has(sku.toLowerCase())) issue = `duplicate SKU ${sku}; combine locations or use distinct variant IDs`;
    else if ([onHand, unitsSold, unitCost, leadDays, safetyStock].some(n => n !== null && !Number.isFinite(n))) issue = "use plain nonnegative numbers; leave unknown unit costs blank";
    else if (leadDays > 3650) issue = "lead time must be at most 3,650 days";
    else if (settings.targetCoverDays < leadDays) issue = "cover target is shorter than this SKU's lead time";
    if (issue) { if (errors.length < 8) errors.push(`Data row ${index + 1}: ${issue}.`); continue; }
    seen.add(sku.toLowerCase());
    const dailySales = unitsSold! / settings.salesDays;
    const daysCover = dailySales > 0 ? onHand! / dailySales : null;
    const reorderPoint = Math.ceil(dailySales * leadDays + safetyStock);
    const excessUnits = dailySales > 0 ? Math.max(0, onHand! - Math.ceil(dailySales * settings.targetCoverDays + safetyStock)) : null;
    const status: HealthStatus = dailySales === 0 ? "no_recent_sales" : daysCover! < leadDays ? "stockout_risk"
      : onHand! <= reorderPoint ? "reorder_review" : excessUnits! > 0 ? "excess_stock" : "within_range";
    rows.push({ sku, onHand: onHand!, unitsSold: unitsSold!, unitCost, leadDays, safetyStock, dailySales, daysCover,
      reorderPoint, excessUnits, excessCost: excessUnits === null || unitCost === null ? null : excessUnits * unitCost, status });
  }
  // Never quietly analyze only the easy rows of a malformed inventory file.
  return errors.length ? { rows: [], errors } : { rows: rows.sort((a, b) => HEALTH_STATUS[a.status].priority - HEALTH_STATUS[b.status].priority ||
    (a.daysCover ?? Infinity) - (b.daysCover ?? Infinity) || a.sku.localeCompare(b.sku)), errors: [] };
}

export function healthResultsCsv(rows: HealthRow[], currency = "USD", settings?: HealthSettings): string {
  const cell = (value: string | number | null) => {
    let text = value === null ? "" : String(value);
    if (/^[=+@\-\t\r]/.test(text)) text = "'" + text;
    return '"' + text.replace(/"/g, '""') + '"';
  };
  const costCurrency = ["USD", "CAD", "GBP", "EUR", "AUD", "NZD"].includes(currency) ? currency : "UNKNOWN";
  const header = ["sku", "status", "on_hand", "units_sold", "days_cover", "reorder_trigger_units", "above_target_units", "above_target_cost", "review_action",
    "cost_currency", "sales_period_days", "target_cover_days", "lead_time_days", "safety_stock_units", "unit_cost"];
  const data = rows.map(r => [r.sku, HEALTH_STATUS[r.status].label, r.onHand, r.unitsSold,
    r.daysCover === null ? null : Math.round(r.daysCover * 10) / 10, r.unitsSold === 0 ? null : r.reorderPoint, r.excessUnits,
    r.excessCost === null ? null : Math.round(r.excessCost * 100) / 100, HEALTH_STATUS[r.status].action,
    costCurrency, settings?.salesDays ?? null, settings?.targetCoverDays ?? null, r.leadDays, r.safetyStock, r.unitCost]);
  return [header, ...data].map(row => row.map(cell).join(",")).join("\r\n");
}

export function containsSampleHealthRows(rows: HealthRow[]): boolean {
  // Template round trips and lightly edited examples are still demonstrations.
  return rows.some(row => /^EXAMPLE-/i.test(row.sku));
}
