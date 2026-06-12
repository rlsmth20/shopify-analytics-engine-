import Link from "next/link";

import { MarketingFooter } from "@/components/marketing-footer";
import { MarketingNav } from "@/components/marketing-nav";
import { WaitlistForm } from "@/components/waitlist-form";
import { FEATURE_CATALOG, availabilityBadge } from "@/lib/feature-catalog";

export const metadata = {
  title: "Features - skubase",
  description:
    "Every skubase feature, explained: ranked Action Queue, 90-day forecasting, reorder and PO planning, dead-stock recovery, bundle opportunities, supplier scorecards, transfers, alerts, and scheduled Excel reports.",
  alternates: { canonical: "/features" },
  openGraph: {
    title: "Features - skubase",
    description:
      "What skubase does, in plain language - and exactly which plan includes each feature.",
    url: "/features",
    type: "website",
  },
};

function badgeClass(badge: string): string {
  if (badge === "All plans") return "feature-badge feature-badge-all";
  if (badge === "Growth and up") return "feature-badge feature-badge-growth";
  if (badge === "Scale") return "feature-badge feature-badge-scale";
  return "feature-badge feature-badge-planned";
}

export default function FeaturesPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero">
        <p className="marketing-eyebrow">Features</p>
        <h1 className="marketing-hero-title">Everything skubase does, explained.</h1>
        <p className="marketing-hero-sub">
          No mystery modules, no &ldquo;contact sales to find out.&rdquo; Every feature below says
          what it does, what it needs, and which plan includes it. Every one is live in the demo.
        </p>
        <div className="marketing-hero-ctas">
          <Link href="/dashboard?demo=1" className="button button-primary button-lg">
            Open the live demo
          </Link>
          <Link href="/pricing" className="button button-secondary button-lg">
            Compare plans
          </Link>
        </div>
      </section>

      {FEATURE_CATALOG.map((group) => (
        <section key={group.key} className="marketing-section feature-group" id={group.key}>
          <p className="marketing-section-kicker">{group.title}</p>
          <h2 className="marketing-section-title feature-group-title">{group.tagline}</h2>
          <div className="feature-grid">
            {group.features.map((feature) => {
              const badge = availabilityBadge(feature);
              return (
                <article key={feature.name} className="feature-card">
                  <div className="feature-card-head">
                    <h3 className="feature-card-title">{feature.name}</h3>
                    <span className={badgeClass(badge)}>{badge}</span>
                  </div>
                  <p className="feature-card-body">{feature.description}</p>
                  {feature.detail ? (
                    <p className="feature-card-detail">{feature.detail}</p>
                  ) : null}
                  {feature.demoHref ? (
                    <Link href={feature.demoHref} className="feature-card-link">
                      See it in the demo →
                    </Link>
                  ) : null}
                </article>
              );
            })}
          </div>
        </section>
      ))}

      <section className="marketing-section marketing-cta-section">
        <h2 className="marketing-section-title">See your own inventory in here, not ours.</h2>
        <p className="marketing-section-sub">
          14-day free trial, no credit card. Connect Shopify or drop in a CSV — the first ranked
          action usually lands in under ten minutes.
        </p>
        <WaitlistForm source="features_footer" ctaLabel="Start free trial" />
      </section>

      <MarketingFooter />
    </div>
  );
}
