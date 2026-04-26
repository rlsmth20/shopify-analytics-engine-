import Link from "next/link";

export const metadata = {
  title: "Why a 6-month moving average is overstocking you",
  description:
    "If you reorder Shopify inventory when cover drops below six months, you're carrying more than you need to and still missing every seasonal ramp. Here's the math.",
  alternates: { canonical: "/blog/why-six-month-moving-average-overstocks-you" },
  keywords: [
    "Shopify forecasting",
    "moving average forecasting",
    "trailing average reorder",
    "ShipStation forecasting",
    "Google Sheet inventory",
    "safety stock formula",
    "service level inventory",
    "Holt forecasting",
  ],
  openGraph: {
    title: "Why a 6-month moving average is overstocking you",
    description: "Six-month moving averages overstock A-items and miss every seasonal ramp. Here's the math, and the fix.",
    url: "/blog/why-six-month-moving-average-overstocks-you",
    type: "article",
    publishedTime: "2026-04-25",
  },
  twitter: {
    card: "summary_large_image",
    title: "Why a 6-month moving average is overstocking you",
    description: "The math, and the fix.",
  },
};

const ARTICLE_LD = {
  "@context": "https://schema.org",
  "@type": "Article",
  headline: "Why a 6-month moving average is overstocking you",
  description:
    "If you reorder Shopify inventory when cover drops below six months, you're carrying more than you need to and still missing every seasonal ramp.",
  datePublished: "2026-04-25",
  dateModified: "2026-04-25",
  author: { "@type": "Organization", name: "slelfly" },
  publisher: {
    "@type": "Organization",
    name: "slelfly",
    url: "https://slelfly.com",
  },
};

