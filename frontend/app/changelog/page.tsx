import Link from "next/link";

import { WaitlistForm } from "@/components/waitlist-form";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "Changelog — skubase",
  description: "Every release lands here. Shipping transparently is how we counter the ''roadmap frozen'' pattern the rest of the market has earned.",
  alternates: { canonical: "/changelog" },
  openGraph: { title: "Changelog — skubase", description: "Every release, on the record.", url: "/changelog", type: "website" },
};

type ChangelogEntry = { version: string; date: string; title: string; items: { type: "Added" | "Changed" | "Fixed" | "Shipped"; text: string }[]; };

const entries: ChangelogEntry[] = [
  { version: "v0.5.0", date: "2026-04-29", title: "14-day free trial + paywall", items: [
    { type: "Shipped", text: "14-day free trial for all new accounts — no credit card required. trial_ends_at set at signup." },
    { type: "Shipped", text: "Backend access gate: require_active_access() on all 15 protected routes (402 when trial expired or no active subscription)." },
    { type: "Shipped", text: "Frontend paywall: trial countdown banner in app shell (shows at ≤7 days, urgent at ≤2)." },
    { type: "Shipped", text: "api-v2: any 402 redirects to /pricing?trial_expired=1." },
    { type: "Shipped", text: "Pricing page: trial-expired banner shown via ?trial_expired=1 query param." },
    { type: "Shipped", text: "Billing page: trial status card with days remaining and subscribe CTA." },
    { type: "Shipped", text: "Account page: plan card shows trial status and days remaining." },
    { type: "Changed", text: "Waitlist signup replaced by magic-link trial signup across all marketing CTAs." },
    { type: "Changed", text: "Dashboard empty state: 4-step onboarding guide (Stocky CSV, ShipStation, Shopify sync, lead times)." },
    { type: "Changed", text: "goodbye-genie and goodbye-stocky step 1: trial language replaces waitlist language." },
    { type: "Fixed", text: "login page: stale 'waitlist' error copy replaced with trial-era copy." },
  ]},
  { version: "v0.4.0", date: "2026-04-25", title: "Pre-launch readiness", items: [
    { type: "Shipped", text: "Waitlist signup form replaces direct dashboard access — skubase enters private beta." },
    { type: "Shipped", text: "Demo-mode banner on /dashboard so visitors know they''re seeing example data." },
    { type: "Shipped", text: "Privacy Policy and Terms of Service pages, including the written price-lock clause." },
    { type: "Shipped", text: "Public blog at /blog with first two posts (Stocky alternatives, why moving averages overstock)." },
    { type: "Shipped", text: "Stocky and ShipStation CSV importers with sample test data." }
  ]},
  { version: "v0.3.0", date: "2026-04-24", title: "Strategic positioning release", items: [
    { type: "Shipped", text: "Public marketing surface: landing page, pricing, about, changelog." },
    { type: "Shipped", text: "Migration landers for Stocky (Aug 31, 2026) and Genie (Aug 31, 2025)." },
    { type: "Shipped", text: "Transparent pricing with a written price-lock clause in TOS." },
    { type: "Shipped", text: "Forecast explainability: every recommended quantity explains itself." },
    { type: "Changed", text: "Brand renamed from Inventory Command to skubase." },
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
      <MarketingNav />

      <section className="marketing-hero">
        <p className="marketing-eyebrow">Changelog</p>
        <h1 className="marketing-hero-title">Every release, on the record.</h1>
        <p className="marketing-hero-sub">
          We ship transparently so you never have to wonder whether skubase is still being built.
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

      <section className="marketing-section marketing-cta-section">
        <h2 className="marketing-section-title">Shipping a public changelog because we plan to keep doing it.</h2>
        <p className="marketing-section-sub">
          14-day free trial, no credit card. The demo is live if you want to look first.
        </p>
        <WaitlistForm source="changelog" ctaLabel="Start free trial" />
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
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">© {new Date().getFullYear()} skubase</p>
      </footer>
    </div>
  );
}

