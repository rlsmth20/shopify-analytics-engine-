"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-guard";
import { SectionCard } from "@/components/section-card";
import { fetchEntitlements, type Entitlements } from "@/lib/entitlements";
import { authenticatedFetch, isEmbeddedShopifyContext } from "@/lib/shopify-embedded";
import { accountPlanConfirmed, readAccountConnection, type AccountConnection } from "@/lib/account-data";

const API_BASE = APP_API_BASE_URL;

export default function AccountPage() {
  const { user, logout } = useAuth();
  const [sub, setSub] = useState<Entitlements | null>(null);
  const [conn, setConn] = useState<AccountConnection | null>(null);
  const [embedded, setEmbedded] = useState(false);
  const [planLoading, setPlanLoading] = useState(true);
  const [connectionLoading, setConnectionLoading] = useState(true);
  const [planError, setPlanError] = useState(false);
  const [connectionError, setConnectionError] = useState(false);
  const [planRetry, setPlanRetry] = useState(0);
  const [connectionRetry, setConnectionRetry] = useState(0);

  useEffect(() => {
    setEmbedded(isEmbeddedShopifyContext());
  }, []);

  useEffect(() => {
    if (user.id === 0) return;
    let active = true;
    setPlanLoading(true);
    setPlanError(false);
    void fetchEntitlements({ fresh: planRetry > 0 })
      .then(data => {
        if (!accountPlanConfirmed(data)) throw new Error("Plan status unavailable");
        if (active) setSub(data);
      })
      .catch(() => { if (active) { setPlanError(true); setSub(null); } })
      .finally(() => { if (active) setPlanLoading(false); });
    return () => { active = false; };
  }, [user.id, planRetry]);

  useEffect(() => {
    if (user.id === 0) return;
    const controller = new AbortController();
    setConnectionLoading(true);
    setConnectionError(false);
    void authenticatedFetch(`${API_BASE}/integrations/shopify/connection`, { credentials: "include", signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error("Connection status unavailable");
        return readAccountConnection(await response.json());
      })
      .then(data => { if (!controller.signal.aborted) setConn(data); })
      .catch(() => { if (!controller.signal.aborted) { setConnectionError(true); setConn(null); } })
      .finally(() => { if (!controller.signal.aborted) setConnectionLoading(false); });
    return () => controller.abort();
  }, [user.id, connectionRetry]);

  return (
    <div className="page-stack">
      <SectionCard>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Account</p>
            <h2 className="section-title section-title-small">Profile</h2>
          </div>
        </div>
        <div className="signal-list">
          <div className="signal-item">
            <div>
              <p className="signal-title">{embedded ? "Signed in via" : "Email"}</p>
              <p className="signal-copy">
                {user.email.startsWith("shopify-admin+")
                  ? "Shopify admin"
                  : user.email}
              </p>
            </div>
          </div>
          <div className="signal-item">
            <div>
              <p className="signal-title">Workspace ID</p>
              <p className="signal-copy">#{user.shop_id}</p>
            </div>
          </div>
          {user.is_admin ? (
            <div className="signal-item">
              <div>
                <p className="signal-title">Role</p>
                <p className="signal-copy">Support administrator</p>
              </div>
            </div>
          ) : null}
        </div>
        {embedded ? null : (
          <div className="button-row" style={{ marginTop: "24px" }}>
            <button
              type="button"
              className="button button-ghost"
              onClick={() => {
                void logout();
              }}
            >
              Sign out
            </button>
          </div>
        )}
      </SectionCard>

      <div className="content-grid content-grid-2-1">
        <SectionCard>
          {(() => {
            if (user.id === 0) return <><p className="section-eyebrow">Plan</p><h2 className="section-title section-title-small">Sample workspace</h2><p className="section-copy">Sample data lets you explore the product. Sign in to view your actual plan.</p><Link className="button button-ghost" href="/login">Sign in</Link></>;
            if (planLoading) return <><p className="section-eyebrow">Plan</p><p className="section-copy" role="status">Checking your plan…</p></>;
            if (planError || !sub) return <><p className="section-eyebrow">Plan</p><h2 className="section-title section-title-small">Plan status unavailable</h2><p className="section-copy">We could not confirm your plan. This does not mean your subscription has ended.</p><div className="button-row"><button type="button" className="button button-ghost" onClick={() => setPlanRetry(value => value + 1)}>Retry plan status</button><Link className="button button-ghost" href="/billing">Open billing</Link></div></>;
            const isActive = sub?.subscription_status === "active" || sub?.subscription_status === "trialing";
            const isShopifyBilling = Boolean(sub?.is_shopify_installed);
            const trialDaysLeft: number | null = (() => {
              if (!user.trial_ends_at) return null;
              const ms = new Date(user.trial_ends_at).getTime() - Date.now();
              const d = Math.ceil(ms / (1000 * 60 * 60 * 24));
              return d > 0 ? d : 0;
            })();
            const planLabel = isActive
              ? sub!.plan_name
              : user.in_trial && !isShopifyBilling
              ? trialDaysLeft === null || trialDaysLeft > 0
                ? trialDaysLeft !== null ? `Free Trial - ${trialDaysLeft}d left` : "Free Trial"
                : "Trial ended"
              : (sub?.plan_name ?? "No active plan");
            const badgeClass = isActive || (!isShopifyBilling && user.in_trial && (trialDaysLeft ?? 0) > 0)
              ? "status-succeeded"
              : "status-failed";
            const badgeLabel = isActive ? sub!.subscription_status : user.in_trial && !isShopifyBilling ? "trial" : "inactive";
            return (
              <>
                <div className="section-heading">
                  <div>
                    <p className="section-eyebrow">Plan</p>
                    <h2 className="section-title section-title-small">{planLabel}</h2>
                  </div>
                  <span className={`status-badge ${badgeClass}`}>{badgeLabel}</span>
                </div>
                <p className="section-copy">
                  {isActive
                    ? isShopifyBilling
                      ? "Plan details and app subscription charges are managed through Shopify."
                      : sub.billing_provider === "stripe" ? "Plan details, invoice history, and payment method are managed in the Stripe Customer Portal." : "View your trial and available plans on the billing page."
                    : user.in_trial && !isShopifyBilling
                    ? "You're on a free trial. Subscribe on the billing page before your trial ends."
                    : "No active subscription. Pick a plan to keep your access."}
                </p>
                <div className="button-row">
                  <Link href="/billing" className="button button-primary">
                    {isActive ? "Open billing" : "See plans"}
                  </Link>
                </div>
              </>
            );
          })()}
        </SectionCard>

        <SectionCard>
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">Shopify connection</p>
              <h2 className="section-title section-title-small">
                {user.id === 0 ? "Sample workspace" : connectionLoading ? "Checking connection…" : connectionError || !conn ? "Connection status unavailable" : conn.connected ? "Connected" : "Not connected"}
              </h2>
            </div>
            <span
              className={`status-badge ${
                conn?.connected && !connectionError && !connectionLoading ? "status-succeeded" : ""
              }`}
            >
              {user.id === 0 ? "Demo" : connectionLoading ? "Checking" : connectionError || !conn ? "Unknown" : conn.connected ? "Connected" : "Not linked"}
            </span>
          </div>
          <p className="section-copy">
            {user.id === 0 ? "Sample inventory does not require a Shopify connection." : connectionLoading ? "Loading your saved Shopify connection." : connectionError || !conn ? "We could not confirm the store connection. Try again before reconnecting or changing settings." : conn.connected
              ? `Connected to ${conn.shopify_domain}. Manage on the Store Sync page.`
              : "Open Connect & import for Shopify access guidance or CSV import. Skubase is in Shopify review and is not listed in the App Store yet."}
          </p>
          <div className="button-row">
            {connectionError ? <button type="button" className="button button-ghost" onClick={() => setConnectionRetry(value => value + 1)}>Retry connection status</button> : null}
            <Link href="/store-sync" className="button button-ghost">
              Connect & import
            </Link>
          </div>
        </SectionCard>
      </div>

      <SectionCard>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Workspace access</p>
            <h2 className="section-title section-title-small">Workspace assistance</h2>
          </div>
          <span className="status-badge status-succeeded">
            Support-assisted
          </span>
        </div>
        <p className="section-copy">
          Contact support to request a change to your workspace or account access.
          Self-service team invitations and role management are planned.
        </p>
        <div className="button-row">
          <a className="button button-ghost" href="mailto:info@skubase.io">
            Request workspace change
          </a>
        </div>
      </SectionCard>
    </div>
  );
}
