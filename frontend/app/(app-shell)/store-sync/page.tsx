"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { SectionCard } from "@/components/section-card";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type Connection = {
  connected: boolean;
  shopify_domain: string | null;
  last_sync_at: string | null;
  scope: string | null;
};

function formatRelative(iso: string | null): string {
  if (!iso) return "never";
  try {
    const dt = new Date(iso);
    return dt.toLocaleString();
  } catch {
    return iso;
  }
}

export default function StoreSyncPage() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [shopInput, setShopInput] = useState("");
  const [installLoading, setInstallLoading] = useState(false);
  const [installError, setInstallError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<{
    products_count?: number;
    order_line_items_count?: number;
  } | null>(null);

  async function loadConnection() {
    try {
      const res = await fetch(`${API_BASE}/integrations/shopify/connection`, {
        credentials: "include",
      });
      if (!res.ok) return;
      setConnection(await res.json());
    } catch {
      // best-effort
    }
  }

  useEffect(() => {
    void loadConnection();
  }, []);

  async function handleInstall(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setInstallError(null);
    if (!shopInput.trim()) {
      setInstallError("Enter your myshopify.com domain.");
      return;
    }
    setInstallLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/integrations/shopify/install?shop=${encodeURIComponent(shopInput.trim())}`,
        { credentials: "include" }
      );
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        setInstallError(body?.detail || `Install failed (${res.status}).`);
        return;
      }
      if (body?.authorize_url) {
        window.location.href = body.authorize_url;
      }
    } finally {
      setInstallLoading(false);
    }
  }

  async function handleSyncNow() {
    setSyncError(null);
    setSyncResult(null);
    setSyncing(true);
    try {
      const res = await fetch(`${API_BASE}/integrations/shopify/sync`, {
        method: "POST",
        credentials: "include",
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        setSyncError(body?.detail || `Sync failed (${res.status}).`);
        return;
      }
      setSyncResult(body);
      void loadConnection();
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="page-stack">
      <SectionCard>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Shopify connection</p>
            <h2 className="section-title">
              {connection?.connected ? "Connected" : "Connect your Shopify store"}
            </h2>
          </div>
          {connection?.connected ? (
            <span className="status-badge status-succeeded">Active</span>
          ) : (
            <span className="status-badge status-failed">Not connected</span>
          )}
        </div>

        {connection?.connected ? (
          <>
            <p className="section-copy">
              Connected to <strong>{connection.shopify_domain}</strong>. Last
              sync: {formatRelative(connection.last_sync_at)}.
            </p>
            <div className="button-row">
              <button
                type="button"
                className="button button-primary"
                onClick={handleSyncNow}
                disabled={syncing}
              >
                {syncing ? "Syncing…" : "Sync now"}
              </button>
            </div>
            {syncError ? (
              <p className="auth-error" style={{ marginTop: "16px" }}>
                {syncError}
              </p>
            ) : null}
            {syncResult ? (
              <p className="section-copy" style={{ marginTop: "16px" }}>
                Synced{" "}
                <strong>{(syncResult.products_count ?? 0).toLocaleString()}</strong>{" "}
                product variants and{" "}
                <strong>{(syncResult.order_line_items_count ?? 0).toLocaleString()}</strong>{" "}
                order line items.
              </p>
            ) : null}
          </>
        ) : (
          <>
            <p className="section-copy">
              Install the skubase app on your Shopify store. We&apos;ll pull
              products, inventory, and the last 180 days of orders so the
              forecast and action queue can run on real data.
            </p>
            <form onSubmit={handleInstall} className="auth-form" style={{ maxWidth: "440px" }}>
              <label className="auth-field">
                <span className="auth-field-label">Your myshopify.com domain</span>
                <input
                  type="text"
                  className="auth-input"
                  placeholder="yourshop.myshopify.com"
                  value={shopInput}
                  onChange={(e) => setShopInput(e.target.value)}
                  disabled={installLoading}
                />
              </label>
              {installError ? <p className="auth-error">{installError}</p> : null}
              <button
                type="submit"
                className="button button-primary"
                disabled={installLoading}
              >
                {installLoading ? "Redirecting…" : "Connect Shopify"}
              </button>
            </form>
          </>
        )}
      </SectionCard>

      <SectionCard>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">No Shopify? No problem.</p>
            <h2 className="section-title section-title-small">CSV imports work too</h2>
          </div>
        </div>
        <p className="section-copy">
          You can import your Stocky catalog or your ShipStation shipment
          history as CSV today — same dashboard, same actions, no OAuth
          required.
        </p>
        <div className="button-row">
          <Link href="/import-stocky" className="button button-ghost">
            Import Stocky CSV
          </Link>
          <Link href="/import-shipstation" className="button button-ghost">
            Import ShipStation CSV
          </Link>
        </div>
      </SectionCard>
    </div>
  );
}
