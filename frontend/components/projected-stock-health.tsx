"use client";

export type StockHealthStatus =
  | "Healthy"
  | "Watch"
  | "At risk"
  | "Stockout risk"
  | "Overstock"
  | "Dead stock";

type RiskLevel = "Critical" | "High" | "Medium" | "Low" | string;

export type ProjectedStockHealthProps = {
  productName?: string;
  sku?: string;
  currentStock?: number | null;
  dailyVelocity?: number | null;
  salesLast30Days?: number | null;
  daysLeft?: number | null;
  daysOfInventory?: number | null;
  leadTimeDays?: number | null;
  targetCoverageDays?: number | null;
  stockoutDate?: string | null;
  recommendedQty?: number | null;
  recommendedAction?: string | null;
  riskLevel?: RiskLevel | null;
  status?: StockHealthStatus | string | null;
  inventoryValue?: number | null;
  cashImpact?: number | null;
  confidence?: string | null;
  dataQualityNote?: string | null;
  daysSinceLastSale?: number | null;
  compact?: boolean;
  hideMetricGrid?: boolean;
  hideIdentity?: boolean;
  hideActionText?: boolean;
  showAdvancedDetails?: boolean;
  context?: "action" | "report" | "forecast" | "po";
};

export function ProjectedStockHealth({
  productName,
  sku,
  currentStock,
  dailyVelocity,
  salesLast30Days,
  daysLeft,
  daysOfInventory,
  leadTimeDays,
  targetCoverageDays,
  stockoutDate,
  recommendedQty,
  recommendedAction,
  riskLevel,
  status,
  inventoryValue,
  cashImpact,
  confidence,
  dataQualityNote,
  daysSinceLastSale,
  compact = false,
  hideMetricGrid = false,
  hideIdentity = false,
  hideActionText = false,
  showAdvancedDetails = true,
  context,
}: ProjectedStockHealthProps) {
  const coverDays = firstFinite(daysLeft, daysOfInventory);
  const health = normalizeStatus(
    status,
    riskLevel,
    currentStock,
    dailyVelocity,
    coverDays,
    leadTimeDays,
    targetCoverageDays,
    daysSinceLastSale,
  );
  const explanation = buildExplanation({
    health,
    currentStock,
    dailyVelocity,
    coverDays,
    leadTimeDays,
    targetCoverageDays,
    daysSinceLastSale,
  });
  const coveragePct = healthBarPercent(coverDays, targetCoverageDays, leadTimeDays);
  const leadPct = markerPercent(leadTimeDays, targetCoverageDays, coverDays);
  const targetPct = markerPercent(targetCoverageDays, targetCoverageDays, coverDays);

  return (
    <section
      className={`stock-health stock-health-${toneForStatus(health)}${compact ? " stock-health-compact" : ""}${context ? ` stock-health-context-${context}` : ""}`}
    >
      <div className="stock-health-head">
        {hideIdentity ? <span className="stock-health-context-label">Stock health</span> : (
          <div>
            {productName ? <p className="stock-health-product">{productName}</p> : null}
            {sku ? <p className="stock-health-sku">{sku}</p> : null}
          </div>
        )}
        <span className={`stock-health-badge stock-health-badge-${toneForStatus(health)}`}>
          {health}
        </span>
      </div>

      <div className="stock-health-bar" aria-label="Stock cover compared with lead time and target coverage">
        <span className="stock-health-fill" style={{ width: `${coveragePct}%` }} />
        {leadPct !== null ? <span className="stock-health-marker stock-health-marker-lead" style={{ left: `${leadPct}%` }} /> : null}
        {targetPct !== null ? <span className="stock-health-marker stock-health-marker-target" style={{ left: `${targetPct}%` }} /> : null}
      </div>
      <div className="stock-health-scale">
        <span>Now</span>
        <span>{leadTimeDays !== null && isFiniteNumber(leadTimeDays) ? `Lead time ${formatNumber(leadTimeDays)}d` : "Lead time unavailable"}</span>
        <span>{targetCoverageDays !== null && isFiniteNumber(targetCoverageDays) ? `Target ${formatNumber(targetCoverageDays)}d` : "Target unavailable"}</span>
      </div>

      <p className="stock-health-explanation">{explanation}</p>

      {hideMetricGrid || !showAdvancedDetails ? null : (
        <details className="stock-health-details">
          <summary>Details</summary>
          <dl>
            <Detail label="Current stock" value={formatNumber(currentStock)} />
            <Detail label="Daily velocity" value={formatVelocity(dailyVelocity)} />
            <Detail label="Sales last 30 days" value={formatNumber(salesLast30Days)} />
            <Detail label="Days left / cover" value={formatDays(coverDays)} />
            <Detail label="Lead time" value={formatDays(leadTimeDays)} />
            <Detail label="Target coverage" value={formatDays(targetCoverageDays)} />
            <Detail label="Recommended qty" value={formatNumber(recommendedQty)} />
            <Detail label="Estimated stockout" value={safeText(stockoutDate)} />
            <Detail label="Inventory value" value={formatMoney(inventoryValue)} />
            <Detail label="Cash impact" value={formatMoney(cashImpact)} />
            <Detail label="Confidence" value={safeText(confidence)} />
          </dl>
          {recommendedAction && !hideActionText ? <p className="stock-health-action">{recommendedAction}</p> : null}
          {dataQualityNote ? <p className="stock-health-note">{dataQualityNote}</p> : null}
        </details>
      )}
    </section>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function normalizeStatus(
  status: string | null | undefined,
  riskLevel: RiskLevel | null | undefined,
  currentStock: number | null | undefined,
  dailyVelocity: number | null | undefined,
  coverDays: number | null,
  leadTimeDays: number | null | undefined,
  targetCoverageDays: number | null | undefined,
  daysSinceLastSale: number | null | undefined,
): StockHealthStatus {
  if (status) {
    const normalized = status.toLowerCase();
    if (normalized.includes("dead")) return "Dead stock";
    if (normalized.includes("overstock")) return "Overstock";
    if (normalized.includes("stockout")) return "Stockout risk";
    if (normalized.includes("at risk")) return "At risk";
    if (normalized.includes("watch")) return "Watch";
    if (normalized.includes("healthy")) return "Healthy";
  }

  if (riskLevel === "Critical") return "Stockout risk";
  if (riskLevel === "High") return "At risk";
  if (riskLevel === "Medium") return "Watch";

  if (isFiniteNumber(currentStock) && currentStock > 0) {
    if ((isFiniteNumber(dailyVelocity) && dailyVelocity === 0) || (isFiniteNumber(daysSinceLastSale) && daysSinceLastSale >= 90)) {
      return "Dead stock";
    }
  }
  if (isFiniteNumber(coverDays) && isFiniteNumber(leadTimeDays)) {
    if (coverDays <= leadTimeDays) return "Stockout risk";
    if (coverDays <= leadTimeDays + 7) return "At risk";
    if (coverDays <= leadTimeDays + 14) return "Watch";
  }
  if (isFiniteNumber(coverDays) && isFiniteNumber(targetCoverageDays) && coverDays > targetCoverageDays * 3) {
    return "Overstock";
  }
  return "Healthy";
}

function buildExplanation({
  health,
  currentStock,
  dailyVelocity,
  coverDays,
  leadTimeDays,
  targetCoverageDays,
  daysSinceLastSale,
}: {
  health: StockHealthStatus;
  currentStock?: number | null;
  dailyVelocity?: number | null;
  coverDays: number | null;
  leadTimeDays?: number | null;
  targetCoverageDays?: number | null;
  daysSinceLastSale?: number | null;
}): string {
  if (health === "Dead stock") {
    if (isFiniteNumber(daysSinceLastSale)) {
      return `This SKU has inventory on hand and ${formatNumber(daysSinceLastSale)} days since last sale, so it belongs in dead-stock review.`;
    }
    return "No recent sales and inventory on hand indicate a dead-stock risk.";
  }
  if (health === "Overstock") {
    if (isFiniteNumber(coverDays) && isFiniteNumber(targetCoverageDays)) {
      return `This SKU has ${formatNumber(coverDays)} days left, above the ${formatNumber(targetCoverageDays)}-day target. Review for overstock.`;
    }
    return "Current stock appears above target, so review this SKU before buying more.";
  }
  if ((health === "Stockout risk" || health === "At risk" || health === "Watch") && isFiniteNumber(coverDays) && isFiniteNumber(leadTimeDays)) {
    if (coverDays <= leadTimeDays) {
      return `This SKU has ${formatNumber(coverDays)} days left and a ${formatNumber(leadTimeDays)}-day lead time, so replenishment may not arrive before stock runs out.`;
    }
    return `This SKU has ${formatNumber(coverDays)} days left against a ${formatNumber(leadTimeDays)}-day lead time, so it should stay in reorder review.`;
  }
  if (!isFiniteNumber(dailyVelocity) || dailyVelocity <= 0) {
    return isFiniteNumber(currentStock) && currentStock > 0
      ? "Not enough sales velocity to project cover confidently. Review sales history before acting."
      : "Not enough sales history to classify this SKU with confidence.";
  }
  return "This SKU has enough projected cover beyond lead time and target coverage based on current signals.";
}

function firstFinite(...values: Array<number | null | undefined>): number | null {
  return values.find((value): value is number => isFiniteNumber(value)) ?? null;
}

function healthBarPercent(
  coverDays: number | null,
  targetCoverageDays?: number | null,
  leadTimeDays?: number | null,
): number {
  if (!isFiniteNumber(coverDays)) return 0;
  const max = Math.max(targetCoverageDays ?? 0, leadTimeDays ?? 0, coverDays, 30);
  return clamp((coverDays / max) * 100, 4, 100);
}

function markerPercent(
  value?: number | null,
  targetCoverageDays?: number | null,
  coverDays?: number | null,
): number | null {
  if (!isFiniteNumber(value)) return null;
  const max = Math.max(targetCoverageDays ?? 0, coverDays ?? 0, value, 30);
  return clamp((value / max) * 100, 4, 98);
}

function toneForStatus(status: StockHealthStatus): "healthy" | "watch" | "risk" | "overstock" | "dead" {
  if (status === "Healthy") return "healthy";
  if (status === "Watch") return "watch";
  if (status === "At risk" || status === "Stockout risk") return "risk";
  if (status === "Overstock") return "overstock";
  return "dead";
}

function formatVelocity(value?: number | null): string {
  return isFiniteNumber(value) ? `${formatNumber(value)} / day` : "Not enough sales history";
}

function formatDays(value?: number | null): string {
  return isFiniteNumber(value) ? `${formatNumber(value)} days` : "Unavailable";
}

function formatNumber(value?: number | null): string {
  if (!isFiniteNumber(value)) return "Unavailable";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: value < 10 ? 1 : 0 }).format(value);
}

function formatMoney(value?: number | null): string {
  if (!isFiniteNumber(value)) return "Unavailable";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
}

function safeText(value?: string | null): string {
  if (!value || value === "Invalid Date" || value === "NaN") return "Unavailable";
  return value;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
