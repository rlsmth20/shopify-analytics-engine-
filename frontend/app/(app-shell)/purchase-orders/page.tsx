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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [busyPo, setBusyPo] = useState<string | null>(null);
  const [receivingPo, setReceivingPo] = useState<string | null>(null);
  const [receiptDrafts, setReceiptDrafts] = useState<ReceiptDrafts>({});

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchPurchaseOrders(serviceLevel, controller.signal)
      .then((r) => {
        setDrafts(r.drafts);
        setTotal(r.total_capital_required);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [serviceLevel]);

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
          <p className="muted small">Total capital required</p>
          <p className="po-total-value">{currency(total)}</p>
        </div>
      </div>

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
                <span className={`po-status po-status-${po.status}`}>{po.status}</span>
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
                      <th>Unit cost</th>
                      <th>Extended</th>
                    </tr>
                  </thead>
                  <tbody>
                    {po.lines.map((line) => (
                      <tr key={line.sku_id}>
                        <td>{line.name}</td>
                        <td>{line.qty}</td>
                        <td>{currency(line.unit_cost)}</td>
                        <td>{currency(line.extended_cost)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="po-card-actions">
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={() => void saveDraft(po)}
                    disabled={busyPo === po.po_id}
                  >
                    Save draft
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
                    Send to vendor
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
                    Receive all
                  </button>
                  <button
                    type="button"
                    className="button button-ghost"
                    onClick={() => exportPurchaseOrderReport(po)}
                  >
                    Export report
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
                          <th>Received qty</th>
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
                              <td>
                                <input
                                  className="input-control"
                                  type="number"
                                  min="0"
                                  max={line.qty}
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
                        Record receipt
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
    const r = await fetchPurchaseOrders(serviceLevel);
    setDrafts(r.drafts);
    setTotal(r.total_capital_required);
  }

  async function saveDraft(po: PurchaseOrderDraft) {
    setBusyPo(po.po_id);
    try {
      await savePurchaseOrder(po);
      await refresh();
    } finally {
      setBusyPo(null);
    }
  }

  async function markStatus(po: PurchaseOrderDraft, status: PurchaseOrderDraft["status"]) {
    setBusyPo(po.po_id);
    try {
      await savePurchaseOrder(po);
      await updatePurchaseOrderStatus(po.po_id, status);
      await refresh();
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
            { qty: String(line.qty), cost: line.unit_cost.toFixed(2) },
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
        return {
          sku_id: line.sku_id,
          received_qty: Number.isFinite(receivedQty) ? receivedQty : 0,
          received_unit_cost: Number.isFinite(receivedUnitCost)
            ? receivedUnitCost
            : line.unit_cost,
        };
      })
      .filter((line) => line.received_qty > 0);

    if (lines.length === 0) return;

    setBusyPo(po.po_id);
    try {
      await savePurchaseOrder(po);
      await receivePurchaseOrder(po.po_id, { lines });
      setReceivingPo(null);
      await refresh();
    } finally {
      setBusyPo(null);
    }
  }

  async function receiveAll(po: PurchaseOrderDraft) {
    setBusyPo(po.po_id);
    try {
      await savePurchaseOrder(po);
      await receivePurchaseOrder(po.po_id, {
        lines: po.lines.map((line) => ({
          sku_id: line.sku_id,
          received_qty: line.qty,
          received_unit_cost: line.unit_cost,
        })),
      });
      await refresh();
    } finally {
      setBusyPo(null);
    }
  }
}

function sendPurchaseOrderToVendor(po: PurchaseOrderDraft): void {
  const subject = encodeURIComponent(`${po.po_id} purchase order`);
  const body = encodeURIComponent(
    [
      `Purchase order ${po.po_id}`,
      `Vendor: ${po.vendor}`,
      `Expected arrival: ${po.expected_arrival_date}`,
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
