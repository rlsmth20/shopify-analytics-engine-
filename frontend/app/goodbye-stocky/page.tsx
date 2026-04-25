import Link from "next/link";

export const metadata = {
  title: "Goodbye Stocky, hello slelfly — slelfly",
  description:
    "Shopify Stocky ends August 31, 2026. slelfly is the Shopify-native replacement: forecasting, supplier scorecards, dead-stock plans, no POS Pro requirement."
};

const compareRows = [
  {
    capability: "Forecasting",
    stocky: "Trailing averages. No seasonality or probability.",
    slelfly: "Holt double-exponential with weekly seasonality and stockout probability on every SKU."
  },
  {
    capability: "Supplier scorecards",
    stocky: "Vendors are free-text. No measurement.",
    slelfly: "On-time delivery, fill rate, lead-time stability, tiering."
  },
  {
    capability: "Dead-stock plans",
    stocky: "Aged-stock flag. No action path.",
    slelfly: "Markdown / bundle / wholesale / write-off plans with dollar impact."
  },
  {
    capability: "Reorder math",
    stocky: "Manual reorder point.",
    slelfly: "Service-level-segmented safety stock + ROP + EOQ."
  },
  {
    capability: "Bundles / kits",
    stocky: "Opaque — kits ordered as SKUs.",
    slelfly: "Decomposed at reorder time so components are never missed."
  },
  {
    capability: "Multi-location transfers",
    stocky: "Not built in.",
    slelfly: "Recommendations to rebalance between locations before ordering."
  },
  {
    capability: "Alerts",
    stocky: "Basic.",
    slelfly: "Rule engine for email, SMS, Slack, and webhooks."
  },
  {
    capability: "Pricing",
    stocky: "Locked to Shopify POS Pro ($89/mo).",
    slelfly: "Published tiers from $49/mo. No POS Pro requirement."
  },
  {
    capability: "Future",
    stocky: "Ending August 31, 2026.",
    slelfly: "Independent, founder-led, public changelog. Built to stay."
  }
];

const steps = [
  {
    number: "1",
    title: "Connect your Shopify store",
    body: "Enter your shop domain and access token on the Store Sync page. We ingest one store at a time, carefully."
  },
  {
    number: "2",
    title: "Bring your Stocky data",
    body: "Export your Stocky inventory, vendors, and lead-time settings as CSV. Our importer maps them into slelfly's model automatically."
  },
  {
    number: "3",
    title: "See your first action in under ten minutes",
    body: "The dashboard ranks your SKUs into urgent / optimize / dead — work the queue from the top."
  },
  {
    number: "4",
    title: "Keep the lights on through August 31",
    body: "Run Stocky and slelfly side-by-side during the transition. We do not charge you to run both while you migrate."
  }
];

export default function GoodbyeStockyPage() {
  return (
    <div className="marketing-shell">
      <header className="marketing-nav">
        <Link href="/" className="marketing-brand">
          <span className="marketing-brand-mark">sf</span>
          <span className="marketing-brand-name">slelfly</span>
        </Link>
        <nav className="marketing-nav-links" aria-label="Primary">
          <Link href="/#pillars">Product</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/about">About</Link>
          <Link href="/changelog">Changelog</Link>
        </nav>
        <div className="marketing-nav-ctas">
          <Link href="/login" className="marketing-link-subtle">
            Sign in
          </Link>
          <Link href="/dashboard" className="button button-primary">
            Open app
          </Link>
        </div>
      </header>

      <section className="marketing-hero marketing-hero-migration">
        <p className="marketing-eyebrow">Stocky sunset · August 31, 2026</p>
        <h1 className="marketing-hero-title">
          Goodbye Stocky. Hello slelfly.
        </h1>
        <p className="marketing-hero-sub">
          Shopify is ending Stocky on August 31, 2026. We built the
          replacement you actually wanted — real forecasting, supplier
          scorecards, and dead-stock plans, Shopify-native, with no POS Pro
          requirement.
        </p>
        <div className="marketing-hero-ctas">
          <Link href="/import-stocky" className="button button-primary button-lg">
            Start migrating today
          </Link>
          <Link href="/pricing" className="button button-ghost button-lg">
            See pricing
          </Link>
        </div>
        <p className="marketing-hero-trust">
          Free during the first 30 days of migration ·
          <strong> Prices locked at renewal</strong>
        </p>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">Side by side</p>
        <h2 className="marketing-section-title">
          What you had in Stocky, and what you get in slelfly.
        </h2>
        <div className="compare-table-wrapper">
          <table className="compare-table">
            <thead>
              <tr>
                <th>Capability</th>
                <th>Stocky</th>
                <th>slelfly</th>
              </tr>
            </thead>
            <tbody>
              {compareRows.map((row) => (
                <tr key={row.capability}>
                  <td className="compare-table-label">{row.capability}</td>
                  <td className="compare-table-old">{row.stocky}</td>
                  <td className="compare-table-new">{row.slelfly}</td>
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
        <h2 className="marketing-section-title">
          Get a head start on August.
        </h2>
        <p className="marketing-section-sub">
          Migrating early means you do not have to rush in July. Open the app,
          connect Shopify, and have your next reorder ready.
        </p>
        <div className="marketing-hero-ctas">
          <Link href="/import-stocky" className="button button-primary button-lg">
            Start migrating
          </Link>
          <Link href="/about" className="button button-ghost button-lg">
            Read our positioning
          </Link>
        </div>
      </section>

      <footer className="marketing-footer">
        <div className="marketing-footer-brand">
          <span className="marketing-brand-mark">sf</span>
          <span>slelfly</span>
        </div>
        <div className="marketing-footer-links">
          <Link href="/">Home</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/about">About</Link>
          <Link href="/changelog">Changelog</Link>
          <Link href="/goodbye-stocky">Stocky migration</Link>
          <Link href="/goodbye-genie">Genie migration</Link>
          <Link href="/login">Sign in</Link>
        </div>
        <p className="marketing-footer-fine">
          © {new Date().getFullYear()} slelfly · Independent · Founder-led ·
          Prices locked at renewal
        </p>
      </footer>
    </div>
  );
}
