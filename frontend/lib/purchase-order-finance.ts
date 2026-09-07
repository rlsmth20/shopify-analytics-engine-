import type { PurchaseOrderDraft, PurchaseOrderLine } from "./api-v2";
import { financialTotal, financialValue } from "./financial-values";

export type EditablePoLine = {
  sku_id: string;
  name: string;
  qty: string;
  unit_cost: string;
  received_qty: number;
};
export type EditablePoDraft = {
  vendor: string;
  expected_arrival_date: string;
  shipping_cost: string;
  rationale: string;
  lines: EditablePoLine[];
};

export function purchaseOrderCostsKnown(po: PurchaseOrderDraft): boolean {
  return financialValue(po, "total_cost", po.total_cost) !== null
    && po.lines.length > 0
    && po.lines.every((line) => financialValue(line, "unit_cost", line.unit_cost) !== null);
}

export function editableUnitCost(line: PurchaseOrderLine): string {
  return financialValue(line, "unit_cost", line.unit_cost)?.toFixed(2) ?? "";
}

export function parseMoney(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) return null;
  const rounded = roundCurrency(parsed);
  return Number.isFinite(rounded) ? rounded : null;
}

export function parseWholeNumber(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 0) return null;
  return parsed;
}

export function normalizeEditableLine(line: EditablePoLine): PurchaseOrderLine | null {
  const skuId = line.sku_id.trim();
  const name = line.name.trim();
  const qty = parseWholeNumber(line.qty);
  const unitCost = parseMoney(line.unit_cost);
  const alreadyReceived = Math.max(Math.round(line.received_qty ?? 0), 0);
  if (!skuId || !name || qty === null || qty < 1 || qty < alreadyReceived || unitCost === null) return null;
  const extendedCost = roundCurrency(qty * unitCost);
  if (!Number.isFinite(extendedCost)) return null;
  return {
    sku_id: skuId,
    name,
    qty,
    unit_cost: unitCost,
    extended_cost: extendedCost,
    received_qty: alreadyReceived,
    cost_source: "recorded",
    financial_values_known: true,
    financial_values: { unit_cost: unitCost, extended_cost: extendedCost },
  };
}

export function previewEditablePoTotals(draft: EditablePoDraft): {
  subtotal: number | null; shipping: number | null; total: number | null;
} {
  const subtotal = financialTotal(draft.lines.map((line) => {
    const qty = parseWholeNumber(line.qty);
    const unitCost = parseMoney(line.unit_cost);
    return qty === null || unitCost === null ? null : roundCurrency(qty * unitCost);
  }));
  const shipping = parseMoney(draft.shipping_cost);
  return { subtotal, shipping, total: financialTotal([subtotal, shipping]) };
}

export function sumPoTotals(drafts: PurchaseOrderDraft[]): number | null {
  const total = financialTotal(drafts.map((po) => financialValue(po, "total_cost", po.total_cost)));
  return total === null ? null : roundCurrency(total);
}

export function roundCurrency(value: number): number {
  return Math.round(value * 100) / 100;
}
