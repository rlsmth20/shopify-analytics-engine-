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
                  <button type="button" className="button-primary">
                    Send to vendor
                  </button>
                  <button type="button" className="button-ghost">
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
