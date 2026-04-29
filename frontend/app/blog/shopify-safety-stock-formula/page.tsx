import Link from "next/link";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "The right safety stock formula for Shopify merchants — skubase",
  description: "Most Shopify merchants use a fixed buffer day rule. Here is the formula that actually accounts for demand variance and supplier lead-time variation — and how to apply it.",
  alternates: { canonical: "/blog/shopify-safety-stock-formula" },
  keywords: ["safety stock formula Shopify", "Shopify safety stock", "how to calculate safety stock", "reorder point Shopify"],
  openGraph: {
    title: "The right safety stock formula for Shopify merchants",
    description: "Fixed buffer days leave you either overstocked or stocked out. Here is the formula that actually works.",
    url: "/blog/shopify-safety-stock-formula",
    type: "article",
  },
};

const ARTICLE_LD = {
  "@context": "https://schema.org",
  "@type": "Article",
  headline: "The right safety stock formula for Shopify merchants",
  datePublished: "2026-04-29",
  author: { "@type": "Organization", name: "skubase" },
};

export default function SafetyStockFormulaPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <article className="blog-article">
        <p className="blog-article-meta">
          <time dateTime="2026-04-29">April 29, 2026</time> · 10 min read · Forecasting
        </p>
        <h1 className="blog-article-title">The right safety stock formula for Shopify merchants</h1>
        <p className="blog-article-lead">
          Most Shopify merchants set a fixed buffer — 30 days of cover on every SKU, or a flat minimum
          quantity — and call it safety stock. It works until it doesn&apos;t: a fast mover stockouts two
          weeks before a holiday; a slow mover sits for eight months. The problem is that a fixed buffer
          ignores the two things that actually drive stockout risk: how much demand varies and how
          reliably your supplier delivers.
        </p>

        <h2 className="blog-article-h2">What safety stock is actually for</h2>
        <p>
          Safety stock is the inventory you hold to absorb uncertainty. There are two sources of
          uncertainty in any replenishment cycle:
        </p>
        <ol className="blog-article-ol">
          <li><strong>Demand uncertainty</strong> — sales in the lead-time window are higher than expected.</li>
          <li><strong>Supply uncertainty</strong> — your supplier ships late, short, or both.</li>
        </ol>
        <p>
          A fixed buffer day rule handles neither systematically. A SKU that sells 10 units/day with
          ±1 variance needs far less safety stock than one that sells 10/day with ±8 variance, even
          though they have the same average.
        </p>

        <h2 className="blog-article-h2">The formula</h2>
        <p>
          The standard safety stock formula that accounts for both sources of uncertainty is:
        </p>
        <p className="blog-article-formula">
          Safety Stock = Z × √(LT × σ_d² + D² × σ_lt²)
        </p>
        <p>Where:</p>
        <ul className="blog-article-ul">
          <li><strong>Z</strong> — service-level Z-score. For 95% service level, Z = 1.645. For 98%, Z = 2.054. For 99%, Z = 2.326.</li>
          <li><strong>LT</strong> — average lead time in days (time from PO to warehouse receipt).</li>
          <li><strong>σ_d</strong> — standard deviation of daily demand over the measurement window.</li>
          <li><strong>D</strong> — average daily demand.</li>
          <li><strong>σ_lt</strong> — standard deviation of lead time (how much your supplier&apos;s delivery timing varies).</li>
        </ul>

        <h2 className="blog-article-h2">A worked example</h2>
        <p>
          Suppose you have a SKU with:
        </p>
        <ul className="blog-article-ul">
          <li>Average daily demand: 12 units/day</li>
          <li>Demand standard deviation: 4 units/day</li>
          <li>Average lead time: 21 days</li>
          <li>Lead-time standard deviation: 5 days</li>
          <li>Target service level: 95% (Z = 1.645)</li>
        </ul>
        <p>
          Plugging in:
        </p>
        <p className="blog-article-formula">
          Safety Stock = 1.645 × √(21 × 4² + 12² × 5²)<br />
          = 1.645 × √(21 × 16 + 144 × 25)<br />
          = 1.645 × √(336 + 3,600)<br />
          = 1.645 × √3,936<br />
          = 1.645 × 62.7<br />
          ≈ 103 units
        </p>
        <p>
          With a flat 30-day buffer, you&apos;d hold 360 units (30 × 12). The formula gets you to 103 — a
          65% reduction in safety stock while maintaining a 95% service level. That&apos;s cash you&apos;re
          currently tying up unnecessarily.
        </p>

        <h2 className="blog-article-h2">The reorder point</h2>
        <p>
          Safety stock is not your reorder point — it&apos;s the floor. The full reorder point (ROP) is:
        </p>
        <p className="blog-article-formula">
          ROP = (Average Daily Demand × Average Lead Time) + Safety Stock
        </p>
        <p>
          In the example above: ROP = (12 × 21) + 103 = 252 + 103 = 355 units. When on-hand drops
          to 355, place the PO.
        </p>

        <h2 className="blog-article-h2">Service level segmentation</h2>
        <p>
          Not every SKU deserves a 98% service level. The Z-score is not free — higher service levels
          mean exponentially more safety stock. A rational approach:
        </p>
        <ul className="blog-article-ul">
          <li><strong>A-tier SKUs</strong> (top 20% of revenue) → 98–99% service level</li>
          <li><strong>B-tier SKUs</strong> (next 30%) → 95% service level</li>
          <li><strong>C-tier SKUs</strong> (bottom 50%) → 90% service level</li>
        </ul>
        <p>
          ABC segmentation lets you hold less total inventory while protecting the revenue-generating items.
          Most Shopify merchants apply one buffer to every SKU — a C-item held at 98% service is cash
          you don&apos;t need to lock up.
        </p>

        <h2 className="blog-article-h2">Where merchants get this wrong</h2>
        <p>
          Three common mistakes:
        </p>
        <ol className="blog-article-ol">
          <li>
            <strong>Using average lead time only, ignoring variance.</strong> If your supplier is on time
            90% of the time but arrives 2 weeks late 10% of the time, the average masks the real risk.
            The standard deviation of lead time is the number that matters.
          </li>
          <li>
            <strong>Measuring demand variance over too short a window.</strong> A 30-day demand window
            during a slow period dramatically underestimates the variance you&apos;ll see during a
            sale or seasonal ramp. Use 52 weeks of history where possible.
          </li>
          <li>
            <strong>Never recalculating.</strong> A SKU&apos;s demand variance changes over time. A product
            that was predictable for two years can become volatile after a single viral moment or a
            competitor stockout. Recalculate safety stock monthly for A-tier SKUs.
          </li>
        </ol>

        <h2 className="blog-article-h2">Getting supplier lead-time variance</h2>
        <p>
          Most Shopify merchants don&apos;t track lead-time variance because no tool surfaces it automatically.
          The data lives in your PO history: date PO sent, date goods received. The gap between those
          two dates, across all POs for a vendor, gives you average lead time and standard deviation.
        </p>
        <p>
          If you&apos;ve been using Stocky or a spreadsheet, you likely don&apos;t have this. Start collecting it.
          Even a 6-month window of PO receipts gives you enough signal to distinguish reliable suppliers
          from unreliable ones.
        </p>

        <h2 className="blog-article-h2">How skubase handles this</h2>
        <p>
          skubase computes safety stock and reorder points using this formula — service-level segmented
          by ABC tier, with lead-time variance pulled from your PO history. The daily action queue shows
          which SKUs are below their ROP, ranked by urgency. You don&apos;t run the formula manually; you
          work the queue.
        </p>

        <div className="blog-article-cta">
          <Link href="/dashboard?demo=1" className="button button-primary button-lg">See the demo</Link>
          <Link href="/forecast?demo=1" className="button button-ghost button-lg">See forecast view</Link>
        </div>
      </article>

      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ARTICLE_LD) }} />

      <footer className="marketing-footer">
        <div className="marketing-footer-brand">
          <span className="marketing-brand-mark">sb</span>
          <span>skubase</span>
        </div>
        <div className="marketing-footer-links">
          <Link href="/">Home</Link>
          <Link href="/blog">Blog</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">© {new Date().getFullYear()} skubase · Independent · Founder-led</p>
      </footer>
    </div>
  );
}
