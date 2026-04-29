import Link from "next/link";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "Terms of Service — skubase",
  description: "The agreement that governs your use of skubase. Includes the price-lock clause.",
  alternates: { canonical: "/terms" },
  openGraph: {
    title: "Terms of Service — skubase",
    description: "The agreement that governs your use of skubase. Includes the price-lock clause.",
    url: "/terms",
    type: "website",
  },
};

export default function TermsPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <article className="blog-article">
        <p className="blog-article-meta">
          <time dateTime="2026-04-25">Last updated: April 25, 2026</time>
        </p>
        <h1 className="blog-article-title">Terms of Service</h1>
        <p className="blog-article-lead">
          These terms govern your use of skubase. By creating an account or
          using the service you agree to them.
        </p>

        <h2 className="blog-article-h2">1. The service</h2>
        <p>
          skubase provides Shopify inventory forecasting, supplier scoring,
          dead-stock recommendations, and alert delivery. The service is
          provided as-is; we will give reasonable effort to keep it
          available, accurate, and secure.
        </p>

        <h2 className="blog-article-h2">2. Your account and your data</h2>
        <p>
          You are responsible for keeping your credentials secure. The data
          you upload or sync (catalog, inventory, vendors, orders) remains
          yours. We process it solely to operate the service. See our{" "}
          <Link href="/privacy">Privacy Policy</Link> for detail.
        </p>

        <h2 className="blog-article-h2">3. Pricing — the price-lock clause</h2>
        <p>
          <strong>The skubase price-lock pledge:</strong> the monthly or
          annual rate you start a subscription at will not increase for as
          long as you maintain that subscription on the same plan. If we
          raise prices for new customers in the future, you remain
          grandfathered at your original rate. This clause is binding.
        </p>
        <p>
          We reserve the right to pass through changes mandated by Shopify
          (e.g., Shopify Plus surcharges), Stripe (payment processing fees),
          or government taxes — these are external costs that do not
          benefit skubase. All other pricing is locked.
        </p>
        <p>
          Plan limits (active SKUs, locations, seats) are not the price.
          Exceeding a limit prompts an upgrade conversation; we do not
          silently auto-upgrade you.
        </p>

        <h2 className="blog-article-h2">4. Trial and cancellation</h2>
        <p>
          Every plan starts with a 14-day free trial. No credit card is
          required during the trial. You may cancel at any time. On
          cancellation we retain your data for 30 days in case you return,
          then purge it.
        </p>

        <h2 className="blog-article-h2">5. Acceptable use</h2>
        <p>
          You agree not to use the service to violate the law, to abuse our
          infrastructure (scraping at scale, denial-of-service), to
          misrepresent your identity, or to upload data you do not have the
          right to use. We may suspend accounts that do.
        </p>

        <h2 className="blog-article-h2">6. Service availability</h2>
        <p>
          We target 99.5% uptime. Scheduled maintenance is announced in
          advance on the changelog page. We do not guarantee perfect
          availability and our liability for downtime is limited to a credit
          equal to the affected portion of your monthly subscription.
        </p>

        <h2 className="blog-article-h2">7. Forecasts and recommendations</h2>
        <p>
          skubase produces statistical forecasts and recommendations. They
          are tools, not guarantees. You remain responsible for your
          inventory decisions. We are not liable for stockouts, overstock,
          or business decisions made on the basis of skubase&apos;s output.
        </p>

        <h2 className="blog-article-h2">8. Intellectual property</h2>
        <p>
          skubase retains all rights to the service, software, and brand.
          You retain all rights to your data. You grant us a limited license
          to process your data only as necessary to operate the service.
        </p>

        <h2 className="blog-article-h2">9. Termination</h2>
        <p>
          You may terminate your account at any time. We may terminate
          accounts that materially violate these terms, with notice when
          possible.
        </p>

        <h2 className="blog-article-h2">10. Changes to these terms</h2>
        <p>
          If we change these terms materially, we will email all registered
          users at least 30 days in advance. The price-lock clause cannot
          be removed for users who signed up under it.
        </p>

        <h2 className="blog-article-h2">11. Governing law</h2>
        <p>
          These terms are governed by the laws of the State of Delaware,
          USA, without regard to conflict-of-laws principles. Disputes will
          be resolved in the state or federal courts located in Delaware.
        </p>

        <h2 className="blog-article-h2">12. Contact</h2>
        <p>
          Questions: <a href="mailto:hello@skubase.io">hello@skubase.io</a>.
          Legal: <a href="mailto:legal@skubase.io">legal@skubase.io</a>.
        </p>
      </article>

      <footer className="marketing-footer">
        <div className="marketing-footer-brand">
          <span className="marketing-brand-mark">sb</span>
          <span>skubase</span>
        </div>
        <div className="marketing-footer-links">
          <Link href="/">Home</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/about">About</Link>
          <Link href="/