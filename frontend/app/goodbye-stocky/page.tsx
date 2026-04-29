import Link from "next/link";

import { WaitlistForm } from "@/components/waitlist-form";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "Goodbye Stocky, hello skubase — skubase",
  description: "Shopify Stocky ends August 31, 2026. skubase is the Shopify-native replacement.",
  alternates: { canonical: "/goodbye-stocky" },
  keywords: ["Stocky alternative", "Stocky replacement", "Stocky sunset"],
  openGraph: { title: "Goodbye Stocky, hello skubase", description: "Shopify Stocky ends August 31, 2026.", url: "/goodbye-stocky", type: "website" },
};

const compareRows = [
  { capability: "Forecasting", stocky: "Trailing averages.", skubase: "Holt double-exponential with weekly seasonality and stockout probability." },
  { capability: "Supplier scorecards", stocky: "Vendors are free-text.", skubase: "On-time delivery, fill rate, lead-time stability, tiering." },
  { capability: "Dead-stock plans", stocky: "Aged-stock flag.", skubase: "Markdown / bundle / wholesale / write-off plans." },
  { capability: "Reorder math", stocky: "Manual reorder point.", skubase: "Service-level-segmented safety stock + ROP + EOQ." },
  { capability: "Alerts", stocky: "Basic.", skubase: "Rule engine for email, SMS, Slack, webhooks." },
  { capability: "Pricing", stocky: "POS Pro $89/mo.", skubase: "Published from $49/mo. No POS Pro requirement." },
  { capability: "Future", stocky: "Ending August 31, 2026.", skubase: "Independent, founder-led, public changelog." }
];

const steps = [
  { number: "1", title: "Get on the early-access list", body: "Drop your email and Shopify domain. We'll send your invite when paid plans launch — well before August." },
  { number: "2", title: "Bring your Stocky data", body: "Export your Stocky Inventory On Hand and Vendor List. Our importer maps them in one step." },
  { number: "3", title: "See your first ranked action", body: "Under ten minutes, no consultant. Urgent / optimize / dead — work the queue from the top." },
  { number: "4", title: "Run side-by-side through August", body: "Use Stocky and skubase together. We don't charge for the migration window." }
];

export default function GoodbyeStockyPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero marketing-hero-migration">
        <p className="marketing-eyebrow">Stocky sunset · August 31, 2026</p>
        <h1 className="marketing-hero-title">Goodbye Stocky. Hello skubase.</h1>
        <p className="marketing-hero-sub">
          Shopify is ending Stocky on August 31, 2026. We built the replacement — real forecasting, supplier scorecards, dead-stock plans, Shopify-native, no POS Pro requirement.
        </p>
        <WaitlistForm source="goodbye_stocky_hero" ctaLabel="Start free trial" />
        <p className="marketing-hero-trust">
          14-day trial · No credit card · <strong>Prices locked at renewal</strong>
        </p>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">Side by side</p>
        <h2 className="marketing-section-title">What you had in Stocky, and what you get in skubase.</h2>
        <div className="compare-table-wrapper">
          <table className="compare-table">
            <thead><tr><th>Capability</th><th>Stocky</th><th>skubase</th></tr></thead>
            <tbody>
              {compareRows.map((row) => (
                <tr key={row.capability}>
                  <td className="compare-table-label">{row.capability}</td>
                  <td className="compare-table-old">{row.stocky}</td>
                  <td className="compare-table-new">{row.skubase}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="marketing-section marketing-section-alt">
        <p className="marketing-section-kicker">Migration path</p>
        <h2 className="marketing-section-title">Four steps. No consultant.</h2>
        <div className="migration-steps">
          {steps.map((s) => (
            <article key={s.number} className="migration-step">
              <span className="migration-step-number">{s.number}</span>
              <div>
                <h3 className="migration-step-title">{s.title}</h3>
                <p className="migration-step-body">{s.body}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-cta-section">
        <h2 className="marketing-section-title">Get a head start on August.</h2>
        <p className="marketing-section-sub">Migrating early means you don&apos;t have to rush in July.</p>
        <WaitlistForm source="goodbye_stocky_footer" ctaLabel="Start free trial" />
      </section>

      <footer className="marketing-footer">
        <div className="marketing-footer-brand">
          <span className="marketing-brand-mark">sb</span>
          <span>skubase</span>
        </div>
        <div className="marketing-footer-links">
          <Link href="/">Home</Link>
          <Link href="/blog">Blog</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/about">About</Link>
          <Link href="/goodbye-stocky">Stocky migration</Link>
          <Link href="/goodbye-genie">Genie migration</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">© {new Date().getFullYear()} skubase · Prices locked at renewa