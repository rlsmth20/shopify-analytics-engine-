"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-guard";
import { SectionCard } from "@/components/section-card";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type Subscription = {
  plan: string;
  status: string;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  has_payment_method: boolean;
  stripe_configured: boolean;
};

type Connection = {
  connected: boolean;
  shopify_domain: string | null;
  last_sync_at: string | null;
};

const PLAN_LABELS: Record<string, string> = {
  starter_monthly: "Starter ($29/mo)",
  growth_monthly: "Growth ($99/mo)",
  scale_monthly: "Scale ($199/mo)",
  starter_annual: "Starter (annual)",
  growth_annual: "Growth (annual)",
  scale_annual: "Scale (annual)",
  none: "No active plan",
};

export default function AccountPage() {
  const { user, logout } = useAuth();
  const [sub, setSub] = useState<Subscription | null>(null);
  const [conn, setConn] = useState<Connection | null>(null);

  useEffect(() => {
    void fetch(`${API_BASE}/billing/me`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setSub(d as Subscription))
      .catch(() => setSub(null));
    void fetch(`${API_BASE}/integrations/shopify/connection`, { credentials: "include" })
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
              <p className="signal-title">Email</p>
              <p className="signal-copy">{user.email}</p>
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
      </SectionCard>

      <div className="content-grid content-grid-2-1">
        <SectionCard>
          {(() => {
            const isActive = sub?.status === "active" || sub?.status === "trialing";
            const trialDaysLeft: number | null = (() => {
              if (!user.trial_ends_at) return null;
              const ms = new Date(user.trial_ends_at).getTime() - Date.now();
              const d = Math.ceil(ms / (1000 * 60 * 60 * 24));
              return d > 0 ? d : 0;
            })();
            const planLabel = isActive
              ? (PLAN_LABELS[sub!.plan] ?? sub!.plan)
              : user.in_trial
              ? trialDaysLeft === null || trialDaysLeft > 0
                ? trialDaysLeft !== null ? `Free Trial — ${trialDaysLeft}d left` : "Free Trial"
                : "Trial ended"
              : (PLAN_LABELS[sub?.plan ?? "none"] ?? sub?.plan ?? "No active plan");
            const badgeClass = isActive || (user.in_trial && (trialDaysLeft ?? 0) > 0)
              ? "status-succeeded"
              : "status-failed";
            const badgeLabel = isActive ? sub!.status : user.in_trial ? "trial" : "inactive";
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
                    ? "Plan details, invoice history, and payment method are managed in the Stripe Customer Portal."
                    : user.in_trial
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

    </div>
  );
}
