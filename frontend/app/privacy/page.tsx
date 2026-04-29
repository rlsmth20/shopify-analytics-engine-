import Link from "next/link";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "Privacy Policy — skubase",
  description: "How skubase collects, uses, and protects your data.",
  alternates: { canonical: "/privacy" },
  openGraph: {
    title: "Privacy Policy — skubase",
    description: "How skubase collects, uses, and protects your data.",
    url: "/privacy",
    type: "website",
  },
};

export default function PrivacyPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <article className="blog-article">
        <p className="blog-article-meta">
          <time dateTime="2026-04-25">Last updated: April 25, 2026</time>
        </p>
        <h1 className="blog-article-title">Privacy Policy</h1>
        <p className="blog-article-lead">
          skubase (&ldquo;skubase,&rdquo; &ldquo;we,&rdquo; &ldquo;our&rdquo;) is operated as an independent,
          founder-led company. This policy describes what we collect, why we
          collect it, who we share it with, and your rights.
        </p>

        <h2 className="blog-article-h2">What we collect</h2>
        <p>
          When you sign up for the waitlist or create an account we collect:
          your email address, optional Shopify domain, and the source page you
          signed up from. When you connect a Shopify store we collect: product
          catalog, inventory levels, vendor records, and order history
          necessary to compute reorder recommendations. When you upload a
          ShipStation or Stocky CSV, we ingest only the rows in that file.
        </p>
        <p>
          Server logs include standard request metadata (IP, user agent,
          path, status code) for the purpose of operating the service.
          Vercel Analytics and Vercel Speed Insights are deployed in
          privacy-preserving (cookieless, no personal identifiers) modes.
        </p>

        <h2 className="blog-article-h2">How we use it</h2>
        <p>
          We use your data only to operate the service: rank reorder
          actions, score suppliers, surface dead-stock plans, deliver
          alerts you configure, and respond to support requests. We do not
          sell your data. We do not train AI models on your store data. We
          do not share your data with advertisers.
        </p>

        <h2 className="blog-article-h2">Sub-processors</h2>
        <p>
          We rely on the following sub-processors to operate the service.
          Each receives only the minimum data necessary for its function:
        </p>
        <ul className="blog-article-ul">
          <li><strong>Vercel</strong> — frontend hosting, analytics, speed insights.</li>
          <li><strong>Railway</strong> — backend hosting and managed PostgreSQL.</li>
          <li><strong>Shopify</strong> — source of catalog, inventory, and order data when you connect a store.</li>
          <li><strong>Resend</strong> — transactional email delivery (planned).</li>
          <li><strong>Stripe</strong> — payment processing (when paid plans launch).</li>
        </ul>

        <h2 className="blog-article-h2">Retention and deletion</h2>
        <p>
          You can delete your account and associated data at any time by
          emailing <a href="mailto:hello@skubase.io">hello@skubase.io</a>.
          We will purge your data from production within 30 days. Backups
          are encrypted and rotated within 90 days. Aggregated, anonymized
          metrics may be retained for service operation.
        </p>

        <h2 className="blog-article-h2">Your rights</h2>
        <p>
          You have the right to access, correct, export, and delete your
          personal data. Contact{" "}
          <a href="mailto:privacy@skubase.io">privacy@skubase.io</a> for any
          such request. EU residents have rights under GDPR; California
          residents have rights under CCPA; we honor both equivalently for
          all users.
        </p>

        <h2 className="blog-article-h2">Cookies and storage</h2>
        <p>
          We use the minimum browser storage required to operate the
          service: a small amount of localStorage to remember your shop
          domain on the dashboard, and standard session cookies once
          authentication is in place. We do not use third-party advertising
          cookies.
        </p>

        <h2 className="blog-article-h2">Security</h2>
        <p>
          Data in transit is encrypted via TLS. Database snapshots are
          encrypted at rest. Shopify access tokens are stored encrypted.
          Internal access is limited to a small founder team and logged.
        </p>

        <h2 className="blog-article-h2">Changes</h2>
        <p>
          If this policy changes materially, we&apos;ll notify all
          registered users by email at least 30 days before the change
          takes effect. Minor clarifications and typo fixes will be reflected
          here without notification.
        </p>

        <h2 className="blog-article-h2">Contact</h2>
        <p>
          Questions about this policy: <a href="mailto:privacy@skubase.io">privacy@skubase.io</a>.
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
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">© {new Date().getFullYear()} skubase</p>
      </footer>
    </div>
  );
}

