export type SyncResult = {
  status: "succeeded" | "partial";
  products_count?: number;
  products_scanned?: number;
  variants_imported?: number;
  inventory_variants_active?: number;
  inventory_variants_excluded?: number;
  inventory_rows_retired?: number;
  order_line_items_count?: number;
  orders_scanned?: number;
  line_items_scanned?: number;
  line_items_imported?: number;
  line_items_skipped?: number;
  line_item_skip_reasons?: Record<string, number>;
  top_skip_reason?: string | null;
  token_lacks_read_orders?: boolean;
  no_eligible_recent_orders_found?: boolean;
  orders_error?: string | null;
};

export function isSyncResult(value: unknown): value is SyncResult {
  if (!value || typeof value !== "object") return false;
  const result = value as Record<string, unknown>;
  return (result.status === "succeeded" || result.status === "partial") &&
    ["variants_imported", "order_line_items_count"].every((key) =>
      typeof result[key] === "number" && Number.isSafeInteger(result[key]) && result[key] >= 0
    );
}

export function getSyncNotice(result: SyncResult): { warning: boolean; title: string; message: string } | null {
  if (result.token_lacks_read_orders) {
    return { warning: true, title: "Order access needs approval", message: "Inventory refreshed. Reconnect Shopify to approve order access, then sync again. Sales forecasts may be incomplete until order history imports." };
  }
  if (result.status === "partial" || result.orders_error) {
    return { warning: true, title: "Order history is incomplete", message: `${result.orders_error || "The order import could not finish. Please try syncing again."} Sales forecasts may be incomplete until order history imports.` };
  }
  if (unmatchedSyncItems(result) > 0) {
    return { warning: true, title: "Some order items could not be matched", message: "Inventory refreshed, but some sales could not be matched to catalog variants. Custom or deleted items may be excluded from forecasts. Review the skipped-item count below." };
  }
  if (result.no_eligible_recent_orders_found) {
    return { warning: false, title: "Inventory refreshed; no recent paid orders", message: "Shopify returned no eligible paid orders in the last 60 days. No reconnect is needed. Sales-based forecasts need order history; any previously imported history is retained." };
  }
  return null;
}

export function unmatchedSyncItems(result: SyncResult): number {
  return Math.max(0, (result.line_items_skipped ?? 0) - (result.line_item_skip_reasons?.already_imported ?? 0));
}
