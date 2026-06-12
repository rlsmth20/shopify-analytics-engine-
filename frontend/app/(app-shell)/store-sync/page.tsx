"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import Link from "next/link";
import { useEffect, useState } from "react";

import { SectionCard } from "@/components/section-card";
import {
  authenticatedFetch,
  getEmbeddedShopifyContext,
  redirectTopLevel,
} from "@/lib/shopify-embedded";

const API_BASE = APP_API_BASE_URL;

type Connection = {
  connected: boolean;
  shopify_domain: string | null;
  last_sync_at: string | null;
  scope: string | null;
};

type SyncResult = {
  status?: string;
  products_count?: number;
  products_scanned?: number;
  variants_imported?: number;
  order_line_items_count?: number;
  orders_scanned?: number;
  line_items_scanned?: number;
  line_items_imported?: number;
  line_items_skipped?: number;
  top_skip_reason?: string | null;
  stored_token_has_read_orders?: boolean;
  token_lacks_read_orders?: boolean;
  no_eligible_recent_orders_found?: boolean;
  orders_error?: string | null;
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
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);

  const shouldExplainZeroOrderItems = Boolean(
    syncResult &&
      (syncResult.order_line_items_count ?? 0) === 0 &&
      ((syncResult.orders_scanned ?? 0) > 0 ||
        (syncResult.line_items_scanned ?? 0) > 0 ||
        syncResult.token_lacks_read_orders ||
        syncResult.no_eligible_recent_orders_found ||
        syncResult.orders_error)
  );

  async function loadConnection() {
    try {
      const res = await authenticatedFetch(`${API_BASE}/integrations/shopify/connection`, {
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
      const embedded = getEmbeddedShopifyContext();
      const params = new URLSearchParams({ shop: shopInput.trim() });
      if (embedded?.host) params.set("host", embedded.host);
      const res = await authenticatedFetch(`${API_BASE}/integrations/shopify/install?${params}`, {
        credentials: "include",
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        setInstallError(body?.detail || `Install failed (${res.status}).`);
        return;
      }
      if (body?.authorize_url) {
        // Shopify's OAuth page refuses to render inside the app iframe.
        redirectTopLevel(body.authorize_url);
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
      const res = await authenticatedFetch(`${API_BASE}/integrations/shopify/sync`, {
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
            <div className="sync-safety-note" role="status">
              <strong>Read-only sync.</strong> skubase imports products,
              inventory, and order history for forecasting. It does not change
              Shopify inventory quantities, prices, products, or orders from
              this screen.
            </div>
            <div className="button-row">
              <button
                type="button"
                className="button button-primary"
                onClick={handleSyncNow}
                disabled={syncing}
              >
                {syncing ? "Syncing…" : "Sync now"}
              </button>
              <button
                type="button"
                className="button button-ghost"
                onClick={async () => {
                  const domain = connection?.shopify_domain || "";
                  if (!domain) return;
                  const embedded = getEmbeddedShopifyContext();
                  const params = new URLSearchParams({ shop: domain });
                  if (embedded?.host) params.set("host", embedded.host);
                  const res = await authenticatedFetch(
                    `${API_BASE}/integrations/shopify/install?${params}`,
                    { credentials: "include" }
                  );
                  const body = await res.json().catch(() => null);
                  if (body?.authorize_url) {
                    redirectTopLevel(body.authorize_url);
                  }
                }}
              >
                Reconnect
              </button>
            </div>
            {syncError ? (
              <p className="auth-error" style={{ marginTop: "16px" }}>
                {syncError}
              </p>
            ) : null}
            {syncResult ? (
              <div className="sync-safety-note" role="status" style={{ marginTop: "16px" }}>
                <p className="section-copy" style={{ margin: 0 }}>
                  Synced{" "}
                  <strong>{(syncResult.variants_imported ?? syncResult.products_count ?? 0).toLocaleString()}</strong>{" "}
                  product variants and{" "}
                  <strong>{(syncResult.order_line_items_count ?? 0).toLocaleString()}</strong>{" "}
                  order line items.
                </p>
                <p className="section-copy" style={{ margin: "8px 0 0" }}>
                  Products scanned:{" "}
                  <strong>{(syncResult.products_scanned ?? 0).toLocaleString()}</strong>.
                  Orders scanned:{" "}
                  <strong>{(syncResult.orders_scanned ?? 0).toLocaleString()}</strong>.
                  Line items scanned:{" "}
                  <strong>{(syncResult.line_items_scanned ?? 0).toLocaleString()}</strong>.
                  Line items skipped:{" "}
                  <strong>{(syncResult.line_items_skipped ?? 0).toLocaleString()}</strong>.
                </p>
                {syncResult.top_skip_reason ? (
                  <p className="section-copy" style={{ margin: "8px 0 0" }}>
                    Top skip reason: <strong>{syncResult.top_skip_reason}</strong>.
                  </p>
                ) : null}
                {syncResult.token_lacks_read_orders ? (
                  <p className="section-copy" style={{ margin: "8px 0 0" }}>
                    Reconnect Shopify to approve the updated order access scope.
                  </p>
                ) : null}
                {syncResult.no_eligible_recent_orders_found ? (
                  <p className="section-copy" style={{ margin: "8px 0 0" }}>
                    No eligible recent paid orders were found in the Shopify order access window.
                  </p>
                ) : null}
              </div>
            ) : null}
            {shouldExplainZeroOrderItems ? (
              <div className="import-error" role="alert" style={{ marginTop: "12px" }}>
                <strong>No order line items were imported.</strong>{" "}
                Reconnect Shopify if order access was recently added.
                <p className="section-copy" style={{ margin: "8px 0 0" }}>
                  Skubase needs recent Shopify orders to calculate sales velocity,
                  forecasts, and bundle opportunities.
                </p>
                <p className="section-copy" style={{ margin: "8px 0 0" }}>
                  Orders without customers should still be imported for inventory
                  forecasting.
                </p>
              </div>
            ) : null}
            {syncResult?.status === "partial" && syncResult.orders_error ? (
              <div className="import-error" role="alert" style={{ marginTop: "12px" }}>
                <strong>Products synced, but order history did not.</strong>{" "}
                {syncResult.orders_error}
              </div>
            ) : null}
          </>
        ) : (
          <>
            <p className="section-copy">
              Install the skubase app on your Shopify store. We&apos;ll pull
              products, inventory, and recent paid orders so the
              forecast and action queue can run on real data.
            </p>
            <div className="sync-safety-note" role="status">
              <strong>Safe by default.</strong> Initial Shopify access is
              read-only for planning. Any future write-back flow should require
              a preview and explicit approval before touching Shopify stock.
            </div>
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