export default function MovingAveragePost() {
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
          <Link href="/blog">Blog</Link>
          <Link href="/changelog">Changelog</Link>
        </nav>
        <div className="marketing-nav-ctas">
          <Link href="/login" className="marketing-link-subtle">Sign in</Link>
          <Link href="/dashboard" className="button button-primary">Open app</Link>
        </div>
      </header>

      <article className="blog-article">
        <p className="blog-article-meta">
          <time dateTime="2026-04-25">April 25, 2026</time> · 7 min read · Forecasting
        </p>
        <h1 className="blog-article-title">
          Why a 6-month moving average is overstocking you
        </h1>
        <p className="blog-article-lead">
          A common Shopify reorder workflow looks like this: export ShipStation
          shipment volume, paste it into a Google Sheet, compute a trailing
          six-month average per SKU, and reorder when cover drops below six
          months. It works. It also overstocks your fast movers, misses every
          seasonal ramp, and treats every SKU like it has the same business
          importance. Here&apos;s the math, and the fix.
        </p>

        <h2 className="blog-article-h2">What a 6-month rule actually says</h2>
        <p>
          When you reorder anything whose cover drops below six months,
          you&apos;re effectively saying: &quot;I want enough buffer that I
          can survive six months of average demand without restocking.&quot;
          That&apos;s a 99th-percentile-or-higher safety policy. For a
          high-velocity, low-variability A-item, that&apos;s a fortune in
          parked working capital. For a slow, lumpy C-item with a 12-week
          lead time, it might actually be too thin.
        </p>
        <p>
          The honest version of this policy is: <em>&quot;I don&apos;t want
          to think about it, so I&apos;m going to apply the worst-case
          buffer to every SKU.&quot;</em> That&apos;s reasonable when you
          have ten SKUs. It stops being reasonable around a hundred.
        </p>

        <h2 className="blog-article-h2">Why moving averages miss seasonality</h2>
        <p>
          A six-month moving average gives equal weight to every week in
          the window. If you&apos;re forecasting an October reorder using
          April-through-September data, your average is dominated by
          summer demand — which has nothing to do with what your customers
          will buy in November.
        </p>
        <p>
          The fix is some form of <strong>exponential smoothing</strong>{" "}
          (Holt-Winters or Holt double-exponential, depending on whether
          your business has seasonality), which weights recent observations
          more heavily and decomposes the signal into level, trend, and
          seasonal components. The math has been around since the 1950s;
          the spreadsheet just doesn&apos;t do it.
        </p>

        <h2 className="blog-article-h2">Why one buffer per SKU is wrong</h2>
        <p>
          The textbook formula for safety stock is:
        </p>
        <p className="blog-article-formula">
          Safety stock = z × σ_LT
        </p>
        <p>
          Where <em>σ_LT</em> is the standard deviation of demand during
          the lead time, and <em>z</em> is the z-score for your desired
          service level. (Service level is the probability that you
          don&apos;t stock out during the lead time.)
        </p>
        <p>
          The point of <em>z</em> is that <strong>different SKUs deserve
          different service levels.</strong> Your top-revenue A-items
          probably want a 99% service level (z ≈ 2.33). Your lumpy,
          end-of-life C-items might be fine at 90% (z ≈ 1.28) or even
          85%. A flat &quot;6 months of cover&quot; rule applies the
          same z to everything, which means you&apos;re either
          overstocking C-items or understocking A-items. Usually both.
        </p>

        <h2 className="blog-article-h2">The simple ABC × XYZ trick</h2>
        <p>
          A useful first cut is to classify every SKU on two axes:
        </p>
        <ul className="blog-article-ul">
          <li>
            <strong>ABC</strong>: by revenue contribution. A = top 80% of
            revenue, B = next 15%, C = last 5%. (Roughly the Pareto cut.)
          </li>
          <li>
            <strong>XYZ</strong>: by demand variability (coefficient of
            variation). X = stable, Y = somewhat variable, Z = lumpy.
          </li>
        </ul>
        <p>
          Then assign service levels to each cell of the 3×3 grid. AX
          items are revenue-critical and predictable — they get the
          highest service level. CZ items are low-revenue and unpredictable
          — they get the lowest. Most of your inventory dollars sit in AX
          and AY, and those are the ones a flat 6-month rule
          systematically overstocks.
        </p>

        <h2 className="blog-article-h2">A worked example</h2>
        <p>
          Imagine an A-item that ships 150 units per week with a standard
          deviation of 20 units. Lead time is 30 days. Average demand
          during lead time is roughly 643 units (150 × 30/7). σ_LT is
          roughly 47 units (20 × √(30/7)).
        </p>
        <ul className="blog-article-ul">
          <li>
            <strong>6-month rule:</strong> 150 × 26 = 3,900 units of cover.
            That&apos;s an enormous buffer for a stable, fast-moving item.
            If unit cost is $25, that&apos;s $97,500 in parked inventory
            for one SKU.
          </li>
          <li>
            <strong>Service-level-segmented:</strong> reorder point = 643 +
            (2.33 × 47) ≈ 753 units. Plus a small cycle stock to cover
            order frequency, say another 150 units. Total cover ≈ 900
            units. At $25, that&apos;s $22,500.
          </li>
        </ul>
        <p>
          The math says you can run the same 99% service level with
          roughly <strong>$75,000 less in working capital tied up in this
          one SKU</strong>. Multiply across a hundred A-items and the
          number gets very large very fast.
        </p>
        <p className="blog-article-aside">
          (Worked example simplified for readability — real reorder math
          also folds in cycle service level, lead time variability, and
          stockout probability over the planning horizon. slelfly does
          all three; the spreadsheet does none.)
        </p>

        <h2 className="blog-article-h2">What about lead-time variability?</h2>
        <p>
          The other reason 6-month rules feel safe is that they implicitly
          buffer against suppliers that miss promised lead times. The fix
          isn&apos;t to overstock everything — it&apos;s to <strong>measure
          your suppliers</strong> and adjust the lead-time assumption per
          vendor based on their actual on-time and fill-rate history.
          Reliable suppliers get tighter buffers. Unreliable ones either
          get bigger buffers or get fired.
        </p>
        <p>
          That&apos;s what slelfly&apos;s supplier scorecards do. The
          spreadsheet doesn&apos;t track this; you&apos;d have to build
          it manually, and you won&apos;t.
        </p>

        <h2 className="blog-article-h2">Three things to do this week</h2>
        <ol className="blog-article-ol">
          <li>
            <strong>Tag your top 20 SKUs.</strong> If they&apos;re A-items,
            their service level should be high but their cover should be
            measured in weeks, not months. You&apos;re probably overstocking
            them.
          </li>
          <li>
            <strong>Pull a vendor on-time history.</strong> If a supplier
            has missed lead times by more than 20% three POs in a row,
            either widen their buffer specifically or move volume to a
            backup. Don&apos;t pay for their unreliability with a
            blanket 6-month rule.
          </li>
          <li>
            <strong>Stop reordering by averages.</strong> Even a simple
            exponential smoothing layer is dramatically better than a
            trailing average for any catalog with seasonality, and most
            do. <Link href="/import-shipstation">Drop your ShipStation
            export into slelfly</Link> and the math runs in 60 seconds.
          </li>
        </ol>

        <h2 className="blog-article-h2">Why slelfly</h2>
        <p>
          We built slelfly because we kept watching merchants do the
          ShipStation-to-Sheet workflow and tie up cash they didn&apos;t
          need to. The tool runs Holt double-exponential smoothing with a
          weekly seasonality factor on every SKU, classifies on ABC ×
          XYZ, sets safety stock per class, scores suppliers on on-time
          and fill rate, and surfaces stockout probability on every card.
          The math is visible — every recommended quantity explains
          itself. <Link href="/vs-spreadsheet">Side-by-side vs the
          spreadsheet</Link>.
        </p>
        <p>
          Pricing is published — three tiers from $49/mo — and renewals do
          not raise the rate on your plan. That&apos;s in the terms of
          service. <Link href="/pricing">See pricing</Link>.
        </p>

        <div className="blog-article-cta">
          <Link href="/import-shipstation" className="button button-primary button-lg">
            Drop in your ShipStation export
          </Link>
          <Link href="/vs-spreadsheet" className="button button-ghost button-lg">
            More: vs. spreadsheet
          </Link>
        </div>
      </article>

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(ARTICLE_LD) }}
      />

      <footer className="marketing-footer">
        <div className="marketing-footer-brand">
          <span className="marketing-brand-mark">sf</span>
          <span>slelfly</span>
        </div>
        <div className="marketing-footer-links">
          <Link href="/">Home</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/about">About</Link>
          <Link href="/blog">Blog</Link>
          <Link href="/changelog">Changelog</Link>
          <Link href="/vs-spreadsheet">vs. spreadsheet</Link>
        </div>
        <p className="marketing-footer-fine">
          © {new Date().getFullYear()} slelfly · Independent · Founder-led ·
          Prices locked at renewal
        </p>
      </footer>
    </div>
  );
}
