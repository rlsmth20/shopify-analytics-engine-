"use client";

import { useEffect, useState } from "react";

import {
  currency,
  fetchPurchaseOrders,
  receivePurchaseOrder,
  savePurchaseOrder,
  updatePurchaseOrderStatus,
  type PurchaseOrderDraft,
} from "@/lib/api-v2";
import { exportPurchaseOrderReport } from "@/lib/report-export";

const SERVICE_LEVELS = [0.9, 0.95, 0.975, 0.99];
type ReceiptDraftLine = { qty: string; cost: string };
type ReceiptDrafts = Record<string, Record<string, ReceiptDraftLine>>;

export default function PurchaseOrdersPage() {
  const [drafts, setDrafts] = useState<PurchaseOrderDraft[]>([]);
  const [total, setTotal] = useState(0);
  const [serviceLevel, setServiceLevel] = useState(0.95);
  const [shippingCost, setShippingCost] = useState(35);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [busyPo, setBusyPo] = useState<string | null>(null);
  const [receivingPo, setReceivingPo] = useState<string | null>(null);
  const [receiptDrafts, setReceiptDrafts] = useState<ReceiptDrafts>({});
  const [operationNotice, setOperationNotice] = useState<string | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchPurchaseOrders(serviceLevel, shippingCost, controller.signal)
      .then((r) => {
        if (controller.signal.aborted) return;
        setDrafts(r.drafts);
        setTotal(r.total_capital_required);
        setOperationError(null);
      })
      .catch((e) => {
        if (controller.signal.aborted || isAbortError(e)) return;
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [serviceLevel, shippingCost]);

  if (error) return <p className="page-error-copy">{error}</p>;

  return (
    <div className="po-page">
      <div className="po-toolbar">
        <div>
          <p className="muted small">Service level</p>
          <div className="segmented">
            {SERVICE_LEVELS.map((l) => (
              <button
                key={l}
                type="button"
                className={`segmented-btn${
                  serviceLevel === l ? " segmented-btn-active" : ""
                }`}
                onClick={() => setServiceLevel(l)}
              >
                {(l * 100).toFixed(1)}%
              </button>
            ))}
          </div>
        </div>
        <div className="po-total">
          <p className="muted small">Total capital required, incl. shipping</p>
          <p className="po-total-value">{currency(total)}</p>
        </div>
      </div>
      <div className="po-shipping-control">
        <label className="field-label">
          <span>Estimated shipping / freight per PO</span>
          <input
            className="input-control"
            type="number"
            min="0"
            step="5"
            value={shippingCost}
            onChange={(event) => {
              const next = Number(event.target.value);
              setShippingCost(Number.isFinite(next) ? Math.max(next, 0) : 0);
            }}
          />
        </label>
        <p className="muted small">
          Used in reorder economics so Skubase avoids freight-heavy top-up orders
          that could create overstock.
        </p>
      </div>

      {operationNotice || operationError ? (
        <div className={`po-feedback${operationError ? " po-feedback-error" : ""}`} role="status">
          {operationError ?? operationNotice}
        </div>
      ) : null}

      {loading ? <p className="page-loading">Generating POs…</p> : null}

      {drafts.length === 0 && !loading ? (
        <div className="empty-state">
          <p className="empty-state-title">All caught up</p>
          <p className="empty-state-copy">
            No vendor currently needs a purchase order at this service level.
          </p>
        </div>
      ) : null}

      <div className="po-list">
        {drafts.map((po) => (
          <div key={po.po_id} className="po-card">
            <div
              className="po-card-head"
              onClick={() => setExpanded(expanded === po.po_id ? null : po.po_id)}
            >
              <div>
                <p className="po-card-vendor">{po.vendor}</p>
                <p className="po-card-meta">
                  {po.po_id} · {po.lines.length} line
                  {po.lines.length === 1 ? "" : "s"} · arrives ~
                  {po.expected_arrival_date}
                </p>
              </div>
              <div className="po-card-cost">
                <p className="po-card-total">{currency(po.total_cost)}</p>
                <p className="po-card-meta">
                  {currency(po.subtotal_cost)} items + {currency(po.shipping_cost)} shipping
                </p>
                <span className={`po-status po-status-${po.status}`}>
                  {formatPoStatus(po.status)}
                </span>
              </div>
            </div>
            {expanded === po.po_id ? (
              <div className="po-card-body">
                <p className="po-rationale">{po.rationale}</p>
                <table className="po-table">
                  <thead>
                    <tr>
                      <th>SKU</th>
                      <th>Qty</th>
                      <th>Received</th>
                      <th>Unit cost</th>
                      <th>Extended</th>
                    </tr>
                  </thead>
                  <tbody>
                    {po.lines.map((line) => (
                      <tr key={line.sku_id}>
                        <td>{line.name}</td>
                        <td>{line.qty}</td>
                        <td>
                          {line.received_qty ?? 0} / {line.qty}
                        </td>
                        <td>{currency(line.unit_cost)}</td>
                        <td>{currency(line.extended_cost)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="po-cost-breakdown">
                  <span>Subtotal {currency(po.subtotal_cost)}</span>
                  <span>Shipping {currency(po.shipping_cost)}</span>
                  <strong>Total {currency(po.total_cost)}</strong>
                </div>
                <div className="po-card-actions">
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={() => void saveDraft(po)}
                    disabled={busyPo === po.po_id}
                  >
                    {busyPo === po.po_id ? "Saving..." : "Save draft"}
                  </button>
                  <button
                    type="button"
                    className="button button-secondary"
                    onClick={() => void markStatus(po, "approved")}
                    disabled={busyPo === po.po_id || po.status === "approved"}
                  >
                    {busyPo === po.po_id ? "Approving..." : "Approve PO"}
                  </button>
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={() => {
                      sendPurchaseOrderToVendor(po);
                      void markStatus(po, "sent");
                    }}
                    disabled={busyPo === po.po_id}
                  >
                    {busyPo === po.po_id ? "Sending..." : "Send to vendor"}
                  </button>
                  <button
                    type="button"
                    className="button button-ghost"
                    onClick={() => startPartialReceipt(po)}
                    disabled={busyPo === po.po_id}
                  >
                    Receive partial
                  </button>
                  <button
                    type="button"
                    className="button button-ghost"
                    onClick={() => void receiveAll(po)}
                    disabled={busyPo === po.po_id}
                  >
                    {busyPo === po.po_id ? "Receiving..." : "Receive all"}
                  </button>
                  <button
                    type="button"
                    className="button button-ghost"
                    onClick={() => exportPurchaseOrderReport(po)}
                  >
                    Export styled Excel
                  </button>
                </div>
                {receivingPo === po.po_id ? (
                  <div className="po-receipt-form">
                    <div className="section-heading">
                      <div>
                        <p className="section-eyebrow">Receiving</p>
                        <h3>Record shipment quantities</h3>
                      </div>
                    </div>
                    <table className="po-table">
                      <thead>
                        <tr>
                          <th>SKU</th>
                          <th>Ordered</th>
                          <th>Already received</th>
                          <th>Qty to receive</th>
                          <th>Unit cost</th>
                        </tr>
                      </thead>
                      <tbody>
                        {po.lines.map((line) => {
                          const draftLine = receiptDrafts[po.po_id]?.[line.sku_id] ?? {
                            qty: String(line.qty),
                            cost: line.unit_cost.toFixed(2),
                          };
                          return (
                            <tr key={line.sku_id}>
                              <td>{line.name}</td>
                              <td>{line.qty}</td>
                              <td>{line.received_qty ?? 0}</td>
                              <td>
                                <input
                                  className="input-control"
                                  type="number"
                                  min="0"
                                  max={Math.max(line.qty - (line.received_qty ?? 0), 0)}
                                  step="1"
                                  value={draftLine.qty}
                                  onChange={(event) =>
                                    updateReceiptLine(po.po_id, line.sku_id, {
                                      qty: event.target.value,
                                    })
                                  }
                                />
                              </td>
                              <td>
                                <input
                                  className="input-control"
                                  type="number"
                                  min="0"
                                  step="0.01"
                                  value={draftLine.cost}
                                  onChange={(event) =>
                                    updateReceiptLine(po.po_id, line.sku_id, {
                                      cost: event.target.value,
                                    })
                                  }
                                />
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                    <div className="button-row">
                      <button
                        type="button"
                        className="button button-primary"
                        onClick={() => void recordPartialReceipt(po)}
                        disabled={busyPo === po.po_id}
                      >
                        {busyPo === po.po_id ? "Recording..." : "Record receipt"}
                      </button>
                      <button
                        type="button"
                        className="button button-ghost"
                        onClick={() => setReceivingPo(null)}
                        disabled={busyPo === po.po_id}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );

  async function refresh() {
    const r = await fetchPurchaseOrders(serviceLevel, shippingCost);
    setDrafts(r.drafts);
    setTotal(r.total_capital_required);
  }

  async function saveDraft(po: PurchaseOrderDraft) {
    setBusyPo(po.po_id);
    setOperationError(null);
    setOperationNotice(null);
    try {
      const response = await savePurchaseOrder(po);
      upsertDraft(response.po ?? po);
      setOperationNotice(`Saved draft ${po.po_id}.`);
      if (!isDemoMode()) await refresh();
    } catch (error) {
      setOperationError(errorMessage(error, "Could not save purchase order draft."));
    } finally {
      setBusyPo(null);
    }
  }

  async function markStatus(po: PurchaseOrderDraft, status: PurchaseOrderDraft["status"]) {
    setBusyPo(po.po_id);
    setOperationError(null);
    setOperationNotice(null);
    try {
      await savePurchaseOrder(po);
      const response = await updatePurchaseOrderStatus(po.po_id, status);
      upsertDraft(response.po ?? { ...po, status });
      setOperationNotice(`Purchase order ${po.po_id} marked ${formatPoStatus(status).toLowerCase()}.`);
      if (!isDemoMode()) await refresh();
    } catch (error) {
      setOperationError(errorMessage(error, `Could not mark purchase order ${formatPoStatus(status).toLowerCase()}.`));
    } finally {
      setBusyPo(null);
    }
  }

  function startPartialReceipt(po: PurchaseOrderDraft) {
    setReceivingPo(po.po_id);
    setReceiptDrafts((current) => {
      if (current[po.po_id]) return current;
      return {
        ...current,
        [po.po_id]: Object.fromEntries(
          po.lines.map((line) => [
            line.sku_id,
            { qty: String(Math.max(line.qty - (line.received_qty ?? 0), 0)), cost: line.unit_cost.toFixed(2) },
          ])
        ),
      };
    });
  }

  function updateReceiptLine(
    poId: string,
    skuId: string,
    patch: Partial<ReceiptDraftLine>
  ) {
    setReceiptDrafts((current) => ({
      ...current,
      [poId]: {
        ...current[poId],
        [skuId]: {
          qty: current[poId]?.[skuId]?.qty ?? "",
          cost: current[poId]?.[skuId]?.cost ?? "",
          ...patch,
        },
      },
    }));
  }

  async function recordPartialReceipt(po: PurchaseOrderDraft) {
    const draft = receiptDrafts[po.po_id];
    const lines = po.lines
      .map((line) => {
        const receiptLine = draft?.[line.sku_id];
        const receivedQty = Number(receiptLine?.qty ?? 0);
        const receivedUnitCost = Number(receiptLine?.cost ?? line.unit_cost);
        const remainingQty = Math.max(line.qty - (line.received_qty ?? 0), 0);
        return {
          sku_id: line.sku_id,
          received_qty: Number.isFinite(receivedQty)
            ? Math.min(Math.max(Math.round(receivedQty), 0), remainingQty)
            : 0,
          received_unit_cost: Number.isFinite(receivedUnitCost)
            ? receivedUnitCost
            : line.unit_cost,
        };
      })
      .filter((line) => line.received_qty > 0);

    if (lines.length === 0) {
      setOperationNotice(null);
      setOperationError("Enter at least one quantity to receive.");
      return;
    }

    setBusyPo(po.po_id);
    setOperationError(null);
    setOperationNotice(null);
    try {
      await savePurchaseOrder(po);
      const response = await receivePurchaseOrder(po.po_id, { lines });
      const fallbackPo = applyReceiptToPo(po, lines);
      upsertDraft(response.po ?? fallbackPo);
      setReceivingPo(null);
      setOperationNotice(`Recorded ${sumReceiptQty(lines)} received unit${sumReceiptQty(lines) === 1 ? "" : "s"} for ${po.po_id}.`);
      if (!isDemoMode()) await refresh();
    } catch (error) {
      setOperationError(errorMessage(error, "Could not record purchase order receipt."));
    } finally {
      setBusyPo(null);
    }
  }

  async function receiveAll(po: PurchaseOrderDraft) {
    setBusyPo(po.po_id);
    setOperationError(null);
    setOperationNotice(null);
    try {
      await savePurchaseOrder(po);
      const lines = po.lines.map((line) => ({
        sku_id: line.sku_id,
        received_qty: Math.max(line.qty - (line.received_qty ?? 0), 0),
        received_unit_cost: line.unit_cost,
      })).filter((line) => line.received_qty > 0);
      if (lines.length === 0) {
        setOperationNotice(`Purchase order ${po.po_id} is already fully received.`);
        return;
      }
      const response = await receivePurchaseOrder(po.po_id, { lines });
      upsertDraft(response.po ?? applyReceiptToPo(po, lines));
      setOperationNotice(`Received all remaining units for ${po.po_id}.`);
      if (!isDemoMode()) await refresh();
    } catch (error) {
      setOperationError(errorMessage(error, "Could not receive purchase order."));
    } finally {
      setBusyPo(null);
    }
  }

  function upsertDraft(nextPo: PurchaseOrderDraft) {
    setDrafts((current) =>
      current.map((draft) => (draft.po_id === nextPo.po_id ? nextPo : draft))
    );
  }
}

type ReceiptLinePayload = {
  sku_id: string;
  received_qty: number;
  received_unit_cost?: number | null;
};

function applyReceiptToPo(po: PurchaseOrderDraft, receiptLines: ReceiptLinePayload[]): PurchaseOrderDraft {
  const receivedBySku = new Map(receiptLines.map((line) => [line.sku_id, line.received_qty]));
  const lines = po.lines.map((line) => {
    const receiptQty = receivedBySku.get(line.sku_id) ?? 0;
    return {
      ...line,
      received_qty: Math.min(line.qty, (line.received_qty ?? 0) + receiptQty),
    };
  });
  const fullyReceived = lines.every((line) => line.received_qty >= line.qty);
  const anyReceived = lines.some((line) => line.received_qty > 0);
  return {
    ...po,
    lines,
    status: fullyReceived ? "received" : anyReceived ? "partially_received" : po.status,
    received_at: anyReceived ? new Date().toISOString() : po.received_at,
  };
}

function sumReceiptQty(lines: ReceiptLinePayload[]): number {
  return lines.reduce((sum, line) => sum + line.received_qty, 0);
}

function isDemoMode(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return (
      sessionStorage.getItem("skubase_demo") === "1" ||
      new URLSearchParams(window.location.search).get("demo") === "1"
    );
  } catch {
    return false;
  }
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function formatPoStatus(status: PurchaseOrderDraft["status"]): string {
  return status.replace(/_/g, " ");
}

function isAbortError(error: unknown): boolean {
  return (
    error instanceof DOMException && error.name === "AbortError"
  ) || (
    error instanceof Error &&
    (error.name === "AbortError" || error.message.toLowerCase().includes("aborted"))
  );
}

function sendPurchaseOrderToVendor(po: PurchaseOrderDraft): void {
  const subject = encodeURIComponent(`${po.po_id} purchase order`);
  const body = encodeURIComponent(
    [
      `Purchase order ${po.po_id}`,
      `Vendor: ${po.vendor}`,
      `Expected arrival: ${po.expected_arrival_date}`,
      `Subtotal: ${currency(po.subtotal_cost)}`,
      `Shipping/freight: ${currency(po.shipping_cost)}`,
      `Total: ${currency(po.total_cost)}`,
      "",
      "Lines:",
      ...po.lines.map(
        (line) =>
          `- ${line.name}: ${line.qty} units @ ${currency(line.unit_cost)} = ${currency(
            line.extended_cost
          )}`
      ),
      "",
      po.rationale,
    ].join("\n")
  );

  window.location.href = `mailto:?subject=${subject}&body=${body}`;
}
