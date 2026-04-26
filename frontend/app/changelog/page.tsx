import Link from "next/link";

export const metadata = {
  title: "Changelog — slelfly",
  description:
    "Every release lands here. Shipping transparently is how we counter the 'roadmap frozen' pattern the rest of the market has earned.",
  alternates: { canonical: "/changelog" },
  openGraph: {
    title: "Changelog — slelfly",
    description: "Every release, on the record. We ship transparently so you never have to wonder whether slelfly is still being built.",
    url: "/changelog",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Changelog — slelfly",
    description: "Every release, on the record. We ship transparently.",
  },
};

type ChangelogEntry = {
  version: string;
  date: string;
  title: string;
  items: { type: "Added" | "Changed" | "Fixed" | "Shipped"; text: string }[];
};

const entries: ChangelogEntry[] = [
  {
    version: "v0.3.0",
    date: "2026-04-24",
    title: "Strategic positioning release",
    items: [
      { type: "Shipped", text: "Public marketing surface: landing page, pricing, about, changelog." },
      { type: "Shipped", text: "Migration landers for Stocky (Aug 31, 2026 sunset) and Genie (Aug 31, 2025 sunset)." },
      { type: "Shipped", text: "Transparent pricing with a written price-lock clause in TOS." },
      { type: "Shipped", text: "Forecast explainability: every recommended quantity explains trailing demand, seasonality factor, and service level." },
      { type: "Changed", text: "Brand renamed from Inventory Command to slelfly." },
      { type: "Changed", text: "Feature page subtitles adopted the report's hero copy across the app." },
      { type: "Added", text: "Alert rules are now persisted to the database — they survive restarts." }
    ]
  },
  {
    version: "v0.2.0",
    date: "2026-04-23",
    title: "Intelligence surface",
    items: [
      { type: "Shipped", text: "Holt double-exponential smoothing with weekly seasonality and stockout probability." },
      { type: "Shipped", text: "ABC × XYZ classification and scorecards." },
      { type: "Shipped", text: "Service-level-segmented safety stock, reorder point, and EOQ." },
      { type: "Shipped", text: "Supplier scorecards and preferred / acceptable / at-risk tiering." },
      { type: "Shipped", text: "Bundle / kit bottleneck analysis — kits decompose at reorder time." },
      { type: "Shipped", text: "Multi-location transfer recommendations." },
      { type: "Shipped", text: "Dead-stock liquidation plans: markdown / bundle / wholesale / write-off." },
      { type: "Shipped", text: "Alert rule engine: email, SMS, Slack, webhook." },
      { type: "Shipped", text: "Redesigned dashboard with chart library and 'What should I do today?' rail." }
    ]
  },
  {
    version: "v0.1.0",
    date: "2026-03-12",
    title: "Mock-data MVP and action feed",
    items: [
      { type: "Shipped", text: "Backend action engine with urgent / optimize / dead outputs." },
      { type: "Shipped", text: "Lead-time hierarchy (SKU > vendor > category > global) with safety buffer." },
      { type: "Shipped", text: "Frontend homepage connected to live /actions." },
      { type: "Shipped", text: "Shopify ingestion scaffolding (one shop at a time)." },
      { type: "Shipped", text: "Shop-scoped settings for lead times and buffers." }
    ]
  }
];

const typeStyle: Record<string, string> = {
  Shipped: "changelog-tag changelog-tag-shipped",
  Added: "changelog-tag changelog-tag-added",
  Changed: "changelog-tag changelog-tag-changed",
  Fixed: "changelog-tag changelog-tag-fixed"
};

export default function ChangelogPage() {
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

      <section className="marketing-hero">
        <p className="marketing-eyebrow">Changelog</p>
        <h1 className="marketing-hero-title">Every release, on the record.</h1>
        <p className="marketing-hero-sub">
          Five of the acquired tools in our competitive set have a roadmap
          that has visibly slowed. We ship transparently so you never have to
          wonder whether slelfly is still being built. It is.
        </p>
      </section>

      <section className="changelog-list">
        {entries.map((entry) => (
          <article key={entry.version} className="changelog-entry">
            <header className="changelog-entry-head">
              <div>
                <p className="changelog-entry-version">{entry.version}</p>
                <h2 className="changelog-entry-title">{entry.title}</h2>
              </div>
              <time className="changelog-entry-date" dateTime={entry.date}>
                {entry.date}
              </time>
            </header>
            <ul className="changelog-entry-items">
              {entry.items.map((item, idx) => (
                <li key={idx} className="changelog-entry-item">
                  <span className={typeStyle[item.type]}>{item.type}</span>
                  <span>{item.text}</span>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </section>

      <section className="marketing-section marketing-cta-section">
        <h2 className="marketing-section-title">
          What&apos;s next?
        </h2>
        <p className="marketing-section-sub">
          In flight: Shopify ingestion swap off mock data, PO approval / send
          flow, Stocky CSV importer, and onboarding concierge for the Stocky
          migration window.
        </p>
        <div className="marketing-hero-ctas">
          <Link href="/dashboard" className="button button-primary button-lg">
            Open the app
          </Link>
          <Link href="/pricing" className="button button-ghost button-lg">
            See pricing
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
