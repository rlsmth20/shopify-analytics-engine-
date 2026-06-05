"use client";

import { useState } from "react";

import { PRICING_TIERS, type BillingCycle } from "@/lib/plans";

export function PricingTable() {
  const [cycle, setCycle] = useState<BillingCycle>("monthly");

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
        {PRICING_TIERS.map((tier) => {
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
                {tier.features.map((feature) => (
                  <li
                    key={feature.label}
                    className={feature.included ? "" : "pricing-feature-muted"}
                  >
                    <span className="pricing-feature-tick" aria-hidden>
                      {feature.included ? "+" : "-"}
                    </span>
                    <span>{feature.label}</span>
                  </li>
                ))}
              </ul>
            </article>
          );
        })}
      </section>
    </>
  );
}
