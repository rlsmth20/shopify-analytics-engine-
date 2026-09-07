import Link from "next/link";
import { MarketingNav } from "@/components/marketing-nav";
import { MarketingFooter } from "@/components/marketing-footer";

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
          <time dateTime="2026-09-06">Last updated: September 6, 2026</time>
        </p>
        <h1 className="blog-article-title">Privacy Policy</h1>
        <p className="blog-article-lead">
          skubase (&ldquo;skubase,&rdquo; &ldquo;we,&rdquo; &ldquo;our&rdquo;) is operated as an independent,
          founder-led company. This policy describes what we collect, why we
          collect it, who we share it with, and your rights.
        </p>

        <h2 className="blog-article-h2">What we collect</h2>
        <p>
          When you start a free trial or create an account we collect:
          your email address and the source page you
          signed up from. When you connect a Shopify store we collect: product
          catalog, inventory levels, vendor names, and order line-item history
          necessary to compute reorder recommendations. When you upload a
          ShipStation or Stocky CSV, we ingest only the rows in that file.
        </p>
        <p>
          Shopify order imports retain order and line-item identifiers, product
          references, quantities, prices, and order dates. They do not request
          customer names, customer email addresses, phone numbers, or delivery
          addresses. We also store your app account and Shopify connection details
          to authenticate access to your workspace.
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
          <li><strong>Shopify</strong> — store data, embedded authentication, and billing for Shopify app subscriptions.</li>
          <li><strong>Resend</strong> — sign-in, support, and configured notification email delivery.</li>
          <li><strong>OpenAI</strong> — when AI responses are enabled, Ask Skubase sends your question, recent conversation, store domain, and relevant inventory metrics to generate an answer. Shopify customer profiles are not included in this context.</li>
          <li><strong>Stripe</strong> — servicing legacy subscriptions created before Shopify billing was adopted; new app subscriptions use Shopify billing.</li>
        </ul>

        <h2 className="blog-article-h2">Retention and deletion</h2>
        <p>
          You can delete your account and associated data at any time by
          emailing <a href="mailto:info@skubase.io">info@skubase.io</a>.
          We will purge your data from production within 30 days. Aggregated, anonymized
          metrics may be retained for service operation.
        </p>
        <p>
          Shopify privacy requests are processed for the store that issued them.
          Customer redaction removes matching retained order records; shop redaction
          removes the uninstalled workspace and its associated production records.
          Customer access requests are available to the merchant under Privacy Requests
          in the app. Uninstalling revokes access immediately; Shopify sends the shop
          redaction request separately. Delayed requests for an earlier installation
          do not erase a subsequently reinstalled workspace.
        </p>

        <h2 className="blog-article-h2">Your rights</h2>
        <p>
          You have the right to access, correct, export, and delete your
          personal data. Contact{" "}
          <a href="mailto:info@skubase.io">info@skubase.io</a> for any
          such request. EU residents have rights under GDPR; California
          residents have rights under CCPA; we honor both equivalently for
          all users.
        </p>

        <h2 className="blog-article-h2">Cookies and storage</h2>
        <p>
          Embedded Shopify access uses short-lived Shopify session tokens
          and does not require third-party cookies. Browser storage can remember
          interface preferences; standalone website sign-in uses a session cookie.
          To understand where merchants find Skubase and where onboarding needs
          improvement, first-party storage retains a random visitor identifier,
          landing-page path and campaign attribution for up to 30 days. These
          events can be linked to your store after sign-in. This measurement is
          skipped when your browser sends Do Not Track. We do not store URL
          query strings or use third-party advertising cookies for this measurement.
        </p>

        <h2 className="blog-article-h2">Security</h2>
        <p>
          Data in transit is encrypted via TLS. Shopify connection tokens are kept
          on the backend and are not sent to the browser. Access to store records
          is scoped to the authenticated workspace. Contact us for further details
          about hosting safeguards and data retention.
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
          Questions about this policy: <a href="mailto:info@skubase.io">info@skubase.io</a>.
        </p>
      </article>

      <MarketingFooter />
    </div>
  );
}

