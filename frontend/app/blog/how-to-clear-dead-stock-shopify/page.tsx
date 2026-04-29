import Link from "next/link";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "How to clear dead stock on Shopify: markdown, bundle, wholesale, or write-off — skubase",
  description: "Dead stock on Shopify costs you storage, cash, and opportunity. Here are four concrete plans — with the math on when each one makes sense.",
  alternates: { canonical: "/blog/how-to-clear-dead-stock-shopify" },
  keywords: ["dead stock Shopify", "clear dead inventory Shopify", "Shopify dead stock recovery", "aged inventory Shopify"],
  openGraph: {
    title: "How to clear dead stock on Shopify",
    description: "Markdown, bundle, wholesale, or write-off — and the math on when each one makes sense.",
    url: "/blog/how-to-clear-dead-stock-shopify",
    type: "article",
  },
};

const ARTICLE_LD = {
  "@context": "https://schema.org",
  "@type": "Article",
  headline: "How to clear dead stock on Shopify: markdown, bundle, wholesale, or write-off",
  datePublished: "2026-04-29",
  author: { "@type": "Organization", name: "skubase" },
};

export default function DeadStockPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <article className="blog-article">
        <p className="blog-article-meta">
          <time dateTime="2026-04-29">April 29, 2026</time> · 8 min read · Liquidation
        </p>
        <h1 className="blog-article-title">How to clear dead stock on Shopify: markdown, bundle, wholesale, or write-off</h1>
        <p className="blog-article-lead">
          Dead stock is inventory that hasn&apos;t sold in 90+ days and shows no sign of selling at full
          price. Most inventory tools tell you it exists. Almost none tell you what to do about it. This
          post covers four concrete plans — with the math on when each one makes sense — so you can
          stop paying to store units that aren&apos;t selling.
        </p>

        <h2 className="blog-article-h2">Why dead stock happens</h2>
        <p>
          Dead stock usually comes from one of three mistakes: over-forecasting demand during a new
          product launch, not adjusting reorder quantities when a SKU&apos;s velocity drops, or carrying
          units through a seasonal transition that doesn&apos;t sell out. The unit is on your shelf, the
          cash is tied up, and every month it sits there it loses a little more value.
        </p>
        <p>
          The cost isn&apos;t just opportunity cost. For merchants paying Shopify Fulfillment Network or
          3PL storage fees, aged inventory has a direct monthly charge. For merchants holding their
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
          Acting on seasonal SKUs as dead stock is a common mistake — you sell the units at a loss in
          January and scramble to reorder in October.
        </p>

        <h2 className="blog-article-h2">The four plans</h2>

        <h3 className="blog-article-h3">Plan 1: Markdown</h3>
        <p>
          A price cut direct to Shopify retail customers. The simplest plan — no logistics change,
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
          it in 6 months at full price, that&apos;s $18 in storage cost. A markdown that gets you $20 more
          now is better — even at lower margin — because you also free up capital.
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
          has value-add to the fast mover&apos;s customer — accessories, consumables, related products.
        </p>
        <p>
          The math: price the bundle at (fast mover price) + (dead stock recovery amount) — typically
          10–30% of the dead stock unit&apos;s cost. If you can sell 200 bundles per month at a 40% margin
          versus zero units of dead stock at any margin, the bundle wins even at a low dead-stock recovery.
        </p>
        <p>
          The complication: bundles require inventory tracking discipline. If your Shopify store doesn&apos;t
          decompose bundle sales back to component SKUs, you&apos;ll oversell. Tools like skubase track
          bundle components and flag reorder needs at the component level.
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
          The math: wholesale at 30–50% of cost is often better than holding for 12+ months of storage
          fees. Run the numbers. If you hold 500 units that cost $20 each, and storage is $1/unit/month,
          that&apos;s $500/month. Selling at $10/unit wholesale recovers $5,000 immediately versus $6,000
          in 12 months minus $6,000 in storage — a wash at best.
        </p>
        <p>
          Routes: Faire for wholesale B2B, direct to a liquidator (Bulq, Direct Liquidation), or
          a retailer in a non-competing geography.
        </p>

        <h3 className="blog-article-h3">Plan 4: Write-off</h3>
        <p>
          Declare the inventory worthless, take the accounting write-off, and move on. Correct when
          recovery cost exceeds recovery value.
        </p>
        <p>
          When it makes sense: units are damaged, obsolete, or so niche that no buyer exists at any
          meaningful price. Also correct when the cost to sell (pick, pack, ship, process returns) plus
          storage while waiting exceeds wholesale value.
        </p>
        <p>
          The benefit: a write-off is a real tax deduction. Consult your accountant — depending on your
          structure, writing off dead inventory can offset income meaningfully. It also forces an honest
          accounting of your inventory quality instead of carrying ghost value on the books.
        </p>

        <h2 className="blog-article-h2">A decision framework</h2>
        <ol className="blog-article-ol">
          <li>Is this a seasonal SKU? If yes, flag it and revisit before next season. Do not liquidate.</li>
          <li>Does it have retail demand at a discount? If yes → markdown.</li>
          <li>Does it pair with a fast mover? If yes → bundle.</li>
          <li>Is the volume large enough for bulk clearance? If yes → wholesale.</li>
          <li>Does recovery cost exceed recovery value? → write-off.</li>
        </ol>

        <h2 className="blog-article-h2">How skubase surfaces this</h2>
        <p>
          skubase&apos;s liquidation module flags dead-stock SKUs automatically — units with 90+ days
          of no sales — and proposes a plan based on margin, velocity, and whether a bundle partner
          exists. The action queue shows the dollar impact attached to each proposed plan so you
          can prioritize by cash recovery, not by guesswork.
        </p>

        <div className="blog-article-cta">
          <Link href="/liquidation?demo=1" className="button button-primary button-lg">See liquidation demo</Link>
          <Link href="/dashboard?demo=1" className="button button-ghost button-lg">See full dashboard</Link>
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
