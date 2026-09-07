import { fetchInventoryActions, type InventoryAction } from "@/lib/api";
import {
  fetchForecasts, fetchReorderSuggestions, fetchScorecards,
  type ForecastResult, type ReorderSuggestion, type SkuScorecard,
} from "@/lib/api-v2";
import { entitlementHas, type Entitlements } from "@/lib/entitlements";

export type ReportKind = "actions" | "stockout" | "dead-stock" | "reorder";
export type LoadedReportData = {
  actions: InventoryAction[];
  forecasts: ForecastResult[];
  reorder: ReorderSuggestion[];
  scorecards: SkuScorecard[];
};
type Dataset = keyof LoadedReportData;
export type ReportSourceState = {
  status: "loading" | "ready" | "error" | "locked" | "unverified";
  message?: string;
};
export type ReportLoadState = {
  data: LoadedReportData;
  sources: Record<Dataset, ReportSourceState>;
};

export function reportDataset(report: ReportKind): Dataset {
  return report === "stockout" ? "forecasts" : report === "dead-stock" ? "actions" : report;
}

/** Each report becomes usable as its own data arrives. Optional enrichment can fail independently. */
export async function loadReportData(
  entitlements: Entitlements | null,
  demo: boolean,
  signal: AbortSignal,
  onUpdate: (state: ReportLoadState) => void,
): Promise<void> {
  const featureState = (capability: "forecast" | "reorder_pos"): ReportSourceState => ({
    status: demo || entitlementHas(entitlements, capability)
      ? "loading" : entitlements ? "locked" : "unverified",
  });
  let state: ReportLoadState = {
    data: { actions: [], forecasts: [], reorder: [], scorecards: [] },
    sources: {
      actions: { status: "loading" }, scorecards: { status: "loading" },
      forecasts: featureState("forecast"), reorder: featureState("reorder_pos"),
    },
  };
  if (signal.aborted) return;
  onUpdate(state);

  async function load<K extends Dataset>(key: K, request: () => Promise<LoadedReportData[K]>) {
    if (state.sources[key].status !== "loading") return;
    try {
      const rows = await request();
      if (signal.aborted) return;
      state = {
        data: { ...state.data, [key]: rows },
        sources: { ...state.sources, [key]: { status: "ready" } },
      };
    } catch (error) {
      if (signal.aborted) return;
      state = {
        ...state,
        sources: { ...state.sources, [key]: {
          status: "error",
          message: error instanceof Error ? error.message : "This report data could not be loaded. Please try again.",
        } },
      };
    }
    onUpdate(state);
  }

  await Promise.all([
    load("actions", async () => (await fetchInventoryActions(signal)).actions),
    load("forecasts", async () => (await fetchForecasts(signal)).forecasts),
    load("reorder", async () => (await fetchReorderSuggestions(0.95, signal)).suggestions),
    load("scorecards", async () => (await fetchScorecards(signal)).scorecards),
  ]);
}

export function reportContextWarning(report: ReportKind, sources: ReportLoadState["sources"]): string | null {
  const optional: Dataset[] = report === "stockout" ? ["actions", "scorecards"] : ["forecasts", "scorecards"];
  return optional.some((key) => sources[key].status === "error")
    ? "Some supporting data could not be loaded. Available report rows are shown; missing context is marked unavailable."
    : null;
}
