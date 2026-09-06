"use client";

import { useEffect, useState } from "react";
import { SectionCard } from "@/components/section-card";
import { API_BASE_URL } from "@/lib/api-base";
import { authenticatedFetch } from "@/lib/shopify-embedded";

type DataRequest = { id: number; request_id: string; created_at: string; order_count: number };

export default function PrivacyRequestsPage() {
  const [items, setItems] = useState<DataRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<number | null>(null);

  async function loadRequests() {
    setLoading(true);
    setError(null);
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/webhooks/customer-data-requests`, { signal: AbortSignal.timeout(15_000) });
      const body = await response.json().catch(() => null);
      if (!response.ok || !Array.isArray(body?.items)) throw new Error("Could not load privacy requests. Please try again.");
      setItems(body.items);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load privacy requests.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadRequests(); }, []);

  async function downloadRequest(item: DataRequest) {
    setDownloading(item.id);
    setError(null);
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/webhooks/customer-data-requests/${item.id}`, { signal: AbortSignal.timeout(15_000) });
      if (!response.ok) throw new Error("Could not export this request. Refresh the list and try again.");
      const body = await response.json();
      const url = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `skubase-privacy-request-${item.id}.json`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not export this request.");
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="page-stack">
      <SectionCard>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Customer privacy</p>
            <h2 className="section-title">Data access requests</h2>
          </div>
          <button type="button" className="button button-ghost" disabled={loading} onClick={() => void loadRequests()}>Refresh</button>
        </div>
        <p className="section-copy">Review requests Shopify has sent for this store. Download the matching records retained by SKUbase to help respond to your customer. Only share an export with the person entitled to receive it.</p>
        {error ? <p className="auth-error" role="alert">{error}</p> : null}
        {loading ? <p role="status">Loading requests…</p> : items.length === 0 && !error ? <p className="section-copy">No customer data requests have been received for this store.</p> : null}
        {!loading && items.length > 0 ? (
          <div className="lead-time-table-wrap">
            <table className="lead-time-table">
              <thead><tr><th scope="col">Request</th><th scope="col">Received</th><th scope="col">Requested orders</th><th scope="col">Export</th></tr></thead>
              <tbody>{items.map((item) => (
                <tr key={item.id}>
                  <td>{item.request_id || item.id}</td>
                  <td>{new Date(item.created_at).toLocaleString()}</td>
                  <td>{item.order_count}</td>
                  <td><button type="button" className="button button-ghost" disabled={downloading !== null} onClick={() => void downloadRequest(item)}>{downloading === item.id ? "Preparing…" : "Download JSON"}</button></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : null}
      </SectionCard>
    </div>
  );
}
