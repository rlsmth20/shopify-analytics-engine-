import type { PurchaseOrderDraft } from "@/lib/api-v2";

export type ReceiptInput = {
  lines: { sku_id: string; received_qty: number; received_unit_cost?: number | null }[];
  received_at: string;
};
export type ReceiptRequest = ReceiptInput & { request_id: string };
export type PendingReceipt = { version: 1; po_id: string; created_at: string; payload: ReceiptRequest; rejection?: string };
export class ReceiptSubmissionError extends Error {
  constructor(message: string, public notAppliedRequestId: string | null = null) { super(message); this.name = "ReceiptSubmissionError"; }
}
type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem" | "key" | "length">;
const PREFIX = "skubase_receipt_v1:";
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function receiptScope(shopId: number, userId: number): string {
  if (!Number.isSafeInteger(shopId) || shopId < 1 || !Number.isSafeInteger(userId) || userId < 1) throw new Error("Sign in to your store before recording a delivery.");
  return `${PREFIX}${shopId}:${userId}:`;
}
const keyFor = (scope: string, poId: string) => `${scope}${encodeURIComponent(poId)}`;

export async function withReceiptLock<T>(locks: Pick<LockManager, "request"> | undefined, scope: string, poId: string, action: () => T | Promise<T>): Promise<T> {
  if (!locks?.request) return Promise.reject(new Error("This browser cannot safely coordinate receipt recovery. Open Skubase in a current browser over HTTPS before recording a delivery."));
  return await locks.request(keyFor(scope, poId), action);
}

function validSubmission(value: unknown): value is PendingReceipt {
  if (!value || typeof value !== "object") return false;
  const row = value as PendingReceipt;
  return row.version === 1 && typeof row.po_id === "string" && row.po_id.length > 0 &&
    (row.rejection === undefined || (typeof row.rejection === "string" && row.rejection.length > 0)) &&
    typeof row.created_at === "string" && Number.isFinite(Date.parse(row.created_at)) &&
    typeof row.payload?.request_id === "string" && uuidPattern.test(row.payload.request_id) &&
    typeof row.payload.received_at === "string" && Number.isFinite(Date.parse(row.payload.received_at)) &&
    Array.isArray(row.payload.lines) && row.payload.lines.length > 0 &&
    new Set(row.payload.lines.map(line => line?.sku_id)).size === row.payload.lines.length &&
    row.payload.lines.every(line => line && typeof line.sku_id === "string" && line.sku_id.trim().length > 0 &&
      Number.isSafeInteger(line.received_qty) && line.received_qty > 0 &&
      typeof line.received_unit_cost === "number" && Number.isFinite(line.received_unit_cost) && line.received_unit_cost >= 0);
}

export function readPendingReceipt(storage: StorageLike, scope: string, poId: string): PendingReceipt | null {
  const raw = storage.getItem(keyFor(scope, poId));
  if (raw === null) return null;
  let value: unknown;
  try { value = JSON.parse(raw); } catch { throw new Error("Saved receipt recovery data could not be read. Do not enter this delivery again; contact info@skubase.io for help."); }
  if (!validSubmission(value) || value.po_id !== poId) throw new Error("Saved receipt recovery data could not be verified. Do not enter this delivery again; contact info@skubase.io for help.");
  return value;
}

export function listPendingReceipts(storage: StorageLike, scope: string): PendingReceipt[] {
  const result: PendingReceipt[] = [];
  for (let index = 0; index < storage.length; index++) {
    const key = storage.key(index);
    if (!key?.startsWith(scope)) continue;
    const entry = readPendingReceipt(storage, scope, decodeURIComponent(key.slice(scope.length)));
    if (entry) result.push(entry);
  }
  return result.sort((a, b) => a.created_at.localeCompare(b.created_at));
}

export function retainReceiptSubmission(storage: StorageLike, scope: string, poId: string, input: ReceiptInput,
  newId: () => string = () => crypto.randomUUID(), now: () => string = () => new Date().toISOString()): PendingReceipt {
  // A changed editor or an updated PO must never mutate an uncertain submission.
  const existing = readPendingReceipt(storage, scope, poId);
  if (existing) return existing;
  const record: PendingReceipt = { version: 1, po_id: poId, created_at: now(),
    payload: JSON.parse(JSON.stringify({ ...input, request_id: newId() })) as ReceiptRequest };
  if (!validSubmission(record)) throw new Error("Enter a valid receipt date, positive whole quantities and actual unit costs before submitting.");
  const serialized = JSON.stringify(record);
  try {
    storage.setItem(keyFor(scope, poId), serialized);
    if (storage.getItem(keyFor(scope, poId)) !== serialized) throw new Error("Storage write was not retained");
  } catch { throw new Error("Receipt recovery could not be saved in this browser. No receipt was submitted. Enable browser storage and try again."); }
  return record;
}

export function clearReceiptSubmission(storage: StorageLike, scope: string, record: PendingReceipt): void {
  const current = readPendingReceipt(storage, scope, record.po_id);
  if (current && current.payload.request_id !== record.payload.request_id) throw new Error("A different receipt is awaiting confirmation. Refresh this page before continuing.");
  storage.removeItem(keyFor(scope, record.po_id));
  if (storage.getItem(keyFor(scope, record.po_id)) !== null) throw new Error("The receipt recovery record could not be cleared. Retry the same receipt to check its saved result safely.");
}

export function markReceiptRejected(storage: StorageLike, scope: string, record: PendingReceipt, message: string): void {
  const current = readPendingReceipt(storage, scope, record.po_id);
  if (!current || current.payload.request_id !== record.payload.request_id) throw new Error("Receipt recovery changed. Reload this page before continuing.");
  storage.setItem(keyFor(scope, record.po_id), JSON.stringify({ ...current, rejection: message }));
}

export function confirmedReceiptResponse(value: unknown, record: PendingReceipt): value is { po: PurchaseOrderDraft; replayed: boolean; request_id: string } {
  if (!value || typeof value !== "object") return false;
  const response = value as { po?: PurchaseOrderDraft; replayed?: boolean; request_id?: string };
  return response.request_id === record.payload.request_id && typeof response.replayed === "boolean" &&
    response.po?.po_id === record.po_id && Array.isArray(response.po.lines) &&
    response.po.lines.every(line => typeof line.sku_id === "string" && Number.isSafeInteger(line.qty) && line.qty >= 0 &&
      Number.isSafeInteger(line.received_qty) && line.received_qty >= 0 && line.received_qty <= line.qty);
}
