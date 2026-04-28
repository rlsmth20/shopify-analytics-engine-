"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

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

const PLAN_LABELS: Record<string, string> = {
  starter_monthly: "Starter ($49/mo)",
  growth_monthly: "Growth ($149/mo)",
  scale_monthly: "Scale ($349/mo)",
  starter_annual: "Starter (annual)",
  growth_annual: "Growth (annual)",
  scale_annual: "Scale (annual)",
  none: "No active plan",
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export default function BillingPage() {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [portalLoading, setPortalLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/billing/me`, { credentials: "include" })
      .then((r) => r.json())
      .then((data) => setSub(data as Subscription))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  async function openPortal() {
    setPortalLoading(true);
    try {
      const res = await fetch(`${API_BASE}/billing/portal`, {
        method: "POST",
        credentials: "include",
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        alert(body?.detail || `Could not open the billing portal (${res.status}).`);
        return;
      }
      if (body?.url) window.location.href = body.url;
    } finally {
      setPortalLoading(false);
    }
  }

  if (loading) {
    return <div className="page-loading">Loading billing…</div>;
  }
  if (error) {
    return (
      <div className="page-error">
        <p className="page-error-title">Could not load billing</p>
        <p className="page-error-copy">{error}</p>
      </div>
    );
  }
  if (!sub) return null;

  const isActive = sub.status === "active" || sub.status === "trialing";

  return (
    <div className="page-stack">
      <div className="content-grid content-grid-2-1">
        <SectionCard>
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">Current plan</p>
              <h2 className="section-title">
                {PLAN_LABELS[sub.plan] ?? sub.plan}
              </h2>
            </div>
            <span
              className={`status-badge ${
                isActive ? "status-succeeded" : "status-failed"
              }`}
            >
              {sub.status}
            </span>
          </div>

          <div className="plan-card">
            <p className="section-copy">
              {isActive
                ? `Your subscription is active. Next billing date: ${formatDate(sub.current_period_end)}.`
                : sub.stripe_configured
                ? "You don't have an active subscription yet. Pick a plan to get started."
                : "Billing isn't enabled on this workspace yet. Subscriptions will activate when paid plans launch."}
            </p>
            {sub.cancel_at_period_end ? (
              <p className="section-copy" style={{ marginTop: "8px", color: "#b91c1c" }}>
                Set to cancel at period end — your access continues until {formatDate(sub.current_period_end)}.
              </p>
            ) : null}
          </div>

          <div className="button-row">
            {isActive ? (
              <button
                type="button"
                className="button button-primary"
                onClick={openPortal}
                disabled={portalLoading}
              >
                {portalLoading ? "Opening…" : "Manage billing"}
              </button>
            ) : (
              <Link href="/pricing" className="button button-primary">
                See plans
              </Link>
            )}
          </div>
        </SectionCard>

        <SectionCard>
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">Price-lock pledge</p>
              <h2 className="section-title section-title-small">Your rate is locked</h2>
            </div>
          </div>
          <p className="section-copy">
            Once you start a subscription at a published price, that price does
            not increase for as long as you maintain the subscription. Read the
            full pledge in our{" "}
            <Link href="/terms" className="auth-link">
              terms of service
            </Link>
            .
          </p>
        </SectionCard>
      </div>

      <SectionCard>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Invoices &amp; receipts</p>
            <h2 className="section-title section-title-small">
              Managed in the Stripe Customer Portal
            </h2>
          </div>
        </div>
        <p className="section-copy">
          Stripe hosts your invoice history, payment methods, and tax
          information. Click <strong>Manage billing</strong> above to download
          past invoices, update your card, or change plans.
        </p>
      </SectionCard>
    </div>
  );
}
