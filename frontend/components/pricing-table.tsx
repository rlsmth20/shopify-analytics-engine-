"use client";

import { useState } from "react";

import { PricingButton } from "@/components/pricing-button";

type Cycle = "monthly" | "annual";

type Tier = {
  name: string;
  pitch: string;
  limit: string;
  features: string[];
  featured: boolean;
  monthly: {
    plan: "starter_monthly" | "growth_monthly" | "scale_monthly";
    price: string;
  };
  annual: {
    plan: "starter_annual" | "growth_annual" | "scale_annual";
    price: string;
    /** Total amount billed once per year. */
    yearTotal: string;
  };
};

const TIERS: Tier[] = [
  {
    name: "Starter",
    pitch: "For solo operators and Stocky migrants picking their first replacement.",
    limit: "Up to 500 active SKUs · 1 location · 1 seat",
    features: [
      "Ranked action feed (urgent / optimize / dead)",
      "Holt + seasonality forecasting",
      "ABC × XYZ classification",
      "Supplier records (scoring on higher tiers)",
      "Email + Slack alerts",
      "Shopify-native ingestion",
      "Self-serve setup",
    ],
    featured: false,
    monthly: { plan: "starter_monthly", price: "$49" },
    annual: { plan: "starter_annual", price: "$41.58", yearTotal: "$499" },
  },
  {
    name: "Growth",
    pitch: "Most merchants land here. Full intelligence stack, multi-location, no seat gates.",
    limit: "Up to 5,000 active SKUs · 3 locations · unlimited seats",
    features: [
      "Everything in Starter",
      "Supplier scorecards + tiering",
      "Safety-stock / ROP / EOQ with service-level segmentation",
      "Bundle / kit bottleneck analysis",
      "Multi-location transfer recommendations",
      "Dead-stock liquidation plans",
      "SMS + webhook alerts",
      "Scheduled PDF reports",
    ],
    featured: true,
    monthly: { plan: "growth_monthly", price: "$149" },
    annual: { plan: "growth_annual", price: "$124.92", yearTotal: "$1,499" },
  },
  {
    name: "Scale",
    pitch: "For multi-store operators and teams that want audit + approval flows.",
    limit: "Up to 25,000 active SKUs · 10 locations · unlimited seats",
    features: [
      "Everything in Growth",
      "PO approval + send flow",
      "Audit log and decision snapshots",
      "Workspace roles",
      "Priority support (same-business-day response)",
      "Onboarding concierge",
      "SSO (Google, Microsoft)",
    ],
    featured: false,
    monthly: { plan: "scale_monthly", price: "$349" },
    annual: { plan: "scale_annual", price: "$291.58", yearTotal: "$3,499" },
  },
];

export function PricingTable() {
  const [cycle, setCycle] = useState<Cycle>("monthly");

  return (
    <>
      <div className="pricing-toggle" role="tablist" aria-label="Billing cycle">
        <button
          type="button"
          role="tab"
          aria-selected={cycle === "monthly"}
          className={`pricing-toggle-button${cycle === "monthly" ? " pricing-toggle-active" : ""}`}
          onClick={() => setCycle("monthly")}
        >
          Monthly
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={cycle === "annual"}
          className={`pricing-toggle-button${cycle === "annual" ? " pricing-toggle-active" : ""}`}
          onClick={() => setCycle("annual")}
        >
          Annual <span className="pricing-toggle-badge">Save 15%</span>
        </button>
      </div>

      <section className="pricing-grid">
        {TIERS.map((tier) => {
          const variant = cycle === "monthly" ? tier.monthly : tier.annual;
          const cadence = cycle === "monthly" ? "/mo" : "/mo (billed annually)";
          return (
            <article
              key={tier.name}
              className={`pricing-card${tier.featured ? " pricing-card-featured" : ""}`}
            >
              {tier.featured ? (
                <p className="pricing-card-ribbon">Most merchants pick this</p>
              ) : null}
              <h2 className="pricing-card-name">{tier.name}</h2>
              <p className="pricing-card-pitch">{tier.pitch}</p>
              <p className="pricing-card-price">
                <span className="pricing-card-amount">{variant.price}</span>
                <span className="pricing-card-cadence">{cadence}</span>
              </p>
              {cycle === "annual" ? (
                <p className="pricing-card-year-total">
                  <strong>{tier.annual.yearTotal}</strong> billed once per year
                </p>
              ) : null}
              <p className="pricing-card-limit">{tier.limit}</p>
              <ul className="pricing-card-features">
                {tier.features.map((f) => (
                  <li key={f}>
                    <span className="pricing-feature-tick" aria-hidden>✓</span>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <PricingButton
                plan={variant.plan}
                label={`Subscribe to ${tier.name}`}
                variant={tier.featured ? "primary" : "ghost"}
              />
            </article>
          );
        })}
      </section>
    </>
  );
}
