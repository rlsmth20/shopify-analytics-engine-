"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-guard";
import { SectionCard } from "@/components/section-card";
import { fetchEntitlements, type Entitlements } from "@/lib/entitlements";
import { PRICING_TIERS } from "@/lib/plans";
import {
  authenticatedFetch,
  isEmbeddedShopifyContext,
  redirectTopLevel,
} from "@/lib/shopify-embedded";

const API_BASE = APP_API_BASE_URL;

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
  const [sub, setSub] = useState<Entitlements | null>(null);
  const [loading, setLoading] = useState(true);
  const [portalLoading, setPortalLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shopifyPlanNotice, setShopifyPlanNotice] = useState<string | null>(null);
  const [portalFallbackUrl, setPortalFallbackUrl] = useState<string | null>(null);
  const [embeddedBilling, setEmbeddedBilling] = useState(false);
  const [subscribingPlan, setSubscribingPlan] = useState<string | null>(null);

  const trialDaysLeft: number | null = (() => {
    if (!user.trial_ends_at) return null;
    const ms = new Date(user.trial_ends_at).getTime() - Date.now();
    const days = Math.ceil(ms / (1000 * 60 * 60 * 24));
    return days > 0 ? days : 0;
  })();

  useEffect(() => {
    setEmbeddedBilling(isEmbeddedShopifyContext());
    setLoading(true);
    fetchEntitlements()
      .then((data) => setSub(data))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  async function openStripePortal() {
    setPortalLoading(true);
    setPortalFallbackUrl(null);
    const popup = embeddedBilling ? window.open("about:blank", "_blank") : null;
    if (popup) {
      popup.opener = null;
      popup.document.title = "Opening Stripe billing...";
    }
    try {
      const res = await authenticatedFetch(`${API_BASE}/billing/portal`, {
        method: "POST",
        credentials: "include",
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        if (popup && !popup.closed) popup.close();
        alert(body?.detail || `Could not open the billing portal (${res.status}).`);
        return;
      }
      if (body?.url) {
        if (embeddedBilling) {
          if (popup && !popup.closed) {
            popup.location.href = body.url;
          } else {
            const opened = window.open(body.url, "_blank", "noopener,noreferrer");
            if (!opened) setPortalFallbackUrl(body.url);
          }
        } else {
          window.location.href = body.url;
        }
      } else if (popup && !popup.closed) {
        popup.close();
      }
    } finally {
      setPortalLoading(false);
    }
  }

  function manageShopifyPlan() {
    setShopifyPlanNotice(null);
    if (sub?.shopify_manage_url) {
      redirectTopLevel(sub.shopify_manage_url);
      return;
    }
    setShopifyPlanNotice(
      "Plan changes are managed through Shopify. Open your Shopify Admin app subscription settings or select a plan from the Shopify App Store listing."
    );
  }

  async function reauthorizeShopify() {
    if (!sub?.shopify_domain) {
      setShopifyPlanNotice(
        "We could not determine your store domain. Reconnect from the Store Sync page."
      );
      return;
    }
    const params = new URLSearchParams({ shop: sub.shopify_domain });
    const res = await authenticatedFetch(
      `${API_BASE}/integrations/shopify/install?${params}`,
      { credentials: "include" }
    ).catch(() => null);
    const body = await res?.json().catch(() => null);
    if (body?.authorize_url) {
      redirectTopLevel(body.authorize_url);
    } else {
      setShopifyPlanNotice(
        "Could not start Shopify re-authorization. Try the Store Sync page."
      );
    }
  }

  async function chooseShopifyPlan(plan: string) {
    setShopifyPlanNotice(null);
    setSubscribingPlan(plan);
    try {
      const res = await authenticatedFetch(`${API_BASE}/billing/shopify/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ plan }),
      });
      const body = await res.json().catch(() => null);
      if (res.status === 409) {
        // Stale access token — run OAuth again, then the merchant can retry.
        await reauthorizeShopify();
        return;
      }
      if (!res.ok) {
        setShopifyPlanNotice(
          body?.detail || `Could not start the Shopify plan approval (${res.status}).`
        );
        return;
      }
      if (body?.url) {
        // Shopify's charge-approval page cannot render inside the app iframe.
        redirectTopLevel(body.url);
        return;
      }
      setShopifyPlanNotice("Shopify did not return an approval link. Try again in a moment.");
    } catch {
      setShopifyPlanNotice("Network error - try again in a moment.");
    } finally {
      setSubscribingPlan(null);
    }
  }

  if (loading) {
    return <div className="page-loading">Loading billing...</div>;
  }
  if (error && !sub) {
    return (
      <div className="page-error">
        <p className="page-error-title">Could not load billing</p>
        <p className="page-error-copy">{error}</p>
      </div>
    );
  }
  if (!sub) return null;

  const isActive = sub.subscription_status === "active" || sub.subscription_status === "trialing";
  const isShopifyBilling = sub.is_shopify_installed;
  const showTrialCard = !isShopifyBilling && user.in_trial && !isActive && trialDaysLeft !== null;
  const includedFeaturesByTier = PRICING_TIERS.map((tier) => ({
    ...tier,
    includedFeatures: tier.features.filter((feature) => feature.included).slice(0, 6),
  }));

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
              ? "Your 14-day free trial gives you full access to skubase. Pick a plan before your trial ends to keep your data and settings."
              : "Your free trial has ended. Subscribe to continue using skubase."}
          </p>
        </SectionCard>
      ) : null}

      <div className="content-grid content-grid-2-1">
        <SectionCard>
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">
                {isShopifyBilling ? "Shopify billing" : "Current plan"}
              </p>
              <h2 className="section-title">
                {isActive
                  ? sub.plan_name
                  : isShopifyBilling
                  ? "Choose a Shopify plan"
                  : user.in_trial
                  ? "Free Trial"
                  : sub.plan_name}
              </h2>
            </div>
            <span
              className={`status-badge ${
                isActive ? "status-succeeded" : user.in_trial && !isShopifyBilling ? "status-succeeded" : "status-failed"
              }`}
            >
              {isActive ? sub.subscription_status : user.in_trial && !isShopifyBilling ? "trial" : sub.subscription_status}
            </span>
          </div>

          <div className="plan-card">
            <p className="section-copy">
              {isShopifyBilling
                ? isActive
                  ? `Your Shopify app subscription is active. Next billing date: ${formatDate(sub.current_period_end)}.`
                  : "Pick a plan below - you approve the charge on Shopify's confirmation page and it lands on your Shopify invoice."
                : isActive
                ? `Your subscription is active. Next billing date: ${formatDate(sub.current_period_end)}.`
                : user.in_trial
                ? trialDaysLeft === 0
                  ? "Your trial has ended. Connect your Shopify store to subscribe and keep your access."
                  : `Trial ends ${formatDate(user.trial_ends_at)}. Connect your Shopify store to subscribe when you're ready.`
                : "Subscriptions are billed through Shopify. Connect your Shopify store to pick a plan."}
            </p>
          </div>

          {isShopifyBilling && sub.billing_status_error === "shopify_unauthorized" ? (
            <div className="import-error" role="alert" style={{ marginBottom: "16px" }}>
              <strong>Shopify connection needs attention.</strong> Your store&apos;s
              access token is no longer valid, so billing and sync calls are
              failing. Re-authorize to fix it - your data and settings are kept.
              <div className="button-row" style={{ marginTop: "12px" }}>
                <button
                  type="button"
                  className="button button-primary"
                  onClick={() => void reauthorizeShopify()}
                >
                  Re-authorize skubase
                </button>
              </div>
            </div>
          ) : null}

          <div className="button-row">
            {isShopifyBilling ? (
              isActive ? (
                <button type="button" className="button button-primary" onClick={manageShopifyPlan}>
                  Manage plan in Shopify
                </button>
              ) : null
            ) : isActive ? (
              <>
                <button
                  type="button"
                  className="button button-primary"
                  onClick={openStripePortal}
                  disabled={portalLoading}
                >
                  {portalLoading ? "Opening..." : "Open billing portal"}
                </button>
                {portalFallbackUrl ? (
                  <a
                    href={portalFallbackUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="button button-ghost"
                  >
                    Click here to open billing portal
                  </a>
                ) : null}
              </>
            ) : !isShopifyBilling ? (
              <Link href="/store-sync" className="button button-primary">
                Connect Shopify store
              </Link>
            ) : null}
          </div>
          {error ? <p className="auth-error" style={{ marginTop: "16px" }}>{error}</p> : null}
          {shopifyPlanNotice ? (
            <p className="section-copy" style={{ marginTop: "16px" }}>{shopifyPlanNotice}</p>
          ) : null}
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

      {isShopifyBilling ? (
        <SectionCard>
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">Plans</p>
              <h2 className="section-title section-title-small">
                {isActive ? "Change your plan" : "Choose your plan"}
              </h2>
            </div>
          </div>
          <p className="section-copy">
            Billing runs through Shopify - skubase never collects payment
            details. Charges appear on your Shopify invoice.
          </p>
          <div className="pricing-grid" style={{ marginTop: "24px" }}>
            {PRICING_TIERS.map((tier) => {
              const current = sub.plan_id === tier.key && isActive;
              const subscribing = subscribingPlan === tier.monthly.plan;
              return (
                <article key={tier.key} className={`pricing-card billing-plan-card ${tier.featured ? "pricing-card-featured" : ""}${current ? " billing-plan-card-current" : ""}`}>
                  <div className="billing-plan-card-head">
                    <h3 className="pricing-card-title">{tier.name}</h3>
                    {current ? <span className="status-badge status-succeeded">Current</span> : null}
                  </div>
                  <p className="pricing-card-price">
                    {tier.monthly.price}<span>/mo</span>
                  </p>
                  <p className="section-copy">{tier.pitch}</p>
                  <p className="pricing-card-limit">{tier.limit}</p>
                  <button
                    type="button"
                    className={`button ${current ? "button-ghost" : "button-primary"} button-full`}
                    disabled={current || subscribingPlan !== null}
                    onClick={() => void chooseShopifyPlan(tier.monthly.plan)}
                  >
                    {current
                      ? "Current plan"
                      : subscribing
                      ? "Opening Shopify approval..."
                      : isActive
                      ? `Switch to ${tier.name}`
                      : `Choose ${tier.name}`}
                  </button>
                </article>
              );
            })}
          </div>
          {shopifyPlanNotice ? (
            <p className="auth-error" role="alert" style={{ marginTop: "16px" }}>
              {shopifyPlanNotice}
            </p>
          ) : null}
          <p className="section-copy" style={{ marginTop: "16px" }}>
            Every plan starts with a 14-day free trial. You approve the charge
            on Shopify&apos;s confirmation page, and it appears on your regular
            Shopify invoice.
          </p>
        </SectionCard>
      ) : null}

      <SectionCard>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Plan gates</p>
            <h2 className="section-title section-title-small">What each tier unlocks</h2>
          </div>
        </div>
        <div className="signal-list">
          {includedFeaturesByTier.map((tier) => (
            <div key={tier.key} className="signal-item">
              <div>
                <p className="signal-title">{tier.name}</p>
                <p className="signal-copy">{tier.limit}</p>
                <ul className="billing-feature-list">
                  {tier.includedFeatures.map((feature) => (
                    <li key={feature.label}>{feature.label}</li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </div>
      </SectionCard>

      <SectionCard>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Invoices &amp; receipts</p>
            <h2 className="section-title section-title-small">
              {isShopifyBilling || !isActive
                ? "Managed by Shopify"
                : "Managed in the Stripe Customer Portal"}
            </h2>
          </div>
        </div>
        <p className="section-copy">
          {isShopifyBilling
            ? "Shopify hosts app subscription approval, app charges, invoices, and payment handling for this installed store."
            : isActive
            ? "Stripe hosts your invoice history, payment methods, and tax information. Click Open billing portal above to download past invoices, update your card, or change plans."
            : "Once your Shopify store is connected and you subscribe, app charges and invoices appear in your Shopify admin billing settings."}
        </p>
      </SectionCard>
    </div>
  );
}
