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

const PLAN_LABELS: Record<string, string> = {
  starter_monthly: "Starter ($29/mo)",
  growth_monthly: "Growth ($99/mo)",
  scale_monthly: "Scale ($199/mo)",
  starter_annual: "Starter (annual)",
  growth_annual: "Growth (annual)",
  scale_annual: "Scale (annual)",
  none: "No active plan",
};

function formatDate(iso: string | null): string {
  if (!iso) return "-";
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
  const { user } = useAuth();
  const [sub, setSub] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [portalLoading, setPortalLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trialDaysLeft: number | null = (() => {
    if (!user.trial_ends_at) return null;
    const ms = new Date(user.trial_ends_at).getTime() - Date.now();
    const days = Math.ceil(ms / (1000 * 60 * 60 * 24));
    return days > 0 ? days : 0;
  })();

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
    return <div className="page-loading">Loading billing...</div>;
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

  const showTrialCard = user.in_trial && !isActive && trialDaysLeft !== null;

  return (
    <div className="page-stack">
      {showTrialCard ? (
        <SectionCard>
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">Free trial</p>
              <h2 className="section-title">
                {trialDaysLeft === 0
                  ? "Trial ended"
                  : trialDaysLeft === 1
                  ? "1 day left"
                  : `${trialDaysLeft} days left`}
              </h2>
            </div>
            <span className={`status-badge ${trialDaysLeft > 0 ? "status-succeeded" : "status-failed"}`}>
              {trialDaysLeft > 0 ? "Active" : "Expired"}
            </span>
          </div>
          <p className="section-copy">
            {trialDaysLeft > 0
              ? `Your 14-day free trial gives you full access to skubase. Pick a plan before your trial ends to keep your data and settings.`
              : "Your free trial has ended. Subscribe to continue using skubase."}
          </p>
          <div className="button-row">
            <Link href="/pricing" className="button button-primary">
              See plans & subscribe
            </Link>
          </div>
        </SectionCard>
      ) : null}

      <div className="content-grid content-grid-2-1">
        <SectionCard>
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">Current plan</p>
              <h2 className="section-title">
                {user.in_trial && !isActive
                  ? "Free Trial"
                  : (PLAN_LABELS[sub.plan] ?? sub.plan)}
              </h2>
            </div>
            <span
              className={`status-badge ${
                isActive ? "status-succeeded" : user.in_trial ? "status-succeeded" : "status-failed"
              }`}
            >
              {isActive ? sub.status : user.in_trial ? "trial" : sub.status}
            </span>
          </div>

          <div className="plan-card">
            <p className="section-copy">
              {isActive
                ? `Your subscription is active. Next billing date: ${formatDate(sub.current_period_end)}.`
                : user.in_trial
                ? trialDaysLeft === 0
                  ? "Your trial has ended. Subscribe to keep your access."
                  : `Trial ends ${formatDate(user.trial_ends_at)}. No credit card required to keep exploring until then.`
                : "You don't have an active subscription. Pick a plan to get started."}
            </p>
            {sub.cancel_at_period_end ? (
              <p className="section-copy" style={{ marginTop: "8px", color: "#b91c1c" }}>
                Set to cancel at period end - your access continues until {formatDate(sub.current_period_end)}.
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
                {portalLoading ? "Opening..." : "Manage billing"}
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
