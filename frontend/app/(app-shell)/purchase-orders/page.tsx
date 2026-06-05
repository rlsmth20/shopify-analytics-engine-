"use client";

import { useEffect, useState } from "react";

import {
  currency,
  fetchPurchaseOrders,
  receivePurchaseOrder,
  savePurchaseOrder,
  updatePurchaseOrderStatus,
  type PurchaseOrderDraft,
  type PurchaseOrderLine,
} from "@/lib/api-v2";
import { exportPurchaseOrderReport } from "@/lib/report-export";

const SERVICE_LEVELS = [0.9, 0.95, 0.975, 0.99];
type ReceiptDraftLine = { qty: string; cost: string };
type ReceiptDrafts = Record<string, Record<string, ReceiptDraftLine>>;
type EditablePoLine = {
  sku_id: string;
  name: string;
  qty: string;
  unit_cost: string;
  received_qty: number;
};
type EditablePoDraft = {
  vendor: string;
  expected_arrival_date: string;
  shipping_cost: string;
  rationale: string;
  lines: EditablePoLine[];
};
type EditablePoDrafts = Record<string, EditablePoDraft>;

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
  const [editingPo, setEditingPo] = useState<string | null>(null);
  const [editDrafts, setEditDrafts] = useState<EditablePoDrafts>({});
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
                {editingPo === po.po_id ? (
                  <PurchaseOrderEditForm
                    po={po}
                    draft={editDrafts[po.po_id] ?? toEditablePoDraft(po)}
                    busy={busyPo === po.po_id}
                    onUpdate={(patch) => updateEditDraft(po.po_id, patch)}
                    onLineUpdate={(index, patch) => updateEditLine(po.po_id, index, patch)}
                    onAddLine={() => addEditLine(po.po_id)}
                    onRemoveLine={(index) => removeEditLine(po.po_id, index)}
                    onSave={() => void saveEditedPo(po)}
                    onCancel={() => cancelEditingPo(po.po_id)}
                  />
                ) : (
                  <>
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
                            <td>
                              <strong>{line.name}</strong>
                              <span className="po-line-sku">{line.sku_id}</span>
                            </td>
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
                  </>
                )}
                <div className="po-card-actions">
                  <button
                    type="button"
                    className="button button-secondary"
                    onClick={() => startEditingPo(po)}
                    disabled={busyPo === po.po_id || editingPo === po.po_id || po.status === "received" || po.status === "cancelled"}
                  >
                    Edit PO
                  </button>
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={() => void saveDraft(po)}
                    disabled={busyPo === po.po_id || editingPo === po.po_id}
                  >
                    {busyPo === po.po_id ? "Saving..." : "Save draft"}
                  </button>
                  <button
                    type="button"
                    className="button button-secondary"
                    onClick={() => void markStatus(po, "approved")}
                    disabled={busyPo === po.po_id || editingPo === po.po_id || po.status === "approved"}
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
                    disabled={busyPo === po.po_id || editingPo === po.po_id}
                  >
                    {busyPo === po.po_id ? "Sending..." : "Send to vendor"}
                  </button>
                  <button
                    type="button"
                    className="button button-ghost"
                    onClick={() => startPartialReceipt(po)}
                    disabled={busyPo === po.po_id || editingPo === po.po_id}
                  >
                    Receive partial
                  </button>
                  <button
                    type="button"
                    className="button button-ghost"
                    onClick={() => void receiveAll(po)}
                    disabled={busyPo === po.po_id || editingPo === po.po_id}
                  >
                    {busyPo === po.po_id ? "Receiving..." : "Receive all"}
                  </button>
                  <button
                    type="button"
                    className="button button-ghost"
                    onClick={() => exportPurchaseOrderReport(po)}
                    disabled={editingPo === po.po_id}
                  >
                    Export styled Excel
                  </button>
                </div>
                {receivingPo === po.po_id && editingPo !== po.po_id ? (
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

  async function saveDraft(po: PurchaseOrderDraft): Promise<boolean> {
    setBusyPo(po.po_id);
    setOperationError(null);
    setOperationNotice(null);
    try {
      const response = await savePurchaseOrder(po);
      upsertDraft(response.po ?? po);
      setOperationNotice(`Saved draft ${po.po_id}.`);
      if (!isDemoMode()) await refresh();
      return true;
    } catch (error) {
      setOperationError(errorMessage(error, "Could not save purchase order draft."));
      return false;
    } finally {
      setBusyPo(null);
    }
  }

  async function saveEditedPo(po: PurchaseOrderDraft) {
    const editedPo = buildEditedPo(po, editDrafts[po.po_id] ?? toEditablePoDraft(po));
    if (!editedPo) return;

    const saved = await saveDraft(editedPo);
    if (saved) {
      setEditingPo(null);
      setEditDrafts((current) => {
        const { [po.po_id]: _removed, ...rest } = current;
        return rest;
      });
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
    setEditingPo(null);
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

  function startEditingPo(po: PurchaseOrderDraft) {
    setReceivingPo(null);
    setEditingPo(po.po_id);
    setEditDrafts((current) => ({
      ...current,
      [po.po_id]: current[po.po_id] ?? toEditablePoDraft(po),
    }));
  }

  function cancelEditingPo(poId: string) {
    setEditingPo(null);
    setOperationError(null);
    setEditDrafts((current) => {
      const { [poId]: _removed, ...rest } = current;
      return rest;
    });
  }

  function updateEditDraft(poId: string, patch: Partial<EditablePoDraft>) {
    setEditDrafts((current) => ({
      ...current,
      [poId]: {
        ...(current[poId] ?? emptyEditablePoDraft()),
        ...patch,
      },
    }));
  }

  function updateEditLine(
    poId: string,
    index: number,
    patch: Partial<EditablePoLine>
  ) {
    setEditDrafts((current) => {
      const draft = current[poId] ?? emptyEditablePoDraft();
      return {
        ...current,
        [poId]: {
          ...draft,
          lines: draft.lines.map((line, lineIndex) =>
            lineIndex === index ? { ...line, ...patch } : line
          ),
        },
      };
    });
  }

  function addEditLine(poId: string) {
    setEditDrafts((current) => {
      const draft = current[poId] ?? emptyEditablePoDraft();
      return {
        ...current,
        [poId]: {
          ...draft,
          lines: [
            ...draft.lines,
            {
              sku_id: "",
              name: "",
              qty: "1",
              unit_cost: "0.00",
              received_qty: 0,
            },
          ],
        },
      };
    });
  }

  function removeEditLine(poId: string, index: number) {
    setEditDrafts((current) => {
      const draft = current[poId] ?? emptyEditablePoDraft();
      return {
        ...current,
        [poId]: {
          ...draft,
          lines: draft.lines.filter((_line, lineIndex) => lineIndex !== index),
        },
      };
    });
  }

  function buildEditedPo(
    po: PurchaseOrderDraft,
    draft: EditablePoDraft
  ): PurchaseOrderDraft | null {
    const vendor = draft.vendor.trim();
    const expectedArrivalDate = draft.expected_arrival_date.trim();
    const rationale = draft.rationale.trim();
    const shipping = parseMoney(draft.shipping_cost);

    if (!vendor) {
      setOperationError("Vendor is required before saving the purchase order.");
      return null;
    }
    if (!expectedArrivalDate) {
      setOperationError("Expected arrival date is required before saving the purchase order.");
      return null;
    }
    if (shipping === null) {
      setOperationError("Shipping / freight must be a valid non-negative number.");
      return null;
    }

    const lines = draft.lines
      .map((line) => normalizeEditableLine(line))
      .filter((line): line is PurchaseOrderLine => Boolean(line));

    if (lines.length === 0) {
      setOperationError("Add at least one valid PO line before saving.");
      return null;
    }

    const subtotal = lines.reduce((sum, line) => sum + line.extended_cost, 0);
    return {
      ...po,
      vendor,
      expected_arrival_date: expectedArrivalDate,
      rationale: rationale || "Manually edited purchase order.",
      lines,
      subtotal_cost: roundCurrency(subtotal),
      shipping_cost: shipping,
      total_cost: roundCurrency(subtotal + shipping),
    };
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
    setDrafts((current) => {
      const exists = current.some((draft) => draft.po_id === nextPo.po_id);
      const nextDrafts = exists
        ? current.map((draft) => (draft.po_id === nextPo.po_id ? nextPo : draft))
        : [nextPo, ...current];
      setTotal(sumPoTotals(nextDrafts));
      return nextDrafts;
    });
  }
}

function PurchaseOrderEditForm({
  po,
  draft,
  busy,
  onUpdate,
  onLineUpdate,
  onAddLine,
  onRemoveLine,
  onSave,
  onCancel,
}: {
  po: PurchaseOrderDraft;
  draft: EditablePoDraft;
  busy: boolean;
  onUpdate: (patch: Partial<EditablePoDraft>) => void;
  onLineUpdate: (index: number, patch: Partial<EditablePoLine>) => void;
  onAddLine: () => void;
  onRemoveLine: (index: number) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  const preview = previewEditablePoTotals(draft);

  return (
    <div className="po-edit-form">
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">Edit purchase order</p>
          <h3>Adjust quantities, costs, freight, and line items</h3>
        </div>
      </div>
      <div className="po-edit-grid">
        <label className="field-label">
          <span>Vendor</span>
          <input
            className="input-control"
            value={draft.vendor}
            onChange={(event) => onUpdate({ vendor: event.target.value })}
          />
        </label>
        <label className="field-label">
          <span>Expected arrival</span>
          <input
            className="input-control"
            type="date"
            value={draft.expected_arrival_date}
            onChange={(event) => onUpdate({ expected_arrival_date: event.target.value })}
          />
        </label>
        <label className="field-label">
          <span>Shipping / freight</span>
          <input
            className="input-control"
            type="number"
            min="0"
            step="0.01"
            value={draft.shipping_cost}
            onChange={(event) => onUpdate({ shipping_cost: event.target.value })}
          />
        </label>
      </div>
      <label className="field-label">
        <span>Rationale / internal note</span>
        <textarea
          className="input-control po-edit-note"
          value={draft.rationale}
          onChange={(event) => onUpdate({ rationale: event.target.value })}
        />
      </label>
      <div className="po-edit-lines">
        <div className="po-edit-lines-head">
          <p className="section-eyebrow">Lines</p>
          <button type="button" className="button button-ghost" onClick={onAddLine}>
            Add line
          </button>
        </div>
        <div className="po-edit-line-list">
          {draft.lines.map((line, index) => {
            const qty = parseWholeNumber(line.qty);
            const unitCost = parseMoney(line.unit_cost);
            const extended =
              qty === null || unitCost === null ? 0 : roundCurrency(qty * unitCost);
            const minQty = line.received_qty ?? 0;
            return (
              <div className="po-edit-line-row" key={`${po.po_id}-${index}`}>
                <label className="field-label">
                  <span>SKU</span>
                  <input
                    className="input-control"
                    value={line.sku_id}
                    onChange={(event) => onLineUpdate(index, { sku_id: event.target.value })}
                  />
                </label>
                <label className="field-label po-edit-product-field">
                  <span>Product</span>
                  <input
                    className="input-control"
                    value={line.name}
                    onChange={(event) => onLineUpdate(index, { name: event.target.value })}
                  />
                </label>
                <label className="field-label">
                  <span>Qty</span>
                  <input
                    className="input-control"
                    type="number"
                    min={minQty}
                    step="1"
                    value={line.qty}
                    onChange={(event) => onLineUpdate(index, { qty: event.target.value })}
                  />
                </label>
                <label className="field-label">
                  <span>Unit cost</span>
                  <input
                    className="input-control"
                    type="number"
                    min="0"
                    step="0.01"
                    value={line.unit_cost}
                    onChange={(event) => onLineUpdate(index, { unit_cost: event.target.value })}
                  />
                </label>
                <div className="po-edit-extended">
                  <span>Extended</span>
                  <strong>{currency(extended)}</strong>
                  {minQty > 0 ? <small>{minQty} already received</small> : null}
                </div>
                <button
                  type="button"
                  className="button button-ghost po-line-remove"
                  onClick={() => onRemoveLine(index)}
                  disabled={draft.lines.length === 1 || minQty > 0}
                  title={minQty > 0 ? "Received lines cannot be removed" : undefined}
                >
                  Remove
                </button>
              </div>
            );
          })}
        </div>
      </div>
      <div className="po-edit-summary">
        <span>Subtotal {currency(preview.subtotal)}</span>
        <span>Shipping {currency(preview.shipping)}</span>
        <strong>Total {currency(preview.total)}</strong>
      </div>
      <div className="button-row">
        <button
          type="button"
          className="button button-primary"
          onClick={onSave}
          disabled={busy}
        >
          {busy ? "Saving..." : "Save changes"}
        </button>
        <button
          type="button"
          className="button button-ghost"
          onClick={onCancel}
          disabled={busy}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function toEditablePoDraft(po: PurchaseOrderDraft): EditablePoDraft {
  return {
    vendor: po.vendor,
    expected_arrival_date: po.expected_arrival_date,
    shipping_cost: String(po.shipping_cost ?? 0),
    rationale: po.rationale,
    lines: po.lines.map((line) => ({
      sku_id: line.sku_id,
      name: line.name,
      qty: String(line.qty),
      unit_cost: line.unit_cost.toFixed(2),
      received_qty: line.received_qty ?? 0,
    })),
  };
}

function emptyEditablePoDraft(): EditablePoDraft {
  return {
    vendor: "",
    expected_arrival_date: "",
    shipping_cost: "0",
    rationale: "",
    lines: [],
  };
}

function normalizeEditableLine(line: EditablePoLine): PurchaseOrderLine | null {
  const skuId = line.sku_id.trim();
  const name = line.name.trim();
  const qty = parseWholeNumber(line.qty);
  const unitCost = parseMoney(line.unit_cost);
  const alreadyReceived = Math.max(Math.round(line.received_qty ?? 0), 0);

  if (!skuId || !name || qty === null || unitCost === null) return null;

  const safeQty = Math.max(qty, alreadyReceived, 1);
  return {
    sku_id: skuId,
    name,
    qty: safeQty,
    unit_cost: unitCost,
    extended_cost: roundCurrency(safeQty * unitCost),
    received_qty: Math.min(alreadyReceived, safeQty),
  };
}

function previewEditablePoTotals(draft: EditablePoDraft): {
  subtotal: number;
  shipping: number;
  total: number;
} {
  const subtotal = draft.lines.reduce((sum, line) => {
    const qty = parseWholeNumber(line.qty);
    const unitCost = parseMoney(line.unit_cost);
    if (qty === null || unitCost === null) return sum;
    return sum + qty * unitCost;
  }, 0);
  const shipping = parseMoney(draft.shipping_cost) ?? 0;
  return {
    subtotal: roundCurrency(subtotal),
    shipping,
    total: roundCurrency(subtotal + shipping),
  };
}

function parseWholeNumber(value: string): number | null {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) return null;
  return Math.round(parsed);
}

function parseMoney(value: string): number | null {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) return null;
  return roundCurrency(parsed);
}

function roundCurrency(value: number): number {
  return Math.round(value * 100) / 100;
}

function sumPoTotals(drafts: PurchaseOrderDraft[]): number {
  return roundCurrency(drafts.reduce((sum, po) => sum + po.total_cost, 0));
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
