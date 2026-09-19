"use client";

import { API_BASE_URL } from "@/lib/api-base";
import type { HealthRow, HealthSettings } from "@/lib/inventory-health-check";

export type InventoryHistoryPoint = { date: string; cost_value: number | null; retail_value: number | null; total_units: number | null };
type WorkbookPayload =
  | { kind: "inventory_history"; sample: boolean; points: InventoryHistoryPoint[] }
  | { kind: "inventory_health"; sample: boolean; currency: string; settings: HealthSettings; rows: HealthRow[] };

/** Explicit download only: the formatter returns an in-memory workbook and saves no inputs. */
export async function downloadSpreadsheet(payload: WorkbookPayload, filename: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/exports/workbook.xlsx`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload), signal: AbortSignal.timeout(45_000), cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : "Couldn't create the Excel file. Try again or download CSV.");
  }
  if (!response.headers.get("content-type")?.includes("spreadsheetml.sheet")) {
    throw new Error("The Excel download was unavailable. Try again or download CSV.");
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url; link.download = filename;
  document.body.appendChild(link);
  link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2_000);
}
