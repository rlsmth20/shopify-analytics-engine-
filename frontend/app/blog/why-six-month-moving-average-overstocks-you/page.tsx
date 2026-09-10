import Link from "next/link";
import { MarketingNav } from "@/components/marketing-nav";
import { MarketingFooter } from "@/components/marketing-footer";

import { BLOG_POSTS } from "@/lib/blog-posts";
import { BlogArticleMeta } from "@/components/blog-article-meta";

const post = BLOG_POSTS["why-six-month-moving-average-overstocks-you"];

export const metadata = {
  title: `${post.title} - skubase`,
  description: post.description,
  alternates: { canonical: "/blog/why-six-month-moving-average-overstocks-you" },
  openGraph: { title: post.title, description: post.description, url: "/blog/why-six-month-moving-average-overstocks-you", type: "article" },
};

const ARTICLE_LD = {
  "@context": "https://schema.org",
  "@type": "Article",
  headline: post.title,
  datePublished: post.publishedAt,
  dateModified: post.updatedAt,
  author: { "@type": "Organization", name: "skubase" },
};

export default function MovingAveragePost() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <article className="blog-article">
        <BlogArticleMeta post={post} />
        <h1 className="blog-article-title">{post.title}</h1>
        <p className="blog-article-lead">
          A six-month sales average can help you understand demand. Holding six months of stock is a separate decision. If you use one blanket stock target for every product, short-lead-time items can tie up cash while seasonal products still need attention.
        </p>

        <h2 className="blog-article-h2">What a 6-month rule actually says</h2>
        <p>
          Your history window estimates demand. Your reorder point decides when to buy, and your order quantity decides how much to buy. Set those using supplier lead time, demand variability, order minimums, and your review schedule. A six-month stock target does not imply a particular service level.
        </p>

        <h2 className="blog-article-h2">Why moving averages miss seasonality</h2>
        <p>
          A six-month moving average gives equal weight to every week. If you&apos;re forecasting an October reorder using April-through-September data, the average combines spring and summer trading. Compare that baseline with recent demand and your actual seasonal sales pattern before placing an autumn order.
        </p>
        <p>
          Trend and seasonal models can help when the data supports them. <a href="https://otexts.com/fpp3/holt.html">Holt&apos;s method</a> models level and trend; <a href="https://otexts.com/fpp3/holt-winters.html">Holt-Winters</a> adds a seasonal component. Compare forecast errors on held-out sales history before choosing a method.
        </p>

        <h2 className="blog-article-h2">Why one buffer per SKU is wrong</h2>
        <p className="blog-article-formula">Safety stock = z × σ_LT</p>
        <p>
          Here, σ_LT is the standard deviation of demand during lead time, and z represents a target cycle service level under a normal approximation. Choose targets by the cost of a stockout, margin, and customer expectations. A blanket number of buffer days does not account for differences in variability.
        </p>

        <h2 className="blog-article-h2">A worked example</h2>
        <p>
          Illustrative assumptions: average demand is 150 units per week, weekly demand standard deviation is 20 units, independent weekly demand, and a fixed 30-day supplier lead time. Expected lead-time demand is 150 × 30/7 ≈ 643 units. Its standard deviation is 20 × √(30/7) ≈ 41.4 units.
        </p>
        <ul className="blog-article-ul">
          <li><strong>Six-month cover target:</strong> 150 × 26 = 3,900 units.</li>
          <li><strong>Illustrative 99% cycle-service reorder point:</strong> 643 + 2.326 × 41.4 ≈ 740 units after rounding up.</li>
        </ul>
        <p>
          The reorder point is an ordering trigger, not average inventory or a promised cash saving. Check inventory position (on hand plus on order minus backorders), then choose an order quantity that fits your buying cycle and supplier minimums. Compare actual stockouts and average stock over subsequent replenishment cycles.
        </p>

        <h2 className="blog-article-h2">Three things to do this week</h2>
        <ol className="blog-article-ol">
          <li>Review your top 20 SKUs. Compare their cover with supplier lead times and upcoming promotions.</li>
          <li>Record order and receipt dates so your supplier lead-time settings reflect actual deliveries.</li>
          <li>Compare a recent-demand forecast with your existing average on the same historical periods. Keep the method that supports better decisions.</li>
        </ol>

        <h2 className="blog-article-h2">Why skubase</h2>
        <p>
          Skubase brings recent sales, stock on hand, supplier lead times, and safety buffers into a ranked reorder queue. Forecast views use trend and weekly patterns when enough history is available. Review a recommendation, create a supplier-grouped PO draft, and export an Excel workbook for your next purchasing discussion.
        </p>

        <p><Link href="/tools/reorder-point-calculator">Try the free reorder-point calculator</Link> with your own daily demand and supplier lead time.</p>

        <div className="blog-article-cta">
          <Link href="/login" className="button button-primary button-lg">Start free trial</Link>
          <Link href="/vs-spreadsheet" className="button button-ghost button-lg">More: vs. spreadsheet</Link>
        </div>
      </article>

      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ARTICLE_LD) }} />

      <MarketingFooter />
    </div>
  );
}

