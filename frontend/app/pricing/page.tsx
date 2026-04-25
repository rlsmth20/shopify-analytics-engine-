import Link from "next/link";

export const metadata = {
  title: "Pricing — slelfly",
  description:
    "Three published tiers. No quote-only pricing. A written price-lock clause that renewals cannot raise the rate on your plan."
};

const tiers = [
  {
    name: "Starter",
    price: "$49",
    cadence: "/mo",
    pitch: "For solo operators and Stocky migrants picking their first replacement.",
    limit: "Up to 500 active SKUs · 1 location · 1 seat",
    features: [
      "Ranked action feed (urgent / optimize / dead)",
      "Holt + seasonality forecasting",
      "ABC × XYZ classification",
      "Supplier records (scoring on higher tiers)",
      "Email + Slack alerts",
      "Shopify-native ingestion",
      "Self-serve setup"
    ],
    cta: "Start free",
    href: "/dashboard",
    featured: false
  },
  {
    name: "Growth",
    price: "$149",
    cadence: "/mo",
    pitch:
      "Most merchants land here. Full intelligence stack, multi-location, no seat gates.",
    limit: "Up to 5,000 active SKUs · 3 locations · unlimited seats",
    features: [
      "Everything in Starter",
      "Supplier scorecards + tiering",
      "Safety-stock / ROP / EOQ with service-level segmentation",
      "Bundle / kit bottleneck analysis",
      "Multi-location transfer recommendations",
      "Dead-stock liquidation plans",
      "SMS + webhook alerts",
      "Scheduled PDF reports"
    ],
    cta: "Start free",
    href: "/dashboard",
    featured: true
  },
  {
    name: "Scale",
    price: "$349",
    cadence: "/mo",
    pitch: "For multi-store operators and teams that want audit + approval flows.",
    limit: "Up to 25,000 active SKUs · 10 locations · unlimited seats",
    features: [
      "Everything in Growth",
      "PO approval + send flow",
      "Audit log and decision snapshots",
      "Workspace roles",
      "Priority support (same-business-day response)",
      "Onboarding concierge",
      "SSO (Google, Microsoft)"
    ],
    cta: "Start free",
    href: "/dashboard",
    featured: false
  }
];

const faqs = [
  {
    q: "Do you raise prices at renewal?",
    a: "No. Every plan has a written price-lock clause in the terms of service: we will not raise the monthly or annual rate on a plan you are already subscribed to for as long as you maintain the subscription. If we change our prices for new customers, existing customers stay on their current rate."
  },
  {
    q: "What happens if I exceed my SKU or location limit?",
    a: "We notify you by email, the app shows a soft banner, and you get thirty days to decide whether to upgrade or prune. We will never silently auto-upgrade your plan or start charging you more without your consent."
  },
  {
    q: "Is there a free tier?",
    a: "Every plan starts with a 14-day free trial, no credit card required. After the trial the Starter plan is $49/mo. We do not operate an ad-supported or 'free forever' tier because we do not want our incentives to live on your data."
  },
  {
    q: "How long does setup take?",
    a: "Most merchants see their first ranked action in under ten minutes after connecting Shopify. We do not require a paid implementation partner and we do not charge for onboarding — that is in stark contrast to several of the competitors we benchmark against."
  },
  {
    q: "Can I pay annually?",
    a: "Yes — pay annually and save 15%. Annual customers also get a contractual price lock on the annual rate."
  },
  {
    q: "How do you compare to Stocky / Inventory Planner / Cin7?",
    a: "Compared with Stocky we add real forecasting, supplier scorecards, and dead-stock plans. Compared with Inventory Planner we publish our price and commit to not raising it. Compared with Cin7 we publish our price and do not require a 6-month implementation. See the migration pages linked from the home page for detail."
  }
];

export default function PricingPage() {
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
        <p className="marketing-eyebrow">Pricing</p>
        <h1 className="marketing-hero-title">Three tiers. Published. Locked.</h1>
        <p className="marketing-hero-sub">
          We publish our prices on this page because the rest of the market
          hides them behind a sales call — and raises them at renewal. We
          commit in writing that renewals do not raise the rate on your plan.
        </p>
      </section>

      <section className="pricing-grid">
        {tiers.map((tier) => (
          <article
            key={tier.name}
            className={`pricing-card${tier.featured ? " pricing-card-featured" : ""}`}
          >
            {tier.featured ? (
              <p className="pricing-card-ribbon">Most merchants pick this</p>
            ) : null}
            <h2 className="pricing-card-name">{tier.name}</h2>
            <p className="pricing-card-pitch">{tier.pitch}</p>
            <p className="pricing-card-price">
              <span className="pricing-card-amount">{tier.price}</span>
              <span className="pricing-card-cadence">{tier.cadence}</span>
            </p>
            <p className="pricing-card-limit">{tier.limit}</p>
            <ul className="pricing-card-features">
              {tier.features.map((f) => (
                <li key={f}>
                  <span className="pricing-feature-tick" aria-hidden>
                    ✓
                  </span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
            <Link
              href={tier.href}
              className={`button ${tier.featured ? "button-primary" : "button-ghost"} button-full`}
            >
              {tier.cta}
            </Link>
          </article>
        ))}
      </section>

      <section className="pricing-lock">
        <div className="pricing-lock-card">
          <p className="pricing-lock-kicker">The slelfly price-lock pledge</p>
          <h2 className="pricing-lock-title">
            Your rate will not go up at renewal. Not this year, not next.
          </h2>
          <p className="pricing-lock-body">
            We built this product because the inventory market is full of
            tools whose prices triple at renewal after an acquisition.
            Inventory Planner users reported roughly a 3× price hike after the
            Sage acquisition. Linnworks users reported a 681% hike after a PE
            rollup. We are not doing that to you.
          </p>
          <p className="pricing-lock-body">
            The specific commitment, which also appears in our terms of
            service, is this: once you start a subscription at a published
            price, that price does not increase for as long as you maintain
            the subscription. If we raise prices for new customers, you stay
            on your grandfathered rate indefinitely.
          </p>
          <p className="pricing-lock-body pricing-lock-fineprint">
            (We reserve the right to pass through Shopify, Stripe, or tax
            changes beyond our control. Everything else: locked.)
          </p>
        </div>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">FAQ</p>
        <h2 className="marketing-section-title">
          The questions we hear the most.
        </h2>
        <div className="faq-grid">
          {faqs.map((f) => (
            <article key={f.q} className="faq-card">
              <h3 className="faq-card-q">{f.q}</h3>
              <p className="faq-card-a">{f.a}</p>
            </article>
          ))}
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
