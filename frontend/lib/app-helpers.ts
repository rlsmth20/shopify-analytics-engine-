"use client";

import type {
  CategoryLeadTimeEntry,
  DataQualityConfidence,
  InventoryAction,
  LatestShopifySyncStatusResponse,
  LeadTimeSource,
  ShopifySyncRun,
  UrgencyLevel,
  VendorLeadTimeEntry
} from "@/lib/api";
import { ApiError } from "@/lib/api";

export const SHOPIFY_DOMAIN_STORAGE_KEY = "shopify_domain";

export type ActionFilter = "all" | InventoryAction["status"];
export type ActionSort = "priority" | "impact";

export const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0
});

export const numberFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 1
});

export const dateTimeFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short"
});

export const statusLabel = {
  urgent: "Urgent",
  optimize: "Optimize",
  dead: "Dead"
} satisfies Record<InventoryAction["status"], string>;

export const urgencyLabel = {
  critical: "Critical",
  high: "High",
  medium: "Medium"
} satisfies Record<UrgencyLevel, string>;

export const confidenceLabel = {
  high: "High",
  medium: "Medium",
  low: "Low"
} satisfies Record<DataQualityConfidence, string>;

export const leadTimeSourceLabel = {
  sku_override: "SKU Override",
  vendor: "Supplier",
  category: "Category",
  global_default: "Global Default"
} satisfies Record<LeadTimeSource, string>;

export function buildActionErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 503) {
    return (
      error.message ||
      "Live action data is unavailable because sample fallback is disabled."
    );
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "The Action Queue could not be loaded.";
}

export function buildSyncRunSummary(syncRun: ShopifySyncRun): string {
  if (syncRun.status === "running") {
    return "A Shopify ingest is currently running";
  }

  if (syncRun.status === "failed") {
    return "The most recent Shopify ingest failed";
  }

  return "The most recent Shopify ingest succeeded";
}

export function formatSyncTimestamp(value: string): string {
  return dateTimeFormatter.format(new Date(value));
}

export function getActionImpactValue(action: InventoryAction): number {
  if (action.status === "urgent") {
    return action.estimated_profit_impact;
  }

  return action.cash_tied_up;
}

export function summarizeDataSource(
  dataSource: "db" | "mock" | null
): string | null {
  if (!dataSource) {
    return null;
  }

  return dataSource === "db" ? "Live store data" : "Sample fallback";
}

export function summarizeSyncStatus(
  latestSyncStatus: LatestShopifySyncStatusResponse | null
): string {
  if (!latestSyncStatus?.latest_run) {
    return "No sync run recorded";
  }

  const { latest_run: latestRun } = latestSyncStatus;
  if (latestRun.status === "running") {
    return "Running";
  }
  if (latestRun.status === "failed") {
    return "Failed";
  }

  return "Succeeded";
}

export function formatVendorLeadTimes(items: VendorLeadTimeEntry[]): string {
  return items.map((item) => `${item.vendor} | ${item.lead_time_days}`).join("\n");
}

export function formatCategoryLeadTimes(items: CategoryLeadTimeEntry[]): string {
  return items
    .map((item) => `${item.category} | ${item.lead_time_days}`)
    .join("\n");
}

export function parseVendorLeadTimes(value: string): VendorLeadTimeEntry[] {
  return parseLeadTimeLines(value, "vendor").map((item) => ({
    vendor: item.name,
    lead_time_days: item.lead_time_days
  }));
}

export function parseCategoryLeadTimes(value: string): CategoryLeadTimeEntry[] {
  return parseLeadTimeLines(value, "category").map((item) => ({
    category: item.name,
    lead_time_days: item.lead_time_days
  }));
}

function parseLeadTimeLines(
  value: string,
  label: "vendor" | "category"
): Array<{ name: string; lead_time_days: number }> {
  const lines = value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  return lines.map((line, index) => {
    const segments = line.split("|").map((segment) => segment.trim());
    if (segments.length !== 2 || !segments[0] || !segments[1]) {
      throw new Error(
        `${label} lead times must use "name | days" format on line ${index + 1}.`
      );
    }

    const leadTimeDays = Number.parseInt(segments[1], 10);
    if (Number.isNaN(leadTimeDays) || leadTimeDays < 1) {
      throw new Error(
        `${label} lead times must use a whole number of at least 1 on line ${
          index + 1
        }.`
      );
    }

    return {
      name: segments[0],
      lead_time_days: leadTimeDays
    };
  });
}
