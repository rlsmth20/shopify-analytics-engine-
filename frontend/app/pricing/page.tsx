import Link from "next/link";

import { MarketingFooter } from "@/components/marketing-footer";
import { MarketingNav } from "@/components/marketing-nav";
import { PlanComparison } from "@/components/plan-comparison";
import { PricingTable } from "@/components/pricing-table";
import { TrialExpiredBanner } from "@/components/trial-expired-banner";

export const metadata = {
  title: "Pricing - skubase",
  description: "Published Skubase pricing for action-first Shopify inventory planning, configurable alerts, reorder recommendations, and reports.",
  alternates: { canonical: "/pricing" },
  openGraph: {
    title: "Pricing - skubase",
    description: "Three published tiers for Shopify inventory alerts, Action Queue, reorder planning, and Reports & Exports.",
    url: "/pricing",
    type: "website",
  },
};

const faqs = [
  { q: "Do you raise prices at renewal?", a: "Your monthly or annual subscription rate is locked for as long as you maintain the subscription on the same plan. The terms of service describe the commitment and exceptions for external fees and taxes." },
  { q: "What happens if I exceed my SKU or location limit?", a: "Plan limits are listed above. If your catalog, locations, or team grows beyond your plan, contact us to review the right fit. We do not silently auto-upgrade your plan." },
  { q: "Is there a free tier?", a: "Every plan starts with a 14-day free trial, no credit card required. After the trial the Starter plan is $29/mo." },
  { q: "Do alerts send automatically?", a: "Yes. Enabled alert rules are evaluated automatically and delivered through the channels you configure and enable. You can also preview an evaluation before sending." },
  { q: "Which alert channels are included?", a: "Starter includes email and Slack alert channels. Growth and Scale add webhook channels. Channels must be configured before notifications are delivered. SMS alerts are planned and are not currently available." },
  { q: "What does setup involve?", a: "Connect Shopify, complete the initial sync, then review your inventory signals and reorder assumptions. Setup time depends on your catalog size and available data. The free sample snapshot shows the kind of output you can review before connecting a store." },
  { q: "Can I pay annually?", a: "Yes. Annual plans save about 15% compared with twelve monthly payments. The monthly equivalent is rounded to the nearest cent; the displayed annual total is billed once per year. The same price-lock terms apply." },
  { q: "Which plan fits my workflow?", a: "Starter covers ranked inventory actions, stock alerts, and dead-stock guidance. Growth adds demand forecasts, purchase-order planning, and Excel exports. Scale adds scheduled reports and supplier scorecards, which require purchase-order receipt history." },
  { q: "Does SKUbase execute inventory changes in Shopify?", a: "SKUbase provides read-only Shopify analysis and planning. Purchase-order drafts, receipt records, and transfer recommendations do not change stock in Shopify. The current sync imports total stock per SKU without a location breakdown, so it does not yet populate location-level transfer recommendations." },
];

const FAQ_LD = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: faqs.map(({ q, a }) => ({
    "@type": "Question",
    name: q,
    acceptedAnswer: { "@type": "Answer", text: a },
  })),
};

export default function PricingPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />
      <TrialExpiredBanner />

      <section className="marketing-hero">
        <p className="marketing-eyebrow">Pricing</p>
        <h1 className="marketing-hero-title">Clear plans for your next inventory decision.</h1>
        <p className="marketing-hero-sub">
          Start with ranked stock risks and alerts. Add forecasting, purchase plans, and reports as your workflow grows. Every plan has published pricing and a written price-lock commitment.
        </p>
        <div className="marketing-hero-ctas">
          <Link href="/inventory-risk-snapshot" className="button button-secondary button-lg">
            Get a free inventory risk snapshot
          </Link>
        </div>
      </section>

      <PricingTable />

      <p className="plan-matrix-footnote">
        Prices are in USD. Annual plans show a rounded monthly equivalent and the total billed yearly.
        Shopify sync is read-only and currently imports total stock per SKU, without a location breakdown.
      </p>

      <PlanComparison />

      <section className="marketing-section">
        <p className="marketing-section-kicker">Alerts + Action Queue</p>
        <h2 className="marketing-section-title">Stay ahead of inventory issues.</h2>
        <p className="marketing-section-sub">
          Use configurable storewide alerts and the Action Queue to catch stockout risk, dead stock, overstock, forecast risk, and reorder needs before they become expensive.
        </p>
        <div className="faq-grid">
          <article className="faq-card">
            <h3 className="faq-card-q">Configurable rules</h3>
            <p className="faq-card-a">Set clear trigger values for stockout risk, reorder buffer, overstock days of cover, dead-stock capital, forecast risk, and supplier slip.</p>
          </article>
          <article className="faq-card">
            <h3 className="faq-card-q">Automatic delivery</h3>
            <p className="faq-card-a">Enabled rules are checked automatically and sent to the email, Slack, or webhook destinations you configure.</p>
          </article>
          <article className="faq-card">
            <h3 className="faq-card-q">Action-first follow-up</h3>
            <p className="faq-card-a">Alerts point back to the Action Queue, Reorder / POs, Dead Stock, and Reports & Exports workflows.</p>
          </article>
        </div>
      </section>

      <section className="pricing-lock">
        <div className="pricing-lock-card">
          <p className="pricing-lock-kicker">The skubase price-lock pledge</p>
          <h2 className="pricing-lock-title">Your rate will not go up at renewal.</h2>
          <p className="pricing-lock-body">
            Plan your software budget alongside your inventory budget. Your monthly or annual subscription rate stays locked while you maintain the same plan.
          </p>
          <p className="pricing-lock-body">
            The <Link href="/terms">terms of service</Link> set out the price-lock commitment, including exceptions for externally mandated fees and taxes. Plan limits and a change of plan are separate from that commitment.
          </p>
        </div>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">FAQ</p>
        <h2 className="marketing-section-title">Before you choose a plan.</h2>
        <div className="faq-grid">
          {faqs.map((f) => (
            <article key={f.q} className="faq-card">
              <h3 className="faq-card-q">{f.q}</h3>
              <p className="faq-card-a">{f.a}</p>
            </article>
          ))}
        </div>
      </section>

      <MarketingFooter />

      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(FAQ_LD) }} />
    </div>
  );
}
