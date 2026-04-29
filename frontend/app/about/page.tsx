import Link from "next/link";

import { WaitlistForm } from "@/components/waitlist-form";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "About â€” skubase",
  description: "Independent, founder-led, Shopify-first. No PE squeeze.",
  alternates: { canonical: "/about" },
  openGraph: { title: "About skubase â€” Independent. Founder-led. No PE squeeze.", description: "Eight of the inventory tools you evaluate were acquired and got worse. skubase is structurally outside that pattern.", url: "/about", type: "website" },
};

const beliefs = [
  { title: "Inventory is a decision problem, not a reporting problem.", body: "Most inventory tools are dashboards â€” they tell you what happened and leave you to act. skubase ranks the decisions: what to reorder, what is overstocked, what is dead, what to do first." },
  { title: "Math should be visible.", body: "Every recommended quantity explains itself. Trailing demand, seasonality factor, service level, stockout probability â€” all on the card, all clickable." },
  { title: "Suppliers are measurable.", body: "23 of 25 tools we studied treat vendors as contact records. We treat them as performers. On-time delivery, fill rate, lead-time stability, tiering. Facts, not feelings." },
  { title: "Dead stock is a cash recovery problem.", body: "24 of 25 tools flag aged inventory and stop. We propose the specific plan â€” markdown, bundle, wholesale, or write-off â€” with the dollar impact attached." },
  { title: "Pricing should be published and locked.", body: "7 of 25 tools are quote-only. 6 of 25 have public complaints about renewal-time price hikes. We publish our prices and commit in writing not to raise them." }
];

const notLikeUs = [
  { competitor: "Inventory Planner", owner: "Sage (2021)", pattern: "Users reported ~3Ã— price hikes and support regression after the acquisition." },
  { competitor: "Linnworks", owner: "Marlin Equity (PE)", pattern: "Trustpilot reviews cite a 681% renewal price hike and support collapse." },
  { competitor: "Veeqo", owner: "Amazon (2021)", pattern: "Non-Amazon merchants raised data concerns; roadmap visibly slowed." },
  { competitor: "Skubana", owner: "Extensiv", pattern: "Forced platform migration created documented churn and billing confusion." },
  { competitor: "Cin7 Core (DEAR)", owner: "Cin7", pattern: "Post-rebrand price restructuring moved legacy DEAR contracts up tiers." },
  { competitor: "Sellbrite", owner: "GoDaddy (2019)", pattern: "Users describe the roadmap as frozen for two-plus years." },
  { competitor: "Brightpearl", owner: "Sage (2022)", pattern: "Quote-only pricing, 6-month implementations, post-acquisition support slips." },
  { competitor: "SKUVault", owner: "Linnworks (2022)", pattern: "Same PE owner as Linnworks; buyers now wary." }
];

export default function AboutPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero">
        <p className="marketing-eyebrow">About skubase</p>
        <h1 className="marketing-hero-title">Independent. Founder-led. Shopify-first.</h1>
        <p className="marketing-hero-sub">
          Eight of the 25 inventory tools we benchmark against have been acquired by a parent that raised prices, slowed the roadmap, or broke support. skubase is structurally outside that pattern.
        </p>
      </section>

      <section className="about-pledge">
        <div className="about-pledge-card">
          <p className="about-pledge-kicker">Our commitments to you</p>
          <ul className="about-pledge-list">
            <li><strong>No PE squeeze.</strong> We are founder-owned and not raising venture capital on terms that force renewal hikes.</li>
            <li><strong>No surprise price changes.</strong> Your rate at sign-up is your rate for as long as you stay subscribed. That is in the <Link href="/terms">terms of service</Link>.</li>
            <li><strong>No quote-only pricing.</strong> Every tier is published on the pricing page.</li>
            <li><strong>No consultant-required onboarding.</strong> Most merchants see their first ranked action in under ten minutes.</li>
            <li><strong>A public changelog.</strong> Every release lands on the <Link href="/changelog">changelog page</Link>.</li>
          </ul>
        </div>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">What we believe</p>
        <h2 className="marketing-section-title">Five ideas that shape the product.</h2>
        <div className="beliefs-grid">
          {beliefs.map((b) => (
            <article key={b.title} className="belief-card">
              <h3 className="belief-card-title">{b.title}</h3>
              <p className="belief-card-body">{b.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-section-alt">
        <p className="marketing-section-kicker">Why independence matters</p>
        <h2 className="marketing-section-title">The tools you evaluated and what happened to them.</h2>
        <p className="marketing-section-sub">Documented patterns from public reviews. We cite them because the pattern is real and our independence is a concrete difference, not a slogan.</p>
        <div className="acquisitions-list">
          {notLikeUs.map((n) => (
            <article key={n.competitor} className="acquisition-card">
              <div>
                <p className="acquisition-card-name">{n.competitor}</p>
                <p className="acquisition-card-owner">{n.owner}</p>
              </div>
              <p className="acquisition-card-pattern">{n.pattern}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-cta-section">
        <p className="marketing-section-kicker">Get early access</p>
        <h2 className="marketing-section-title">If this take resonates, get on the list.</h2>
        <p className="marketing-section-sub">
          skubase is in private beta. Drop your email â€” we&apos;ll send your invite when paid plans launch.
        </p>
        <WaitlistForm source="about" ctaLabel="Get early access" />
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
        <p className="marketing-footer-fine">Â© {new Date().getFullYear()} skubase Â· Independent Â· Founder-led</p>
      </footer>
    </div>
  );
}

