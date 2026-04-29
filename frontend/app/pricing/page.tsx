import Link from "next/link";

import { PricingTable } from "@/components/pricing-table";
import { MarketingNav } from "@/components/marketing-nav";
import { TrialExpiredBanner } from "@/components/trial-expired-banner";

export const metadata = {
  title: "Pricing — skubase",
  description: "Three published tiers. No quote-only pricing. A written price-lock clause that renewals cannot raise the rate on your plan.",
  alternates: { canonical: "/pricing" },
  openGraph: {
    title: "Pricing — skubase",
    description: "Three published tiers ($49/$149/$349) with a written price-lock pledge. Pay annually, save 15%.",
    url: "/pricing",
    type: "website",
  },
};

const FAQ_LD = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: [
    { "@type": "Question", name: "Do you raise prices at renewal?", acceptedAnswer: { "@type": "Answer", text: "No. Every plan has a written price-lock clause in the terms of service: we will not raise the monthly or annual rate on a plan you are already subscribed to." } },
    { "@type": "Question", name: "Is there a free tier?", acceptedAnswer: { "@type": "Answer", text: "Every plan starts with a 14-day free trial, no credit card required. After the trial the Starter plan is $49/mo." } },
    { "@type": "Question", name: "How long does setup take?", acceptedAnswer: { "@type": "Answer", text: "Most merchants see their first ranked action in under ten minutes. We do not require a paid implementation partner." } },
    { "@type": "Question", name: "Can I pay annually?", acceptedAnswer: { "@type": "Answer", text: "Yes — pay annually and save 15%. Annual customers also get a contractual price lock on the annual rate." } },
  ],
};

const faqs = [
  { q: "Do you raise prices at renewal?", a: "No. Every plan has a written price-lock clause in the terms of service: we will not raise the monthly or annual rate on a plan you are already subscribed to for as long as you maintain the subscription." },
  { q: "What happens if I exceed my SKU or location limit?", a: "We notify you by email, the app shows a soft banner, and you get thirty days to decide whether to upgrade or prune. We will never silently auto-upgrade your plan." },
  { q: "Is there a free tier?", a: "Every plan starts with a 14-day free trial, no credit card required. After the trial the Starter plan is $49/mo." },
  { q: "How long does setup take?", a: "Most merchants see their first ranked action in under ten minutes. We do not require a paid implementation partner." },
  { q: "Can I pay annually?", a: "Yes — pay annually and save 15%. Annual customers also get a contractual price lock on the annual rate." },
  { q: "How do you compare to Stocky / Inventory Planner / Cin7?", a: "Compared with Stocky we add real forecasting, supplier scorecards, and dead-stock plans. Compared with Inventory Planner we publish our price and commit to not raising it. Compared with Cin7 we publish our price and do not require a 6-month implementation." }
];

export default function PricingPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />
      <TrialExpiredBanner />

      <section className="marketing-hero">
        <p className="marketing-eyebrow">Pricing</p>
        <h1 className="marketing-hero-title">Three tiers. Published. Locked.</h1>
        <p className="marketing-hero-sub">
          We publish our prices on this page because the rest of the market hides them behind a sales call &mdash; and raises them at renewal. We commit in writing that renewals do not raise the rate on your plan.
        </p>
      </section>

      <PricingTable />

      <section className="pricing-lock">
        <div className="pricing-lock-card">
          <p className="pricing-lock-kicker">The skubase price-lock pledge</p>
          <h2 className="pricing-lock-title">Your rate will not go up at renewal.</h2>
          <p className="pricing-lock-body">
            We built this product because the inventory market is full of tools whose prices triple at renewal after an acquisition. Inventory Planner users reported roughly a 3&times; price hike after Sage. Linnworks users reported a 681% hike after a PE rollup. We are not doing that to you.
          </p>
          <p className="pricing-lock-body">
            The specific commitment, which appears in the <Link href="/terms">terms of service</Link>: once you start a subscription at a published price, that price does not increase for as long as you maintain the subscription.
          </p>
        </div>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">FAQ</p>
        <h2 className="marketing-section-title">The questions we hear the most.</h2>
        <div className="faq-grid">
          {faqs.map((f) => (
            <article key={f.q} className="faq-card">
              <h3 className="faq-card-q">{f.q}</h3>
              <p className="faq-card-a">{f.a}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="marketing-footer">
        <div className="marketing-footer-brand">
          <span className="marketing-brand-mark">sb</span>
          <span>skubase</span>
        </div>
        <div className="marketing-footer-links">
          <Link href="/">Home</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/about">About</Link>
          <Link href="/blog">Blog</Link>
          <Link href="/changelog">Changelog</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">© {new Date().getFullYear()} skubase · Prices locked at renewal</p>
      </footer>

      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(FAQ_LD) }} />
    </div>
  );
}

