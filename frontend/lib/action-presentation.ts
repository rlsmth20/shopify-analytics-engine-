import type { InventoryAction } from "@/lib/api";
import { isHistoryReviewAction } from "@/lib/action-quality";

function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function actionTableMetrics(action: InventoryAction) {
  const historyReview = isHistoryReviewAction(action);
  const coverage = historyReview ? null
    : action.status === "urgent" && finite(action.days_until_stockout) ? action.days_until_stockout
    : finite(action.days_of_inventory) ? action.days_of_inventory : null;
  const leadTime = finite(action.lead_time_days_used) ? action.lead_time_days_used : null;
  const impact = historyReview ? null : action.status === "urgent" ? action.estimated_profit_impact : action.cash_tied_up;
  return {
    historyReview,
    coverage,
    leadTime,
    impact: finite(impact) ? impact : null,
    stock: finite(action.current_on_hand) ? action.current_on_hand : null,
    priority: finite(action.priority_score) ? action.priority_score : null,
    // Match the existing ActionCard display calculation, not a second forecast.
    reorderUnits: action.status === "urgent" && finite(action.target_inventory_units) && finite(action.current_on_hand)
      ? Math.max(Math.round(action.target_inventory_units - action.current_on_hand), 0) : null,
    runsOutBeforeDelivery: action.status === "urgent" && coverage !== null && leadTime !== null && coverage < leadTime,
  };
}
