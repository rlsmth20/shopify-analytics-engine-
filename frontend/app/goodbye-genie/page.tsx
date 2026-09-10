import Link from "next/link";

import { WaitlistForm } from "@/components/waitlist-form";
import { MarketingNav } from "@/components/marketing-nav";
import { MarketingFooter } from "@/components/marketing-footer";

export const metadata = {
  title: "Goodbye Genie, hello skubase - skubase",
  description: "Plan your next steps after Genie with Skubase forecasts, reorder recommendations, exportable purchase orders, and supplier scorecards.",
  alternates: { canonical: "/goodbye-genie" },
  keywords: ["Genie alternative", "Genie replacement", "Genie shutdown"],
  openGraph: { title: "Goodbye Genie, hello skubase", description: "Inventory planning, exportable purchase orders, and a practical path to getting started after Genie.", url: "/goodbye-genie", type: "website" },
};

const reasons = [
  { title: "A clear daily plan.", body: "See which products need reorder attention and which are tying up cash, with a ranked action queue." },
  { title: "Reorders you can act on.", body: "Review recommended quantities, create supplier-grouped purchase-order drafts, and export them as Excel workbooks." },
  { title: "Suppliers, measured.", body: "Build supplier scorecards from recorded receipts: on-time delivery, fill rate, and lead-time stability. Availability depends on your plan." },
  { title: "Dead stock, acted on.", body: "Compare markdown, bundle, wholesale, and write-off recommendations for slow inventory, with projected recovery where cost data is available." }
];

const steps = [
  { number: "1", title: "Open your workspace", body: "Get a sign-in link and start a 14-day free trial, or explore the sample dashboard first." },
  { number: "2", title: "Add supported inventory and sales data", body: "Use a supported Stocky product CSV and non-Shopify ShipStation shipment history, or sync Shopify if Skubase is already installed. Keep saved Genie files for reference and ask us about mapping your fields." },
  { number: "3", title: "See your first ranked action", body: "Check a few products, set supplier lead times, then review reorder priorities and purchase-order drafts." }
];

export default function GoodbyeGeniePage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero marketing-hero-migration">
        <p className="marketing-eyebrow">Genie closed August 31, 2025</p>
        <h1 className="marketing-hero-title">Your next inventory plan starts here.</h1>
        <p className="marketing-hero-sub">
          Bring your inventory decisions into one place: reorder priorities, exportable purchase orders, supplier scorecards, and plans for slow stock.
        </p>
        <p className="marketing-hero-trust">Genie&apos;s <a href="https://genie.io/blog-articles/we-are-joining-doss">closure announcement</a> set August 31, 2025 as its sunset date. Updated September 9, 2026.</p>
        <p className="marketing-hero-trust">Skubase is in Shopify&apos;s review process and is not yet listed in the Shopify App Store. Start with a CSV workspace or the <Link href="/tools/inventory-health-check">free inventory health check</Link>.</p>
        <WaitlistForm source="goodbye_genie_hero" ctaLabel="Start free trial" />
        <p className="marketing-hero-trust">
          14-day trial · No credit card · <strong>Prices locked at renewal</strong> ·{" "}
          <Link href="/inventory-risk-snapshot">Get a free inventory risk snapshot</Link>
        </p>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">What changes for you</p>
        <h2 className="marketing-section-title">A practical workflow for your next order.</h2>
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
        <p className="marketing-section-kicker">Migration path</p>
        <h2 className="marketing-section-title">Three steps.</h2>
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
        <h2 className="marketing-section-title">Stop improvising.</h2>
        <p className="marketing-section-sub">Start with a few representative products, review your reorder priorities, and build a routine your team can use.</p>
        <WaitlistForm source="goodbye_genie_footer" ctaLabel="Start free trial" />
      </section>

      <MarketingFooter />
    </div>
  );
}
