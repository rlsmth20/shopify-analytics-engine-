"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import Link from "next/link";
import { useEffect, useState } from "react";

import { SectionCard } from "@/components/section-card";
import {
  authenticatedFetch,
  getEmbeddedShopifyContext,
  reconnectShopify,
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
  const [connectionLoading, setConnectionLoading] = useState(true);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [embeddedShop, setEmbeddedShop] = useState<string | null>(null);
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
    setConnectionLoading(true);
    setConnectionError(null);
    try {
      const res = await authenticatedFetch(`${API_BASE}/integrations/shopify/connection`, {
        credentials: "include",
        signal: AbortSignal.timeout(15_000),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(typeof body?.detail === "string" ? body.detail : `Could not check your Shopify connection (${res.status}).`);
      }
      if (typeof body?.connected !== "boolean") throw new Error("Could not read your Shopify connection. Please try again.");
      setConnection(body);
    } catch (error) {
      setConnectionError(error instanceof Error ? error.message : "Could not load your Shopify connection.");
    } finally {
      setConnectionLoading(false);
    }
  }

  useEffect(() => {
    setEmbeddedShop(getEmbeddedShopifyContext()?.shop || null);
    void loadConnection();
  }, []);

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
    } catch {
      setSyncError("The connection was interrupted before sync could be confirmed. Check the last sync time, then try again.");
      void loadConnection();
    } finally {
      setSyncing(false);
    }
  }

  async function handleReconnect() {
    setInstallError(null);
    setInstallLoading(true);
    try {
      await reconnectShopify(connection?.shopify_domain || undefined);
    } catch (error) {
      setInstallError(error instanceof Error ? error.message : "Could not reconnect Shopify. Please try again.");
    } finally {
      setInstallLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <SectionCard>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Shopify connection</p>
            <h2 className="section-title">
              {connectionLoading ? "Checking Shopify connection…" : connectionError ? "Connection unavailable" : connection?.connected ? "Connected" : "Connect your Shopify store"}
            </h2>
          </div>
          {connectionLoading || connectionError ? null : connection?.connected ? (
            <span className="status-badge status-succeeded">Active</span>
          ) : (
            <span className="status-badge status-failed">Not connected</span>
          )}
        </div>

        {connectionLoading ? (
          <p className="section-copy" role="status">Loading your Shopify connection…</p>
        ) : connectionError ? (
          <div>
            <p className="auth-error" role="alert">{connectionError}</p>
            <button type="button" className="button button-primary" onClick={() => void loadConnection()}>Try again</button>
            <Link href="/billing" className="button button-ghost">View billing</Link>
          </div>
        ) : connection?.connected ? (
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
                onClick={() => void handleReconnect()}
                disabled={installLoading || syncing}
              >
                {installLoading ? "Connecting…" : "Reconnect"}
              </button>
            </div>
            {installError ? <p className="auth-error" role="alert">{installError}</p> : null}
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
            <p className="section-copy">Open skubase from the Apps section of your Shopify Admin. Your store connects automatically when the app opens.</p>
            {embeddedShop ? (
              <button type="button" className="button button-primary" disabled={installLoading} onClick={() => void handleReconnect()}>
                {installLoading ? "Connecting…" : "Reconnect this store"}
              </button>
            ) : (
              <a className="button button-primary" href="https://admin.shopify.com" target="_top">Open Shopify Admin</a>
            )}
            {installError ? <p className="auth-error" role="alert">{installError}</p> : null}
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
