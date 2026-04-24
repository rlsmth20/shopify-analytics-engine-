"use client";

import { useEffect, useState } from "react";

import { fetchTransfers, type TransferRecommendation } from "@/lib/api-v2";

export default function TransfersPage() {
  const [transfers, setTransfers] = useState<TransferRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchTransfers(controller.signal)
      .then((r) => setTransfers(r.transfers))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  if (loading && transfers.length === 0) {
    return <div className="page-loading">Pairing locations…</div>;
  }
  if (error) return <p className="page-error-copy">{error}</p>;

  if (transfers.length === 0) {
    return (
      <div className="empty-state">
        <p className="empty-state-title">Inventory is balanced</p>
        <p className="empty-state-copy">
          No inter-location transfers would meaningfully rebalance cover right now.
        </p>
      </div>
    );
  }

  return (
    <div className="transfers-page">
      {transfers.map((t, i) => (
        <div key={i} className="transfer-card">
          <div className="transfer-head">
            <h4 className="transfer-name">{t.name}</h4>
            <span className="transfer-qty">Move {t.qty} units</span>
          </div>
          <div className="transfer-flow">
            <div className="transfer-flow-end">
              <p className="muted small">From</p>
              <p className="transfer-location">{t.from_location}</p>
              <div className="cover-meter">
                <span className="cover-before">{t.from_days_of_cover_before.toFixed(0)}d</span>
                <span className="cover-arrow">→</span>
                <span className="cover-after">{t.from_days_of_cover_after.toFixed(0)}d</span>
              </div>
            </div>
            <div className="transfer-arrow" aria-hidden>
              ↦
            </div>
            <div className="transfer-flow-end">
              <p className="muted small">To</p>
              <p className="transfer-location">{t.to_location}</p>
              <div className="cover-meter">
                <span className="cover-before">{t.to_days_of_cover_before.toFixed(0)}d</span>
                <span className="cover-arrow">→</span>
                <span className="cover-after">{t.to_days_of_cover_after.toFixed(0)}d</span>
              </div>
            </div>
          </div>
          <p className="transfer-rationale">{t.rationale}</p>
        </div>
      ))}
    </div>
  );
}
