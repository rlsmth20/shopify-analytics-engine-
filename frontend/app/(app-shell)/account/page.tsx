"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-guard";
import { SectionCard } from "@/components/section-card";
import { fetchEntitlements, type Entitlements } from "@/lib/entitlements";
import { authenticatedFetch, isEmbeddedShopifyContext } from "@/lib/shopify-embedded";

const API_BASE = APP_API_BASE_URL;

type Connection = {
  connected: boolean;
  shopify_domain: string | null;
  last_sync_at: string | null;
};

export default function AccountPage() {
  const { user, logout } = useAuth();
  const [sub, setSub] = useState<Entitlements | null>(null);
  const [conn, setConn] = useState<Connection | null>(null);
  const [embedded, setEmbedded] = useState(false);

  useEffect(() => {
    setEmbedded(isEmbeddedShopifyContext());
  }, []);

  useEffect(() => {
    void fetchEntitlements()
      .then((d) => setSub(d))
      .catch(() => setSub(null));
    void authenticatedFetch(`${API_BASE}/integrations/shopify/connection`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setConn(d as Connection))
      .catch(() => setConn(null));
  }, []);

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
                <p className="signal-copy">Admin</p>
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
              Sign out of all sessions
            </button>
          </div>
        )}
      </SectionCard>

      <div className="content-grid content-grid-2-1">
        <SectionCard>
          {(() => {
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
                      : "Plan details, invoice history, and payment method are managed in the Stripe Customer Portal."
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
                {conn?.connected ? "Connected" : "Not connected"}
              </h2>
            </div>
            <span
              className={`status-badge ${
                conn?.connected ? "status-succeeded" : "status-failed"
              }`}
            >
              {conn?.connected ? "Live" : "Off"}
            </span>
          </div>
          <p className="section-copy">
            {conn?.connected
              ? `Connected to ${conn.shopify_domain}. Manage on the Store Sync page.`
              : "Connect your Shopify store to pull live products and orders."}
          </p>
          <div className="button-row">
            <Link href="/store-sync" className="button button-ghost">
              Manage Shopify
            </Link>
          </div>
        </SectionCard>
      </div>

      <SectionCard>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Workspace access</p>
            <h2 className="section-title section-title-small">Admin/member roles</h2>
          </div>
          <span className="status-badge status-succeeded">
            {user.is_admin ? "Admin" : "Member"}
          </span>
        </div>
        <p className="section-copy">
          Skubase uses workspace roles to separate admin access from day-to-day
          inventory work. Admin users can manage invites and support-level
          workspace changes; members can use the inventory workflows for their
          connected shop.
        </p>
        <div className="button-row">
          <a className="button button-ghost" href="mailto:hello@skubase.io">
            Request workspace change
          </a>
        </div>
      </SectionCard>
    </div>
  );
}
