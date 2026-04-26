import Link from "next/link";

export const metadata = {
  title: "About — slelfly",
  description:
    "Independent, founder-led, Shopify-first. No PE squeeze. No acquisition surprises. No quote-only pricing.",
  alternates: { canonical: "/about" },
  openGraph: {
    title: "About slelfly — Independent. Founder-led. No PE squeeze.",
    description:
      "Eight of the inventory tools you evaluate were acquired and got worse. slelfly is structurally outside that pattern.",
    url: "/about",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "About slelfly — Independent. Founder-led. No PE squeeze.",
    description:
      "Eight of the inventory tools you evaluate were acquired and got worse. slelfly is built to stay independent.",
  },
};

const beliefs = [
  {
    title: "Inventory is a decision problem, not a reporting problem.",
    body:
      "Most inventory tools are dashboards — they tell you what happened and leave you to act. slelfly ranks the decisions: what to reorder, what is overstocked, what is dead, what to do first."
  },
  {
    title: "Math should be visible.",
    body:
      "Every recommended quantity explains itself. Trailing demand, seasonality factor, service level, stockout probability — all on the card, all clickable. If we cannot explain it, we will not recommend it."
  },
  {
    title: "Suppliers are measurable.",
    body:
      "23 of 25 tools we studied treat vendors as contact records. We treat them as performers. On-time delivery, fill rate, lead-time stability, tiering. Facts, not feelings."
  },
  {
    title: "Dead stock is a cash recovery problem.",
    body:
      "24 of 25 tools flag aged inventory and stop. We propose the specific plan — markdown, bundle, wholesale, or write-off — with the dollar impact attached."
  },
  {
    title: "Pricing should be published and locked.",
    body:
      "7 of 25 tools are quote-only. 6 of 25 have public complaints about renewal-time price hikes. We publish our prices and commit in writing not to raise them at renewal."
  }
];

const notLikeUs = [
  {
    competitor: "Inventory Planner",
    owner: "Sage (2021)",
    pattern: "Users reported ~3× price hikes and support regression after the acquisition."
  },
  {
    competitor: "Linnworks",
    owner: "Marlin Equity (PE)",
    pattern: "Trustpilot reviews cite a 681% renewal price hike and support collapse."
  },
  {
    competitor: "Veeqo",
    owner: "Amazon (2021)",
    pattern: "Non-Amazon merchants raised data concerns; roadmap visibly slowed."
  },
  {
    competitor: "Skubana",
    owner: "Extensiv",
    pattern: "Forced platform migration created documented churn and billing confusion."
  },
  {
    competitor: "Cin7 Core (DEAR)",
    owner: "Cin7",
    pattern: "Post-rebrand price restructuring moved legacy DEAR contracts up tiers."
  },
  {
    competitor: "Sellbrite",
    owner: "GoDaddy (2019)",
    pattern: "Users describe the roadmap as frozen for two-plus years."
  },
  {
    competitor: "Brightpearl",
    owner: "Sage (2022)",
    pattern: "Quote-only pricing, 6-month implementations, post-acquisition support slips."
  },
  {
    competitor: "SKUVault",
    owner: "Linnworks (2022)",
    pattern: "Same PE owner as Linnworks; buyers now wary."
  }
];

export default function AboutPage() {
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
        <p className="marketing-eyebrow">About slelfly</p>
        <h1 className="marketing-hero-title">
          Independent. Founder-led. Shopify-first.
        </h1>
        <p className="marketing-hero-sub">
          Eight of the 25 inventory tools we benchmark against have been
          acquired by a parent that raised prices, slowed the roadmap, or
          broke support. slelfly is structurally outside that pattern — and
          we plan to stay that way.
        </p>
      </section>

      <section className="about-pledge">
        <div className="about-pledge-card">
          <p className="about-pledge-kicker">Our commitments to you</p>
          <ul className="about-pledge-list">
            <li>
              <strong>No PE squeeze.</strong> We are founder-owned and not
              raising venture capital on terms that force renewal hikes. When
              our incentives and yours diverge, we will tell you.
            </li>
            <li>
              <strong>No surprise price changes.</strong> Your rate at sign-up
              is your rate for as long as you stay subscribed. That is in the
              terms of service, not just on this page.
            </li>
            <li>
              <strong>No quote-only pricing.</strong> Every tier is published
              on the pricing page. Enterprise customers get the same numbers
              as everyone else.
            </li>
            <li>
              <strong>No consultant-required onboarding.</strong> Most
              merchants see their first ranked action in under ten minutes.
              We will never require a paid implementation partner.
            </li>
            <li>
              <strong>A public changelog.</strong> Five of the acquired tools
              in our study have a roadmap that has visibly slowed. We ship
              transparently. Every release lands on the changelog page.
            </li>
          </ul>
        </div>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">What we believe</p>
        <h2 className="marketing-section-title">
          Five ideas that shape the product.
        </h2>
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
        <h2 className="marketing-section-title">
          The tools you evaluated and what happened to them.
        </h2>
        <p className="marketing-section-sub">
          We do not enjoy writing this section. These are documented patterns
          from public reviews; we cite them because the pattern is real and
          because our independence is a concrete difference, not a slogan.
        </p>
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
        <h2 className="marketing-section-title">
          See slelfly on your catalog.
        </h2>
        <p className="marketing-section-sub">
          Open the app, connect your Shopify store, and the first ranked
          action appears in under ten minutes.
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
