"use client";

import { useEffect, useState } from "react";

import {
  currency,
  fetchPurchaseOrders,
  type PurchaseOrderDraft,
} from "@/lib/api-v2";

const SERVICE_LEVELS = [0.9, 0.95, 0.975, 0.99];

export default function PurchaseOrdersPage() {
  const [drafts, setDrafts] = useState<PurchaseOrderDraft[]>([]);
  const [total, setTotal] = useState(0);
  const [serviceLevel, setServiceLevel] = useState(0.95);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

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
                    className="button-primary"
                    onClick={() => sendPurchaseOrderToVendor(po)}
                  >
                    Send to vendor
                  </button>
                  <button
                    type="button"
                    className="button-ghost"
                    onClick={() => exportPurchaseOrderCsv(po)}
                  >
                    Export CSV
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
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

function exportPurchaseOrderCsv(po: PurchaseOrderDraft): void {
  const headers = ["po_id", "vendor", "sku_id", "sku_name", "qty", "unit_cost", "extended_cost"];
  const rows = po.lines.map((line) => ({
    po_id: po.po_id,
    vendor: po.vendor,
    sku_id: line.sku_id,
    sku_name: line.name,
    qty: String(line.qty),
    unit_cost: line.unit_cost.toFixed(2),
    extended_cost: line.extended_cost.toFixed(2),
  }));
  const csv = [
    headers.join(","),
    ...rows.map((row) =>
      headers.map((header) => escapeCsv(row[header as keyof typeof row])).join(",")
    ),
  ].join("\r\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${po.po_id.toLowerCase()}-${slugify(po.vendor)}.csv`;
  link.click();
  window.URL.revokeObjectURL(url);
}

function escapeCsv(value: string): string {
  if (/[",\n\r]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }

  return value;
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}
