import { InventoryRiskSnapshotCtas } from "@/components/inventory-risk-snapshot-ctas";
import { InventoryRiskSnapshotForm } from "@/components/inventory-risk-snapshot-form";
import { MarketingNav } from "@/components/marketing-nav";
import Link from "next/link";

export const metadata = {
  title: "Free Shopify Inventory Risk Snapshot - skubase",
  description:
    "Find SKUs likely to stock out, sit dead, or tie up cash. Get a practical Shopify inventory action snapshot from skubase.",
  alternates: { canonical: "/inventory-risk-snapshot" },
};

const includes = [
  "Stockout risks",
  "Reorder priorities",
  "Dead-stock cash tied up",
  "Slow movers",
  "Suggested next actions",
];

const audience = [
  "Shopify stores with 50+ SKUs",
  "Stores with variants, bundles, seasonal products, or multiple suppliers",
  "Founders, operators, and ecommerce teams still using spreadsheets or basic Shopify reports",
];

const reassurance = [
  "No credit card required",
  "Sample report available immediately",
  "Browser check works from a SKU summary",
  "No app installation required for the first check",
];

const faqs = [
  {
    q: "Is this only for Shopify?",
    a: "Yes. The snapshot is designed around Shopify inventory, variants, sales velocity, and reorder workflows.",
  },
  {
    q: "Do I need to install anything?",
    a: "No. Start with the browser-based inventory health check, or submit your store URL and context for a review. Skubase is currently in Shopify's review process and is not yet listed in the App Store. We can work from a SKU summary while review is pending.",
  },
  {
    q: "What does the snapshot include?",
    a: "A short SKU-level readout covering likely stockouts, slow movers, cash tied up, reorder priorities, and lead-time risks.",
  },
  {
    q: "Is this free?",
    a: "Yes. The diagnostic is free and does not require a credit card.",
  },
  {
    q: "Is this for small stores?",
    a: "It is most useful once inventory gets complex: roughly 50+ SKUs, variants, seasonal products, bundles, or multiple suppliers.",
  },
  {
    q: "What happens after I submit?",
    a: "We will email the next step from info@skubase.io. Start with the free browser check, then reply with the inventory question you want help interpreting. A store URL alone does not give Skubase access to your inventory data.",
  },
];

export default function InventoryRiskSnapshotPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero snapshot-hero">
        <p className="marketing-eyebrow">Free Shopify Inventory Risk Snapshot</p>
        <h1 className="marketing-hero-title">
          Get a free Shopify inventory risk snapshot
        </h1>
        <p className="marketing-hero-sub">
          Skubase reviews your Shopify sales and inventory data to identify stockout
          risks, slow movers, overstock, and reorder priorities.
        </p>
        <InventoryRiskSnapshotCtas />
        <p className="marketing-hero-trust">
          Built for Shopify merchants with real SKU complexity. The sample report is instant;
          a real analysis needs your inventory and sales summary. Skubase is in Shopify review and is not yet listed in the App Store.
        </p>
        <p className="marketing-hero-trust">Want an immediate first check? <Link href="/tools/inventory-health-check">Check your SKU summary in your browser</Link>. No account, installation or file upload to Skubase is required.</p>
      </section>

      <section className="snapshot-two-column">
        <div>
          <p className="marketing-section-kicker">What the snapshot includes</p>
          <h2 className="marketing-section-title">A practical inventory readout, not another dashboard.</h2>
          <div className="snapshot-card-grid">
            {includes.map((item) => (
              <article key={item} className="snapshot-mini-card">
                <span className="snapshot-check" aria-hidden>+</span>
                <h3>{item}</h3>
              </article>
            ))}
          </div>
        </div>
        <InventoryRiskSnapshotForm />
      </section>

      <section className="marketing-section marketing-section-alt">
        <p className="marketing-section-kicker">Who it is for</p>
        <h2 className="marketing-section-title">For Shopify teams that have outgrown gut-feel inventory planning.</h2>
        <div className="beliefs-grid">
          {audience.map((item) => (
            <article key={item} className="belief-card">
              <h3 className="belief-card-title">{item}</h3>
              <p className="belief-card-body">
                The snapshot is built to find the week&apos;s highest-risk inventory decisions.
              </p>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">How it works</p>
        <h2 className="marketing-section-title">Three steps. Low friction.</h2>
        <div className="migration-steps">
          {[
            ["1", "Submit your store URL", "Send the store and a little context about your inventory issue."],
            ["2", "Check your SKU summary in the browser", "Use stock and units sold over a stated period. Your entries stay in your browser; the tool needs no account or installation."],
            ["3", "Review the priorities and ask for help", "Download the review list and reply to our email with the inventory question you want to solve. We can work with you to understand a missing workflow or feature."],
          ].map(([number, title, body]) => (
            <article key={number} className="migration-step">
              <span className="migration-step-number">{number}</span>
              <div>
                <h3 className="migration-step-title">{title}</h3>
                <p className="migration-step-body">{body}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="snapshot-reassurance" aria-label="Reassurance">
        {reassurance.map((item) => (
          <span key={item}>{item}</span>
        ))}
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">FAQ</p>
        <h2 className="marketing-section-title">Quick answers before you send the store.</h2>
        <div className="faq-grid">
          {faqs.map((faq) => (
            <article key={faq.q} className="faq-card">
              <h3 className="faq-card-q">{faq.q}</h3>
              <p className="faq-card-a">{faq.a}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
