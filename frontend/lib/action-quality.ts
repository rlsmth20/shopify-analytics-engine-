import type { InventoryAction } from "@/lib/api";

export function isHistoryReviewAction(action: InventoryAction): boolean {
  return action.status === "optimize" && action.sales_history_complete === false;
}
