import type { InventoryAction } from "@/lib/api";
import { ProjectedStockHealth } from "@/components/projected-stock-health";
import {
  confidenceLabel,
  currencyFormatter,
  leadTimeSourceLabel,
  numberFormatter,
  statusLabel,
  urgencyLabel
} from "@/lib/app-helpers";

export function ActionCard({
  action
}: {
  action: InventoryAction;
}) {
  const daysLeft = firstFinite(
    action.status === "urgent" ? action.days_until_stockout : null,
    action.days_of_inventory
  );
  const recommendedQty =
    action.status === "urgent" && isFiniteNumber(action.target_inventory_units) && isFiniteNumber(action.current_on_hand)
      ? Math.max(Math.round(action.target_inventory_units - action.current_on_hand), 0)
      : null;
  const cashAtRisk = action.status === "urgent" ? action.estimated_profit_impact : action.cash_tied_up;
  const calculationDetails = technicalExplanation(action.explanation) ? action.explanation : null;
  const explanation = plainEnglishExplanation(action, daysLeft);
  const stockHealthStatus =
    action.status === "urgent"
      ? "Stockout risk"
      : action.status === "dead"
        ? "Dead stock"
        : isFiniteNumber(action.days_of_inventory) &&
            isFiniteNumber(action.target_coverage_days) &&
            action.days_of_inventory > action.target_coverage_days * 3
          ? "Overstock"
          : "Watch";

  return (
    <article className={`action-card action-card-${action.status}`}>
      <div className="action-card-top">
        <div className="action-card-badges">
          <span className={`pill pill-${action.status}`}>
            {statusLabel[action.status]}
          </span>
          {action.status === "urgent" ? (
            <span className={`pill pill-urgency-${action.urgency_level}`}>
              {urgencyLabel[action.urgency_level]}
            </span>
          ) : null}
        </div>
        <span className="score-chip">
          Priority {numberFormatter.format(action.priority_score)}
        </span>
      </div>

      <div className="action-card-main">
        <p className="action-sku">{action.sku_id}</p>
        <h3 className="action-name">{action.name}</h3>
        <p className="action-recommendation">{action.recommended_action}</p>
        <p className="action-explanation">{explanation}</p>
      </div>

      <div className="action-rationale">
        <p className="quality-label">Why this is ranked here</p>
        <div className="action-rationale-grid">
          <Reason label="Priority" value={numberFormatter.format(action.priority_score)} />
          {action.status === "urgent" ? (
            <>
              <Reason
                label="Days left"
                value={formatDaysLeft(daysLeft)}
              />
              <Reason
                label="Cash at risk"
                value={formatMoney(cashAtRisk)}
              />
            </>
          ) : (
            <>
              <Reason
                label="Days left"
                value={formatDaysLeft(daysLeft)}
              />
              <Reason
                label="Cash at risk"
                value={formatMoney(cashAtRisk)}
              />
            </>
          )}
          <Reason
            label="Lead time"
            value={formatDays(action.lead_time_days_used, "Lead time unavailable")}
          />
          <Reason
            label="Target coverage"
            value={formatDays(action.target_coverage_days, "Unavailable")}
          />
          {recommendedQty !== null ? (
            <Reason label="Recommended qty" value={numberFormatter.format(recommendedQty)} />
          ) : null}
        </div>
      </div>

      <ProjectedStockHealth
        productName={action.name}
        sku={action.sku_id}
        currentStock={action.current_on_hand}
        dailyVelocity={action.daily_velocity}
        salesLast30Days={isFiniteNumber(action.daily_velocity) ? Math.round(action.daily_velocity * 30) : null}
        daysLeft={daysLeft}
        daysOfInventory={action.days_of_inventory}
        leadTimeDays={action.lead_time_days_used}
        targetCoverageDays={action.target_coverage_days}
        recommendedQty={recommendedQty}
        recommendedAction={action.recommended_action}
        status={stockHealthStatus}
        cashImpact={cashAtRisk}
        confidence={confidenceLabel[action.data_quality_confidence]}
        dataQualityNote={action.data_quality_warnings[0]}
        compact
        hideMetricGrid
      />

      <details className="action-advanced-details">
        <summary>Advanced details</summary>
        {action.data_quality_warnings.length > 0 ? (
          <div className="quality-block">
            <p className="quality-label">
              Data confidence {confidenceLabel[action.data_quality_confidence]}
            </p>
            <ul className="warning-list">
              {action.data_quality_warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="quality-inline">
            <span className="quality-label">
              Data confidence {confidenceLabel[action.data_quality_confidence]}
            </span>
          </div>
        )}

        <dl className="action-metadata">
          <Meta label="Current stock" value={formatNumber(action.current_on_hand)} />
          <Meta label="Daily velocity" value={formatVelocity(action.daily_velocity)} />
          <Meta label="Reorder point" value={formatNumber(action.reorder_point_units)} />
          <Meta label="Safety stock" value={formatNumber(action.safety_stock_units)} />
          <Meta label="Target units" value={formatNumber(action.target_inventory_units)} />
          <Meta label="Lead time source" value={leadTimeSourceLabel[action.lead_time_source]} />
          {action.status === "urgent" ? (
            <Meta label="Exact stockout probability" value={riskTextFromExplanation(action.explanation)} />
          ) : (
            <Meta label="Excess units" value={formatNumber(action.excess_units)} />
          )}
          {calculationDetails ? (
            <div className="action-metadata-wide">
              <dt>Calculation details</dt>
              <dd>{calculationDetails}</dd>
            </div>
          ) : null}
        </dl>
      </details>
    </article>
  );
}

function Reason({ label, value }: { label: string; value: string }) {
  return (
    <div className="action-reason">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function plainEnglishExplanation(action: InventoryAction, daysLeft: number | null): string {
  if (!technicalExplanation(action.explanation) && action.explanation) {
    return action.explanation;
  }
  if (action.status === "urgent" && isFiniteNumber(daysLeft) && isFiniteNumber(action.lead_time_days_used)) {
    if (daysLeft <= action.lead_time_days_used) {
      return `Current stock covers ${numberFormatter.format(daysLeft)} days, but lead time is ${numberFormatter.format(action.lead_time_days_used)} days. This SKU may run out before replenishment arrives.`;
    }
    return `Current stock covers ${numberFormatter.format(daysLeft)} days against a ${numberFormatter.format(action.lead_time_days_used)}-day lead time. Keep this SKU in reorder review.`;
  }
  if (action.status === "dead" && isFiniteNumber(action.cash_tied_up)) {
    return `${formatMoney(action.cash_tied_up)} is tied up in inventory that should be reviewed for recovery.`;
  }
  if (action.status === "optimize" && isFiniteNumber(action.days_of_inventory) && isFiniteNumber(action.target_coverage_days)) {
    return `Current stock covers ${numberFormatter.format(action.days_of_inventory)} days against a ${numberFormatter.format(action.target_coverage_days)}-day target. Review before placing another order.`;
  }
  return "Skubase ranked this item because its inventory signals need review.";
}

function technicalExplanation(value?: string | null): boolean {
  if (!value) return false;
  return /normal_cdf|normalcdf|erf\(|z-score|demand volatility|projected 30d|1\s*-\s*normal/i.test(value);
}

function riskTextFromExplanation(value?: string | null): string {
  const match = value?.match(/Stockout risk is\s+(\d+(?:\.\d+)?)%/i);
  return match ? `${match[1]}%` : "Unavailable";
}

function firstFinite(...values: Array<number | null | undefined>): number | null {
  return values.find((value): value is number => isFiniteNumber(value)) ?? null;
}

function formatDays(value: number | null | undefined, fallback: string): string {
  return isFiniteNumber(value) ? `${numberFormatter.format(value)} days` : fallback;
}

function formatDaysLeft(value: number | null): string {
  return isFiniteNumber(value) ? `${numberFormatter.format(value)} days` : "Not enough sales history";
}

function formatMoney(value: number | null | undefined): string {
  return isFiniteNumber(value) ? currencyFormatter.format(value) : "Unavailable";
}

function formatNumber(value: number | null | undefined): string {
  return isFiniteNumber(value) ? numberFormatter.format(value) : "Unavailable";
}

function formatVelocity(value: number | null | undefined): string {
  return isFiniteNumber(value) ? `${numberFormatter.format(value)} / day` : "Not enough sales history";
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}
