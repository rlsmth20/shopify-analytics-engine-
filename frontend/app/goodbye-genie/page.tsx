import Link from "next/link";

import { WaitlistForm } from "@/components/waitlist-form";

export const metadata = {
  title: "Goodbye Genie, hello slelfly — slelfly",
  description: "Genie closed August 31, 2025. slelfly kept the simple Shopify-native experience and added the math.",
  alternates: { canonical: "/goodbye-genie" },
  keywords: ["Genie alternative", "Genie replacement", "Genie shutdown"],
  openGraph: { title: "Goodbye Genie, hello slelfly", description: "Genie closed Aug 31, 2025. slelfly is the upgrade.", url: "/goodbye-genie", type: "website" },
};

const reasons = [
  { title: "Shopify-native simplicity, kept.", body: "Genie's appeal was that it felt like a Shopify app, not an ERP bolt-on. slelfly is built the same way." },
  { title: "The math, added.", body: "Genie merchants told reviewers the forecasting felt basic. slelfly ships Holt double-exponential smoothing with weekly seasonality." },
  { title: "Suppliers, measured.", body: "Genie treated vendors as contacts. slelfly scores them: on-time delivery, fill rate, lead-time stability, tiering." },
  { title: "Dead stock, acted on.", body: "Genie surfaced aged stock. slelfly proposes a plan: markdown, bundle, wholesale, or write-off." }
];

const steps = [
  { number: "1", title: "Get on the early-access list", body: "Drop your email. We'll send your invite when we open up." },
  { number: "2", title: "Bring your Genie CSV", body: "If you exported your Genie data before the sunset, our importer maps vendors and lead-time settings." },
  { number: "3", title: "See your first ranked action", body: "Under ten minutes, no consultant. The dashboard prioritizes urgent reorders." }
];

export default function GoodbyeGeniePage() {
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

      <section className="marketing-hero marketing-hero-migration">
        <p className="marketing-eyebrow">Genie closed August 31, 2025</p>
        <h1 className="marketing-hero-title">Genie is gone. slelfly is the upgrade.</h1>
        <p className="marketing-hero-sub">
          Genie merchants loved simple. We kept the simple — and added the math, the supplier scorecards, and the dead-stock plans Genie never shipped.
        </p>
        <WaitlistForm source="goodbye_genie_hero" ctaLabel="Get early access" />
        <p className="marketing-hero-trust">
          Free 30-day trial · No credit card · <strong>Prices locked at renewal</strong>
        </p>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">What changes for you</p>
        <h2 className="marketing-section-title">Everything you liked, and four things Genie didn&apos;t do.</h2>
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
        <p className="marketing-section-sub">The CSV exports and spreadsheets were good under pressure. slelfly is the permanent replacement.</p>
        <WaitlistForm source="goodbye_genie_footer" ctaLabel="Get early access" />
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
          <Link href="/goodbye-stocky">Stocky migration</Link>
          <Link href="/goodbye-genie">Genie migration</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">© {new Date().getFullYear()} slelfly · Prices locked at renewal</p>
      </footer>
    </div>
  );
}
