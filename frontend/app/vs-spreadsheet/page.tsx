import Link from "next/link";

import { WaitlistForm } from "@/components/waitlist-form";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "Better than your spreadsheet — skubase",
  description: "If your forecasting lives in a Google Sheet with a trailing 6-month average, you''re tying up cash you don''t need to. skubase fixes that in ten minutes.",
  alternates: { canonical: "/vs-spreadsheet" },
  openGraph: {
    title: "Your spreadsheet is overstocking you — skubase",
    description: "ShipStation export → Google Sheet → 6-month moving average → reorder. That math is costing you money.",
    url: "/vs-spreadsheet",
    type: "website",
  },
};

const reasons = [
  { title: "A 6-month rule of thumb is a tax on your working capital.", body: "Holding 6 months of cover for an A-item with steady demand is statistically wasteful — that''s a 95th-percentile-plus stockout rule applied to SKUs that only need 30–60 days. The cash gap is real, and it compounds across every reorder cycle." },
  { title: "Trailing averages miss seasonality and trend.", body: "A 6-month moving average is half-blind on every Q4 ramp. skubase fits a Holt double-exponential model with a weekly seasonality factor, so a back-to-school SKU isn''t reordered like a steady-state one." },
  { title: "All SKUs are not equal.", body: "Your A-items deserve a 99% service level; your C-items don''t. skubase segments by ABC × XYZ and sets safety stock per class — the math the spreadsheet can''t do without becoming a part-time job." },
  { title: "Your suppliers are unmeasured.", body: "If your spreadsheet doesn''t track which vendors miss promised lead times, you''re carrying their failures as your stockouts. skubase scores every vendor on on-time, fill rate, and lead-time stability." },
  { title: "Dead stock is a cash recovery problem your sheet ignores.", body: "The Sheet shows you what you have. It does not propose a markdown plan, a bundle, a wholesale list, or a write-off. skubase does — with the dollar impact attached." }
];

const compare = [
  { metric: "Forecasting model", sheet: "Trailing 6-month moving average", skubase: "Holt double-exponential + weekly seasonality + stockout probability" },
  { metric: "Safety stock", sheet: "Same buffer for every SKU", skubase: "Service-level segmented by ABC × XYZ class" },
  { metric: "Reorder trigger", sheet: "Cover < 6 months", skubase: "Days-until-stockout < lead time + safety, ranked by $ impact" },
  { metric: "Supplier accuracy", sheet: "Not tracked", skubase: "On-time %, fill rate, lead-time stability, tiered" },
  { metric: "Bundle/kit logic", sheet: "Manual decomposition", skubase: "Auto-decomposes at reorder time" },
  { metric: "Dead stock action", sheet: "None", skubase: "Markdown / bundle / wholesale / write-off plans" },
  { metric: "Time to update", sheet: "30–60 minutes per week", skubase: "Zero — recomputes when shipments land" },
  { metric: "Auditability", sheet: "Whoever last touched it", skubase: "Every recommended quantity explains itself" }
];

const steps = [
  { n: "1", title: "Drop in your ShipStation export", body: "We accept the standard Orders or Shipments CSV — SKU, quantity, ship date are all we need. ShipStation aggregates Shopify, Amazon, eBay, Walmart, and most other channels, so the import covers everywhere you sell." },
  { n: "2", title: "See your real velocity", body: "Per-SKU 30 / 90 / 180-day shipped units. The number you''ve been eyeballing in the spreadsheet, computed correctly." },
  { n: "3", title: "Get ranked actions", body: "Skubase ranks every SKU into urgent reorders, overstock to draw down, and dead stock to liquidate. Work the queue; close the spreadsheet." }
];

export default function VsSpreadsheetPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero marketing-hero-migration">
        <p className="marketing-eyebrow">vs. your forecasting spreadsheet</p>
        <h1 className="marketing-hero-title">Your reorder math is costing you money.</h1>
        <p className="marketing-hero-sub">
          If your forecasting lives in a Google Sheet — ShipStation export pasted in, six-month trailing average computed, reorder when cover drops below six months — you&apos;re carrying more inventory than you need to and you&apos;re still missing seasonality. skubase fixes both, in under ten minutes.
        </p>
        <WaitlistForm source="vs_spreadsheet_hero" ctaLabel="Get early access" />
        <p className="marketing-hero-trust">
          14-day free trial · No credit card · <strong>Prices locked at renewal</strong>
        </p>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">Why the spreadsheet is wrong</p>
        <h2 className="marketing-section-title">Five things your sheet can&apos;t do — and skubase does by default.</h2>
        <div className="beliefs-grid">
          {reasons.map((r) => (
            <article key={r.title} className="belief-card">
              <h3 className="belief-card-title">{r.title}</h3>
              <p className="belief-card-body">{r.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-section-alt">
        <p className="marketing-section-kicker">Side by side</p>
        <h2 className="marketing-section-title">The math, made visible.</h2>
        <div className="compare-table-wrapper">
          <table className="compare-table">
            <thead>
              <tr><th>Metric</th><th>Your spreadsheet</th><th>skubase</th></tr>
            </thead>
            <tbody>
              {compare.map((row) => (
                <tr key={row.metric}>
                  <td className="compare-table-label">{row.metric}</td>
                  <td className="compare-table-old">{row.sheet}</td>
                  <td className="compare-table-new">{row.skubase}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">How it works</p>
        <h2 className="marketing-section-title">Three steps. No consultant.</h2>
        <div className="migration-steps">
          {steps.map((s) => (
            <article key={s.n} className="migration-step">
              <span className="migration-step-number">{s.n}</span>
              <div>
                <h3 className="migration-step-title">{s.title}</h3>
                <p className="migration-step-body">{s.body}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-cta-section">
        <h2 className="marketing-section-title">Stop reordering by averages. Start reordering by math.</h2>
        <p className="marketing-section-sub">
          The spreadsheet was a heroic fix. skubase is the permanent one.
        </p>
        <WaitlistForm source="vs_spreadsheet_footer" ctaLabel="Get early access" />
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
          <Link href="/vs-spreadsheet">vs. spreadsheet</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">© {new Date().getFullYear()} skubase · Prices locked at renewal</p>
      </footer>
    </div>
  );
}

