import Link from "next/link";

export const metadata = {
  title: "Changelog — slelfly",
  description: "Every release lands here. Shipping transparently is how we counter the 'roadmap frozen' pattern the rest of the market has earned.",
  alternates: { canonical: "/changelog" },
  openGraph: { title: "Changelog — slelfly", description: "Every release, on the record.", url: "/changelog", type: "website" },
};

type ChangelogEntry = { version: string; date: string; title: string; items: { type: "Added" | "Changed" | "Fixed" | "Shipped"; text: string }[]; };

const entries: ChangelogEntry[] = [
  { version: "v0.4.0", date: "2026-04-25", title: "Pre-launch readiness", items: [
    { type: "Shipped", text: "Waitlist signup form replaces direct dashboard access — slelfly enters private beta." },
    { type: "Shipped", text: "Demo-mode banner on /dashboard so visitors know they're seeing example data." },
    { type: "Shipped", text: "Privacy Policy and Terms of Service pages, including the written price-lock clause." },
    { type: "Shipped", text: "Public blog at /blog with first two posts (Stocky alternatives, why moving averages overstock)." },
    { type: "Shipped", text: "Stocky and ShipStation CSV importers with sample test data." }
  ]},
  { version: "v0.3.0", date: "2026-04-24", title: "Strategic positioning release", items: [
    { type: "Shipped", text: "Public marketing surface: landing page, pricing, about, changelog." },
    { type: "Shipped", text: "Migration landers for Stocky (Aug 31, 2026) and Genie (Aug 31, 2025)." },
    { type: "Shipped", text: "Transparent pricing with a written price-lock clause in TOS." },
    { type: "Shipped", text: "Forecast explainability: every recommended quantity explains itself." },
    { type: "Changed", text: "Brand renamed from Inventory Command to slelfly." },
    { type: "Added", text: "Alert rules persisted to database — they survive restarts." }
  ]},
  { version: "v0.2.0", date: "2026-04-23", title: "Intelligence surface", items: [
    { type: "Shipped", text: "Holt double-exponential smoothing with weekly seasonality and stockout probability." },
    { type: "Shipped", text: "ABC × XYZ classification and scorecards." },
    { type: "Shipped", text: "Service-level-segmented safety stock, ROP, and EOQ." },
    { type: "Shipped", text: "Supplier scorecards and tiering." },
    { type: "Shipped", text: "Bundle / kit bottleneck analysis." },
    { type: "Shipped", text: "Multi-location transfer recommendations." },
    { type: "Shipped", text: "Dead-stock liquidation plans." },
    { type: "Shipped", text: "Alert rule engine: email, SMS, Slack, webhook." }
  ]},
  { version: "v0.1.0", date: "2026-03-12", title: "Mock-data MVP and action feed", items: [
    { type: "Shipped", text: "Backend action engine with urgent / optimize / dead outputs." },
    { type: "Shipped", text: "Lead-time hierarchy with safety buffer." },
    { type: "Shipped", text: "Frontend homepage connected to live /actions." }
  ]}
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
          <Link href="/blog">Blog</Link>
          <Link href="/changelog">Changelog</Link>
        </nav>
      </header>

      <section className="marketing-hero">
        <p className="marketing-eyebrow">Changelog</p>
        <h1 className="marketing-hero-title">Every release, on the record.</h1>
        <p className="marketing-hero-sub">
          We ship transparently so you never have to wonder whether slelfly is still being built.
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
              <time className="changelog-entry-date" dateTime={entry.date}>{entry.date}</time>
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

      <footer className="marketing-footer">
        <div className="marketing-footer-brand">
          <span className="marketing-brand-mark">sf</span>
          <span>slelfly</span>
        </div>
        <div className="marketing-footer-links">
          <Link href="/">Home</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/about">About</Link>
          <Link href="/blog">Blog</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">© {new Date().getFullYear()} slelfly</p>
      </footer>
    </div>
  );
}
