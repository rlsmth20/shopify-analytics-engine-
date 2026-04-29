import Link from "next/link";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "Why a 6-month moving average is overstocking you",
  description: "If you reorder Shopify inventory when cover drops below six months, you''re carrying more than you need to.",
  alternates: { canonical: "/blog/why-six-month-moving-average-overstocks-you" },
  openGraph: { title: "Why a 6-month moving average is overstocking you", description: "The math, and the fix.", url: "/blog/why-six-month-moving-average-overstocks-you", type: "article" },
};

const ARTICLE_LD = {
  "@context": "https://schema.org",
  "@type": "Article",
  headline: "Why a 6-month moving average is overstocking you",
  datePublished: "2026-04-25",
  author: { "@type": "Organization", name: "skubase" },
};

export default function MovingAveragePost() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <article className="blog-article">
        <p className="blog-article-meta">
          <time dateTime="2026-04-25">April 25, 2026</time> Â· 7 min read Â· Forecasting
        </p>
        <h1 className="blog-article-title">Why a 6-month moving average is overstocking you</h1>
        <p className="blog-article-lead">
          A common Shopify reorder workflow: export ShipStation shipment volume, paste into a Google Sheet, compute a trailing six-month average per SKU, reorder when cover drops below six months. It works. It also overstocks fast movers and misses every seasonal ramp.
        </p>

        <h2 className="blog-article-h2">What a 6-month rule actually says</h2>
        <p>
          Reordering when cover drops below six months is effectively a 99th-percentile-or-higher safety policy. For a high-velocity, low-variability A-item, that&apos;s a fortune in parked working capital. The honest version: <em>&quot;I don&apos;t want to think about it, so I apply the worst-case buffer to every SKU.&quot;</em>
        </p>

        <h2 className="blog-article-h2">Why moving averages miss seasonality</h2>
        <p>
          A six-month moving average gives equal weight to every week. If you&apos;re forecasting an October reorder using April-through-September data, your average is dominated by summer demand â€” which has nothing to do with what your customers buy in November.
        </p>
        <p>
          The fix is exponential smoothing (Holt-Winters or Holt double-exponential), which weights recent observations more heavily and decomposes the signal into level, trend, and seasonal components.
        </p>

        <h2 className="blog-article-h2">Why one buffer per SKU is wrong</h2>
        <p className="blog-article-formula">Safety stock = z Ã— Ïƒ_LT</p>
        <p>
          The point of <em>z</em> is that <strong>different SKUs deserve different service levels.</strong> Top-revenue A-items want 99% (z â‰ˆ 2.33). Lumpy C-items might be fine at 90%. A flat &quot;6 months&quot; applies the same z to everything. Result: overstocking C-items, understocking A-items, usually both.
        </p>

        <h2 className="blog-article-h2">A worked example</h2>
        <p>
          A-item shipping 150/wk, Ïƒ=20, lead time 30 days. Average lead-time demand â‰ˆ 643 units. Ïƒ_LT â‰ˆ 47 units.
        </p>
        <ul className="blog-article-ul">
          <li><strong>6-month rule:</strong> 150 Ã— 26 = 3,900 units of cover. At $25/unit = $97,500 parked.</li>
          <li><strong>Service-level-segmented at 99%:</strong> ROP â‰ˆ 753, plus cycle stock â‰ˆ 900 total. At $25 = $22,500.</li>
        </ul>
        <p>
          Same 99% service level, <strong>$75,000 less working capital tied up in one SKU</strong>. Multiply across a hundred A-items and the number gets very large.
        </p>

        <h2 className="blog-article-h2">Three things to do this week</h2>
        <ol className="blog-article-ol">
          <li>Tag your top 20 SKUs. Their cover should be measured in weeks, not months.</li>
          <li>Pull a vendor on-time history. Don&apos;t pay for vendor unreliability with a blanket 6-month rule.</li>
          <li>Stop reordering by averages. Even simple exponential smoothing dramatically beats trailing average.</li>
        </ol>

        <h2 className="blog-article-h2">Why skubase</h2>
        <p>
          skubase runs Holt double-exponential with weekly seasonality on every SKU, classifies on ABC Ã— XYZ, sets safety stock per class, scores suppliers, surfaces stockout probability. The math is visible â€” every recommended quantity explains itself.
        </p>

        <div className="blog-article-cta">
          <Link href="/" className="button button-primary button-lg">Get early access</Link>
          <Link href="/vs-spreadsheet" className="button button-ghost button-lg">More: vs. spreadsheet</Link>
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
        <p className="marketing-footer-fine">Â© {new Date().getFullYear()} skubase</p>
      </footer>
    </div>
  );
}

