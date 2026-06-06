"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import { useAuth } from "@/components/auth-guard";
import { entitlementHas, fetchEntitlements, type Entitlements } from "@/lib/entitlements";
import {
  PLAN_CAPABILITIES,
  getUpgradeLabel,
  planDisplayName,
  type CapabilityKey,
} from "@/lib/plans";

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
  const [entitlements, setEntitlements] = useState<Entitlements | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setFailed(false);

    if (user.id === 0) {
      setEntitlements(null);
      setLoading(false);
      return;
    }

    void fetchEntitlements()
      .then((data) => {
        if (!cancelled) setEntitlements(data);
      })
      .catch(() => {
        if (cancelled) return;
        setEntitlements(null);
        setFailed(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [user.id]);

  if (loading) {
    return <div className="page-loading">Loading plan access...</div>;
  }

  if (user.id === 0 || entitlementHas(entitlements, capability)) {
    return <>{children}</>;
  }

  const config = PLAN_CAPABILITIES[capability];
  const requiredPlan = planDisplayName(config.requiredPlan);
  const upgradeLabel = getUpgradeLabel(config.requiredPlan);
  const isShopifyInstalled = Boolean(entitlements?.is_shopify_installed);
  const currentPlan = entitlements ? planDisplayName(entitlements.plan_id) : "Unverified";

  function openSampleWorkspace() {
    try {
      sessionStorage.setItem("skubase_demo", "1");
    } catch {
      // ignore storage failures; the query param still signals demo mode.
    }
    window.location.href = "/dashboard?demo=1";
  }

  return (
    <section className="section-card gated-feature-card">
      <div className="gated-feature-content">
        <div className="gated-feature-head">
          <div>
            <p className="section-eyebrow">Plan upgrade</p>
            <h2 className="section-title section-title-small">
              {title ?? `Unlock ${config.title.toLowerCase()}`}
            </h2>
            <p className="section-copy">{description ?? config.description}</p>
          </div>
          <span className="status-badge status-neutral">{currentPlan}</span>
        </div>
        <div className="gated-feature-panel">
          <div>
            <strong>{upgradeLabel}</strong>
            <span>
              {isShopifyInstalled
                ? `This workflow is included on ${requiredPlan}. Plan changes happen in Shopify.`
                : `This workflow is included on ${requiredPlan}. Upgrade from Billing to unlock it.`}
            </span>
          </div>
          <ul className="gated-feature-list">
            <li>Keep the page visible for context while premium controls stay locked.</li>
            <li>Billing status is checked before Skubase shows upgrade or locked states.</li>
            <li>Data requirements still appear separately once the right plan is active.</li>
          </ul>
        </div>
        {failed ? (
          <p className="section-copy">
            Billing status is unavailable right now, so Skubase is keeping this
            feature locked until plan access can be verified.
          </p>
        ) : null}
        <div className="button-row">
          <Link href="/billing" className="button button-primary">
            {upgradeLabel}
          </Link>
          <button type="button" className="button button-ghost" onClick={openSampleWorkspace}>
            View sample workspace
          </button>
        </div>
      </div>
    </section>
  );
}
