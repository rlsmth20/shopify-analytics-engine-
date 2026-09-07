import type { InventoryAction } from "@/lib/api";
import { getActionImpactValue } from "@/lib/app-helpers";
import { isHistoryReviewAction } from "@/lib/action-quality";

export type ActionFilters = {
  query: string;
  status: "all" | "urgent" | "optimize" | "dead";
  confidence: "all" | "high" | "medium" | "low";
  stockoutDays: "all" | "7" | "14";
  sort: "priority" | "impact" | "coverage";
};

export const DEFAULT_ACTION_FILTERS: ActionFilters = {
  query: "", status: "all", confidence: "all", stockoutDays: "all", sort: "priority",
};

export function filterInventoryActions(actions: InventoryAction[], filters: ActionFilters): InventoryAction[] {
  const query = filters.query.trim().toLocaleLowerCase();
  return actions.filter((action) =>
    (!query || `${action.sku_id} ${action.name}`.toLocaleLowerCase().includes(query)) &&
    (filters.status === "all" || action.status === filters.status) &&
    (filters.confidence === "all" || action.data_quality_confidence === filters.confidence) &&
    (filters.stockoutDays === "all" || (action.status === "urgent" && Number.isFinite(action.days_until_stockout) && action.days_until_stockout <= Number(filters.stockoutDays)))
  ).sort((a, b) => {
    const primary = filters.sort === "impact" ? (getActionImpactValue(b) ?? Number.NEGATIVE_INFINITY) - (getActionImpactValue(a) ?? Number.NEGATIVE_INFINITY)
      : filters.sort === "coverage" ? coverageForSort(a) - coverageForSort(b)
      : b.priority_score - a.priority_score;
    return primary || b.priority_score - a.priority_score || a.sku_id.localeCompare(b.sku_id);
  });
}

function coverageForSort(action: InventoryAction): number {
  return !isHistoryReviewAction(action) && Number.isFinite(action.days_of_inventory)
    ? action.days_of_inventory : Number.POSITIVE_INFINITY;
}

export function readActionFilters(params: URLSearchParams): ActionFilters {
  return {
    query: params.get("q") || "",
    status: (["urgent", "optimize", "dead"].includes(params.get("status") || "") ? params.get("status") : "all") as ActionFilters["status"],
    confidence: (["high", "medium", "low"].includes(params.get("confidence") || "") ? params.get("confidence") : "all") as ActionFilters["confidence"],
    stockoutDays: (["7", "14"].includes(params.get("stockout") || "") ? params.get("stockout") : "all") as ActionFilters["stockoutDays"],
    sort: (["impact", "coverage"].includes(params.get("sort") || "") ? params.get("sort") : "priority") as ActionFilters["sort"],
  };
}
