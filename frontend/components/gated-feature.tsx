"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import { useAuth } from "@/components/auth-guard";
import {
  PLAN_CAPABILITIES,
  hasCapability,
  planDisplayName,
  planToTier,
  type CapabilityKey,
} from "@/lib/plans";
import { authenticatedFetch, isEmbeddedShopifyContext } from "@/lib/shopify-embedded";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type BillingSummary = {
  plan: string;
  status: string;
  billing_provider?: "stripe" | "shopify";
  shopify_installed?: boolean;
};

export function GatedFeature({
  capability,
  title,
  description,
  children,
}: {
  capability: CapabilityKey;
  title?: string;
  description?: string;
  children: ReactNode;
}) {
  const { user } = useAuth();
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setFailed(false);

    if (user.id === 0 || user.is_admin) {
      setBilling({ plan: "scale_monthly", status: "active" });
      setLoading(false);
      return;
    }

    void authenticatedFetch(`${API_BASE}/billing/me`, { credentials: "include" })
      .then((response) => (response.ok ? response.json() : null))
      .then((data: BillingSummary | null) => {
        if (cancelled) return;
        setBilling(data);
      })
      .catch(() => {
        if (cancelled) return;
        setBilling(null);
        setFailed(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [user.id, user.is_admin]);

  if (loading) {
    return <div className="page-loading">Loading plan access...</div>;
  }

  const active =
    user.id === 0 ||
    user.is_admin ||
    billing?.status === "active" ||
    billing?.status === "trialing";
  const isShopifyInstalled = billing?.billing_provider === "shopify" || billing?.shopify_installed;
  const directTrialAccess =
    Boolean(user.in_trial) && !isShopifyInstalled && !isEmbeddedShopifyContext();
  const tier = directTrialAccess ? "scale" : active ? planToTier(billing?.plan) : null;

  if ((active || directTrialAccess) && hasCapability(tier, capability)) {
    return <>{children}</>;
  }

  const config = PLAN_CAPABILITIES[capability];
  const requiredPlan = planDisplayName(config.requiredPlan);
  return (
    <section className="section-card gated-feature-card">
      <div className="gated-feature-content">
        <p className="section-eyebrow">Plan upgrade</p>
        <h2 className="section-title section-title-small">
          {title ?? `Unlock ${config.title.toLowerCase()}`}
        </h2>
        <p className="section-copy">
          {description ?? config.description}
        </p>
        <div className="gated-feature-panel">
          <strong>{config.cta}</strong>
          <span>
            {isShopifyInstalled
              ? `This feature is included on ${requiredPlan}. Plan approval is handled securely through Shopify.`
              : `This feature is included on ${requiredPlan}. Upgrade from Billing to unlock it.`}
          </span>
        </div>
        {failed ? (
          <p className="section-copy">
            Billing status is unavailable right now, so Skubase is keeping this
            feature locked until plan access can be verified.
          </p>
        ) : null}
        <div className="button-row">
          <Link href="/billing" className="button button-primary">
            {config.cta}
          </Link>
          <Link href="/sample-inventory-risk-snapshot" className="button button-ghost">
            View sample report
          </Link>
        </div>
      </div>
    </section>
  );
}
