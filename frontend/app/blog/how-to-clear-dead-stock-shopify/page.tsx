import Link from "next/link";
import { MarketingNav } from "@/components/marketing-nav";
import { MarketingFooter } from "@/components/marketing-footer";

import { BLOG_POSTS } from "@/lib/blog-posts";
import { BlogArticleMeta } from "@/components/blog-article-meta";

const post = BLOG_POSTS["how-to-clear-dead-stock-shopify"];

export const metadata = {
  title: `${post.title} - skubase`,
  description: post.description,
  alternates: { canonical: "/blog/how-to-clear-dead-stock-shopify" },
  keywords: ["dead stock Shopify", "clear dead inventory Shopify", "Shopify dead stock recovery", "aged inventory Shopify"],
  openGraph: {
    title: post.title,
    description: post.description,
    url: "/blog/how-to-clear-dead-stock-shopify",
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

export default function DeadStockPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <article className="blog-article">
        <BlogArticleMeta post={post} />
        <h1 className="blog-article-title">{post.title}</h1>
        <p className="blog-article-lead">
          Dead stock is inventory with little realistic demand at its current price. The right review window depends
          on the product: a seasonal item and a replenishable everyday item need different treatment. Compare
          these four options using likely cash recovery, selling costs, and how long stock will occupy space.
        </p>

        <h2 className="blog-article-h2">Why dead stock happens</h2>
        <p>
          Dead stock usually comes from one of three mistakes: over-forecasting demand during a new
          product launch, not adjusting reorder quantities when a SKU&apos;s velocity drops, or carrying
          units through a seasonal transition that doesn&apos;t sell out. The unit is on your shelf, the
          cash is tied up, and every month it sits there it loses a little more value.
        </p>
        <p>
          The cost isn&apos;t just opportunity cost. For merchants paying warehouse or
          third-party fulfillment storage fees, aged inventory has a direct monthly charge. For merchants holding their
          own stock, aged units occupy space that could hold faster-moving products.
        </p>

        <h2 className="blog-article-h2">How to define it before you act on it</h2>
        <p>
          Before picking a recovery plan, be precise. Aged inventory is not the same as dead stock:
        </p>
        <ul className="blog-article-ul">
          <li><strong>Slow mover:</strong> velocity has dropped but units still sell. Hold and adjust reorder quantity down.</li>
          <li><strong>Seasonal SKU:</strong> hasn&apos;t sold in 90 days because it&apos;s the off-season. Flag, don&apos;t liquidate.</li>
          <li><strong>True dead stock:</strong> no sales in 90+ days with no seasonal explanation and no upcoming event that would clear it.</li>
        </ul>
        <p>
          Acting on seasonal SKUs as dead stock is a common mistake - you sell the units at a loss in
          January and scramble to reorder in October.
        </p>

        <h2 className="blog-article-h2">The four plans</h2>

        <h3 className="blog-article-h3">Plan 1: Markdown</h3>
        <p>
          A price cut direct to Shopify retail customers. The simplest plan - no logistics change,
          no new relationships, immediate execution.
        </p>
        <p>
          When it makes sense: the unit has a real retail customer base, just at a lower price point.
          Seasonal items, last-season colorways, superseded versions of products that are still
          functional.
        </p>
        <p>
          The math: discount to the point where the margin recovered exceeds the ongoing storage cost
          over the time it would take to sell. If a unit costs $3/month to store and you expect to sell
          it in 6 months at full price, that&apos;s $18 in storage cost. A $15 reduction in net proceeds today would avoid $18 of storage in this example, leaving you $3 ahead
          before other costs and the time value of money. Compare net proceeds after fees and fulfillment.
        </p>
        <p>
          The risk: margin erosion, brand perception on perennially discounted items, and Shopify
          price history that shows customers full price followed by markdown, which trains them to wait.
        </p>

        <h3 className="blog-article-h3">Plan 2: Bundle</h3>
        <p>
          Combine the dead-stock unit with a fast-moving SKU into a kit and sell the bundle at a price
          that clears the slow unit while maintaining per-bundle margin.
        </p>
        <p>
          When it makes sense: you have a complementary product with real velocity. The dead-stock unit
          has value-add to the fast mover&apos;s customer - accessories, consumables, related products.
        </p>
        <p>
          The math: compare net contribution from the bundle with selling the fast mover alone. Include both
          product costs, packaging, fulfillment, and discounts. Test whether attaching the slow item increases
          recovery without simply discounting sales you would have made anyway.
        </p>
        <p>
          The complication: bundles require inventory tracking discipline. Keep component quantities synchronized in your store&apos;s bundle workflow. Skubase can help review
          component demand and reorder needs for configured bundles while stock updates stay in your store.
        </p>

        <h3 className="blog-article-h3">Plan 3: Wholesale / B2B</h3>
        <p>
          Sell remaining units in bulk to a retailer, reseller, or liquidator at below-retail prices.
          Clears units fast, recovers partial cost, and frees storage immediately.
        </p>
        <p>
          When it makes sense: unit volume is too large to clear through retail markdown in a reasonable
          timeframe, or the product is not a brand-sensitive item where wholesale pricing could undercut
          your retail channel.
        </p>
        <p>
          The math: compare the offer with expected later proceeds after carrying and selling costs. If you hold 500 units that cost $20 each, and storage is $1/unit/month,
          that&apos;s $500/month. Selling at $10/unit wholesale recovers $5,000 immediately versus $6,000
          in 12 months minus $6,000 in storage - a wash at best.
        </p>
        <p>
          Ask relevant retailers, existing wholesale contacts, or a liquidator for offers. Compare accepted
          quantities, freight responsibility, fees, payment timing, and any resale restrictions.
        </p>

        <h3 className="blog-article-h3">Plan 4: Write-off</h3>
        <p>
          When recovery costs exceed likely proceeds, consider disposal, recycling, or another appropriate exit.
          Keep an itemized record of quantities, costs, condition, and the action taken.
        </p>
        <p>
          When it makes sense: units are damaged, obsolete, or so niche that no buyer exists at any
          meaningful price. Also correct when the cost to sell (pick, pack, ship, process returns) plus
          storage while waiting exceeds wholesale value.
        </p>
        <p>
          Have your accountant determine the appropriate accounting and tax treatment from those records.
          Review stock values regularly so purchasing decisions reflect inventory you can realistically sell.
        </p>

        <h2 className="blog-article-h2">A decision framework</h2>
        <ol className="blog-article-ol">
          <li>Is this a seasonal SKU? Compare likely next-season recovery with storage costs and obsolescence risk.</li>
          <li>Does it have retail demand at a discount? If yes → markdown.</li>
          <li>Does it pair with a fast mover? If yes → bundle.</li>
          <li>Is the volume large enough for bulk clearance? If yes → wholesale.</li>
          <li>Does recovery cost exceed recovery value? → write-off.</li>
        </ol>

        <h2 className="blog-article-h2">How skubase surfaces this</h2>
        <p>
          Skubase surfaces slow and inactive inventory, then suggests markdown, bundle, wholesale, or write-off
          plans on supported subscriptions. The action queue helps you prioritize products and review projected
          recovery when costs are known. Compare the suggested action with your seasonal calendar and actual
          selling options, then carry out the chosen plan in your store.
        </p>

        <div className="blog-article-cta">
          <Link href="/liquidation?demo=1" className="button button-primary button-lg">See liquidation demo</Link>
          <Link href="/dashboard?demo=1" className="button button-ghost button-lg">See full dashboard</Link>
        </div>
      </article>

      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ARTICLE_LD) }} />

      <MarketingFooter />
    </div>
  );
}
