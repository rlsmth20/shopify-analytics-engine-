import Link from "next/link";
import { MarketingNav } from "@/components/marketing-nav";
import { MarketingFooter } from "@/components/marketing-footer";

import { BLOG_POSTS } from "@/lib/blog-posts";
import { BlogArticleMeta } from "@/components/blog-article-meta";

const post = BLOG_POSTS["shopify-safety-stock-formula"];

export const metadata = {
  title: `${post.title} - skubase`,
  description: post.description,
  alternates: { canonical: "/blog/shopify-safety-stock-formula" },
  keywords: ["safety stock formula Shopify", "Shopify safety stock", "how to calculate safety stock", "reorder point Shopify"],
  openGraph: {
    title: post.title,
    description: post.description,
    url: "/blog/shopify-safety-stock-formula",
    type: "article",
  },
};

const ARTICLE_LD = {
  "@context": "https://schema.org",
  "@type": "Article",
  headline: post.title,
  datePublished: post.publishedAt,
  dateModified: post.updatedAt,
  author: { "@type": "Organization", name: "skubase" },
};

export default function SafetyStockFormulaPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <article className="blog-article">
        <BlogArticleMeta post={post} />
        <h1 className="blog-article-title">{post.title}</h1>
        <p><Link href="/tools/reorder-point-calculator">Try the free reorder-point calculator</Link> to see how daily demand, lead time and safety stock change your ordering trigger.</p>
        <p className="blog-article-lead">
          A fixed buffer is a useful starting point. To refine it, look at how much demand varies and how reliably
          suppliers deliver. This guide shows a statistical planning example and the practical data to collect
          before changing your reorder settings.
        </p>

        <h2 className="blog-article-h2">What safety stock is actually for</h2>
        <p>
          Safety stock is the inventory you hold to absorb uncertainty. There are two sources of
          uncertainty in any replenishment cycle:
        </p>
        <ol className="blog-article-ol">
          <li><strong>Demand uncertainty</strong> - sales in the lead-time window are higher than expected.</li>
          <li><strong>Supply uncertainty</strong> - your supplier ships late, short, or both.</li>
        </ol>
        <p>
          A fixed buffer day rule handles neither systematically. A SKU that sells 10 units/day with
          a standard deviation of 1 unit needs far less safety stock than one that sells 10/day with a standard deviation of 8 units, even
          though they have the same average.
        </p>

        <h2 className="blog-article-h2">The formula</h2>
        <p>
          With independent daily demand and lead times, a normal approximation gives this planning estimate:
        </p>
        <p className="blog-article-formula">
          Safety Stock = Z × √(LT × σ_d² + D² × σ_lt²)
        </p>
        <p>Where:</p>
        <ul className="blog-article-ul">
          <li><strong>Z</strong> - service-level Z-score. For a target 95% cycle service level, Z = 1.645. For 98%, Z = 2.054. For 99%, Z = 2.326.</li>
          <li><strong>LT</strong> - average lead time in days (time from PO to warehouse receipt).</li>
          <li><strong>σ_d</strong> - standard deviation of daily demand over the measurement window.</li>
          <li><strong>D</strong> - average daily demand.</li>
          <li><strong>σ_lt</strong> - standard deviation of lead time (how much your supplier&apos;s delivery timing varies).</li>
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
          ≈ 103.2 units; round up to 104 units
        </p>
        <p>
          A 30-day buffer at 12 units/day is 360 units. The illustrative 104-unit estimate is about 71% lower.
          It targets a 95% chance of avoiding a stockout during a replenishment cycle under these assumptions;
          compare actual delivery and stockout results before changing the buffer.
        </p>

        <h2 className="blog-article-h2">The reorder point</h2>
        <p>
          Add expected lead-time demand to your safety stock to calculate the reorder point (ROP):
        </p>
        <p className="blog-article-formula">
          ROP = (Average Daily Demand × Average Lead Time) + Safety Stock
        </p>
        <p>
          In this example: ROP = (12 × 21) + 104 = 356 units. Review replenishment when inventory position
          (on hand plus on order minus backorders) reaches this level. Account for open orders before adding another PO.
        </p>

        <h2 className="blog-article-h2">Service level segmentation</h2>
        <p>
          Not every SKU deserves a 98% service level. The Z-score is not free - higher service levels
          require more safety stock. An illustrative starting point to test:
        </p>
        <ul className="blog-article-ul">
          <li><strong>A-tier SKUs</strong> (largest cumulative revenue contribution) → 98–99% service level</li>
          <li><strong>B-tier SKUs</strong> (middle contribution) → 95% service level</li>
          <li><strong>C-tier SKUs</strong> (remaining contribution) → 90% service level</li>
        </ul>
        <p>
          Choose service targets using revenue contribution, margin, substitutability, and the cost of a stockout.
          A low-revenue spare part may still be essential to a customer, so ABC class is a starting point for review.
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
          Useful lead-time data lives in your PO history: date PO sent, date goods received. The gap between those
          two dates, across all POs for a vendor, gives you average lead time and standard deviation.
        </p>
        <p>
          Use any saved Stocky records or spreadsheet order dates you already have, then record subsequent receipts
          consistently. Keep the sample count visible: a supplier with two deliveries offers less evidence than
          one with dozens of comparable shipments.
        </p>

        <h2 className="blog-article-h2">How skubase handles this</h2>
        <p>
          Skubase uses demand variability, configured supplier lead times, and safety-buffer settings to help
          prioritize reorder decisions. Recorded PO receipts support supplier scorecards and lead-time review.
          The example above includes variable lead time; Skubase&apos;s current reorder calculation uses a configured
          lead time, so review that setting when your supplier&apos;s delivery pattern changes.
        </p>

        <div className="blog-article-cta">
          <Link href="/dashboard?demo=1" className="button button-primary button-lg">See the demo</Link>
          <Link href="/forecast?demo=1" className="button button-ghost button-lg">See forecast view</Link>
        </div>
      </article>

      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ARTICLE_LD) }} />

      <MarketingFooter />
    </div>
  );
}
