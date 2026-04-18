import type { InventoryAction } from "@/lib/api";
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
        <p className="action-explanation">
          {action.explanation ?? "Decision rationale is loading."}
        </p>
      </div>

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
        <div>
          <dt>Days of inventory</dt>
          <dd>{numberFormatter.format(action.days_of_inventory)}</dd>
        </div>
        <div>
          <dt>Lead time used</dt>
          <dd>{action.lead_time_days_used} days</dd>
        </div>
        <div>
          <dt>Lead time source</dt>
          <dd>{leadTimeSourceLabel[action.lead_time_source]}</dd>
        </div>
        <div>
          <dt>Target coverage</dt>
          <dd>{action.target_coverage_days} days</dd>
        </div>
        {action.status === "urgent" ? (
          <>
            <div>
              <dt>Days until stockout</dt>
              <dd>{numberFormatter.format(action.days_until_stockout)}</dd>
            </div>
            <div>
              <dt>Profit at risk</dt>
              <dd>{currencyFormatter.format(action.estimated_profit_impact)}</dd>
            </div>
          </>
        ) : (
          <>
            <div>
              <dt>Excess units</dt>
              <dd>{numberFormatter.format(action.excess_units)}</dd>
            </div>
            <div>
              <dt>Cash tied up</dt>
              <dd>{currencyFormatter.format(action.cash_tied_up)}</dd>
            </div>
          </>
        )}
      </dl>
    </article>
  );
}
