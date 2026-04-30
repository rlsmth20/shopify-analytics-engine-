Set-Location 'C:\Users\Rainer\Shopify_Analytics_Engine'

Set-Content -Path 'C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\about\page.tsx' -Value @'
import Link from "next/link";

import { WaitlistForm } from "@/components/waitlist-form";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "About — skubase",
  description: "Independent, founder-led, Shopify-first. No PE squeeze.",
  alternates: { canonical: "/about" },
  openGraph: { title: "About skubase — Independent. Founder-led. No PE squeeze.", description: "Eight of the inventory tools you evaluate were acquired and got worse. skubase is structurally outside that pattern.", url: "/about", type: "website" },
};

const beliefs = [
  { title: "Inventory is a decision problem, not a reporting problem.", body: "Most inventory tools are dashboards — they tell you what happened and leave you to act. skubase ranks the decisions: what to reorder, what is overstocked, what is dead, what to do first." },
  { title: "Math should be visible.", body: "Every recommended quantity explains itself. Trailing demand, seasonality factor, service level, stockout probability — all on the card, all clickable." },
  { title: "Suppliers are measurable.", body: "23 of 25 tools we studied treat vendors as contact records. We treat them as performers. On-time delivery, fill rate, lead-time stability, tiering. Facts, not feelings." },
  { title: "Dead stock is a cash recovery problem.", body: "24 of 25 tools flag aged inventory and stop. We propose the specific plan — markdown, bundle, wholesale, or write-off — with the dollar impact attached." },
  { title: "Pricing should be published and locked.", body: "7 of 25 tools are quote-only. 6 of 25 have public complaints about renewal-time price hikes. We publish our prices and commit in writing not to raise them." }
];

const notLikeUs = [
  { competitor: "Inventory Planner", owner: "Sage (2021)", pattern: "Users reported ~3× price hikes and support regression after the acquisition." },
  { competitor: "Linnworks", owner: "Marlin Equity (PE)", pattern: "Trustpilot reviews cite a 681% renewal price hike and support collapse." },
  { competitor: "Veeqo", owner: "Amazon (2021)", pattern: "Non-Amazon merchants raised data concerns; roadmap visibly slowed." },
  { competitor: "Skubana", owner: "Extensiv", pattern: "Forced platform migration created documented churn and billing confusion." },
  { competitor: "Cin7 Core (DEAR)", owner: "Cin7", pattern: "Post-rebrand price restructuring moved legacy DEAR contracts up tiers." },
  { competitor: "Sellbrite", owner: "GoDaddy (2019)", pattern: "Users describe the roadmap as frozen for two-plus years." },
  { competitor: "Brightpearl", owner: "Sage (2022)", pattern: "Quote-only pricing, 6-month implementations, post-acquisition support slips." },
  { competitor: "SKUVault", owner: "Linnworks (2022)", pattern: "Same PE owner as Linnworks; buyers now wary." }
];

export default function AboutPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero">
        <p className="marketing-eyebrow">About skubase</p>
        <h1 className="marketing-hero-title">Independent. Founder-led. Shopify-first.</h1>
        <p className="marketing-hero-sub">
          Eight of the 25 inventory tools we benchmark against have been acquired by a parent that raised prices, slowed the roadmap, or broke support. skubase is structurally outside that pattern.
        </p>
      </section>

      <section className="about-pledge">
        <div className="about-pledge-card">
          <p className="about-pledge-kicker">Our commitments to you</p>
          <ul className="about-pledge-list">
            <li><strong>No PE squeeze.</strong> We are founder-owned and not raising venture capital on terms that force renewal hikes.</li>
            <li><strong>No surprise price changes.</strong> Your rate at sign-up is your rate for as long as you stay subscribed. That is in the <Link href="/terms">terms of service</Link>.</li>
            <li><strong>No quote-only pricing.</strong> Every tier is published on the pricing page.</li>
            <li><strong>No consultant-required onboarding.</strong> Most merchants see their first ranked action in under ten minutes.</li>
            <li><strong>A public changelog.</strong> Every release lands on the <Link href="/changelog">changelog page</Link>.</li>
          </ul>
        </div>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">What we believe</p>
        <h2 className="marketing-section-title">Five ideas that shape the product.</h2>
        <div className="beliefs-grid">
          {beliefs.map((b) => (
            <article key={b.title} className="belief-card">
              <h3 className="belief-card-title">{b.title}</h3>
              <p className="belief-card-body">{b.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-section-alt">
        <p className="marketing-section-kicker">Why independence matters</p>
        <h2 className="marketing-section-title">The tools you evaluated and what happened to them.</h2>
        <p className="marketing-section-sub">Documented patterns from public reviews. We cite them because the pattern is real and our independence is a concrete difference, not a slogan.</p>
        <div className="acquisitions-list">
          {notLikeUs.map((n) => (
            <article key={n.competitor} className="acquisition-card">
              <div>
                <p className="acquisition-card-name">{n.competitor}</p>
                <p className="acquisition-card-owner">{n.owner}</p>
              </div>
              <p className="acquisition-card-pattern">{n.pattern}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-cta-section">
        <p className="marketing-section-kicker">Get early access</p>
        <h2 className="marketing-section-title">If this take resonates, get on the list.</h2>
        <p className="marketing-section-sub">
          skubase is in private beta. Drop your email — we&apos;ll send your invite when paid plans launch.
        </p>
        <WaitlistForm source="about" ctaLabel="Get early access" />
      </section>

      <footer className="marketing-footer">
        <div className="marketing-footer-brand">
          <span className="marketing-brand-mark">sb</span>
          <span>skubase</span>
        </div>
        <div className="marketing-footer-links">
          <Link href="/">Home</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/about">About</Link>
          <Link href="/blog">Blog</Link>
          <Link href="/changelog">Changelog</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">© {new Date().getFullYear()} skubase · Independent · Founder-led</p>
      </footer>
    </div>
  );
}

'@ -Encoding UTF8
Write-Host 'Wrote: C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\about\page.tsx'

Set-Content -Path 'C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\blog\page.tsx' -Value @'
import Link from "next/link";

import { WaitlistForm } from "@/components/waitlist-form";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "Blog — skubase",
  description: "Posts about Shopify inventory, forecasting, supplier scoring, dead stock, and the rest of the math the spreadsheet can''t do.",
  alternates: { canonical: "/blog" },
  openGraph: { title: "skubase blog", description: "Shopify inventory, forecasting, and supplier intelligence.", url: "/blog", type: "website" },
};

const posts = [
  { slug: "stocky-alternatives-2026", title: "Stocky alternatives for Shopify merchants in 2026", date: "2026-04-25", description: "Shopify is shutting down Stocky on August 31, 2026. Here are the realistic replacements.", minutes: 8 },
  { slug: "why-six-month-moving-average-overstocks-you", title: "Why a 6-month moving average is overstocking you", date: "2026-04-25", description: "If you reorder when cover drops below six months, you''re carrying more inventory than you need to.", minutes: 7 },
];

export default function BlogIndex() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero">
        <p className="marketing-eyebrow">Blog</p>
        <h1 className="marketing-hero-title">Inventory, written carefully.</h1>
        <p className="marketing-hero-sub">
          Posts about forecasting, supplier scoring, dead stock, and the rest of the math the spreadsheet can&apos;t do.
        </p>
      </section>

      <section className="blog-list">
        {posts.map((p) => (
          <article key={p.slug} className="blog-list-item">
            <p className="blog-list-meta">
              <time dateTime={p.date}>{p.date}</time>
              <span> · {p.minutes} min read</span>
            </p>
            <h2 className="blog-list-title">
              <Link href={`/blog/${p.slug}`}>{p.title}</Link>
            </h2>
            <p className="blog-list-desc">{p.description}</p>
            <Link href={`/blog/${p.slug}`} className="blog-list-link">Read post →</Link>
          </article>
        ))}
      </section>

      <section className="marketing-section marketing-cta-section">
        <p className="marketing-section-kicker">Get early access</p>
        <h2 className="marketing-section-title">Want the next post in your inbox?</h2>
        <p className="marketing-section-sub">
          We send the new post and the early-access invite to the same list. Drop your email — that&apos;s it.
        </p>
        <WaitlistForm source="blog_index" ctaLabel="Get early access" />
      </section>

      <footer className="marketing-footer">
        <div className="marketing-footer-brand">
          <span className="marketing-brand-mark">sb</span>
          <span>skubase</span>
        </div>
        <div className="marketing-footer-links">
          <Link href="/">Home</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/about">About</Link>
          <Link href="/changelog">Changelog</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">© {new Date().getFullYear()} skubase</p>
      </footer>
    </div>
  );
}

'@ -Encoding UTF8
Write-Host 'Wrote: C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\blog\page.tsx'

Set-Content -Path 'C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\blog\stocky-alternatives-2026\page.tsx' -Value @'
import Link from "next/link";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "Stocky alternatives for Shopify merchants in 2026",
  description: "Shopify is shutting down Stocky on August 31, 2026. Here are the realistic replacements.",
  alternates: { canonical: "/blog/stocky-alternatives-2026" },
  keywords: ["Stocky alternative", "Stocky shutdown", "Shopify Stocky end of life"],
  openGraph: { title: "Stocky alternatives for Shopify merchants in 2026", description: "Stocky ends Aug 31, 2026.", url: "/blog/stocky-alternatives-2026", type: "article" },
};

const ARTICLE_LD = {
  "@context": "https://schema.org",
  "@type": "Article",
  headline: "Stocky alternatives for Shopify merchants in 2026",
  datePublished: "2026-04-25",
  author: { "@type": "Organization", name: "skubase" },
};

export default function StockyAlternativesPost() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <article className="blog-article">
        <p className="blog-article-meta">
          <time dateTime="2026-04-25">April 25, 2026</time> · 8 min read · Migration
        </p>
        <h1 className="blog-article-title">Stocky alternatives for Shopify merchants in 2026</h1>
        <p className="blog-article-lead">
          Shopify announced that Stocky reaches end of life on <strong>August 31, 2026</strong>. Thousands of POS Pro merchants now have to pick a replacement before the lights go out. This is the short, honest list.
        </p>

        <h2 className="blog-article-h2">What Stocky did well, and what it didn&apos;t</h2>
        <p>
          Stocky was loved for being free (bundled with $89/mo POS Pro), Shopify-native, and easy. It generated suggested POs, tracked transfers, and did basic forecasting from a trailing window of sales.
        </p>
        <p>
          What it never did well: real forecasting beyond trailing averages, supplier scorecarding, dead-stock plans, or alerts beyond email. Past a couple thousand SKUs, it felt like a notebook with extra steps.
        </p>

        <h2 className="blog-article-h2">The replacements worth considering</h2>

        <h3 className="blog-article-h3">skubase</h3>
        <p>
          We built skubase partly because we couldn&apos;t find a Stocky replacement that did the math right. Holt double-exponential smoothing with weekly seasonality, stockout probability per SKU, supplier scorecards (on-time, fill rate), markdown/bundle/wholesale/write-off plans for dead stock. Pricing published, three tiers from $49/mo, with a written price-lock clause in TOS. <Link href="/goodbye-stocky">Migration page</Link>.
        </p>

        <h3 className="blog-article-h3">Inventory Planner (Sage)</h3>
        <p>
          Historically the go-to. Acquired by Sage in 2021. Customers report ~3× price hikes and slower support post-acquisition. Strong forecasting math, but the post-acquisition trajectory has cost it goodwill.
        </p>

        <h3 className="blog-article-h3">Prediko</h3>
        <p>
          Newer Shopify-first AI forecasting. Strong forecasting surface but Shopify-only. Multi-location is recent. $119–$599/mo, published.
        </p>

        <h3 className="blog-article-h3">Cin7 Core (DEAR)</h3>
        <p>
          Mid-market IMS. Heavier than Stocky. Quoted $349–$999/mo plus implementation, often with a partner consultant. Probably overkill if Stocky was enough.
        </p>

        <h3 className="blog-article-h3">Sumtracker</h3>
        <p>
          Lightweight Shopify SMB tool. Sync hiccups in reviews. Forecasting basic. Easy switch for merchants who used Stocky mostly to track quantities.
        </p>

        <h2 className="blog-article-h2">How to evaluate, in order</h2>
        <ol className="blog-article-ol">
          <li><strong>Export your Stocky data now.</strong> Don&apos;t wait until July.</li>
          <li><strong>Decide if you need multi-channel.</strong> If you sell on Amazon/eBay, your tool either does channel sync (Linnworks, Veeqo, EComDash) or pairs with one.</li>
          <li><strong>Check pricing transparency.</strong> Quote-only is a warning sign.</li>
          <li><strong>Check ownership.</strong> 8 of 25 tools we benchmark against got worse after acquisition.</li>
          <li><strong>Insist on self-serve setup.</strong> If the answer is &quot;book a demo,&quot; you&apos;re on a 6-month implementation track.</li>
        </ol>

        <h2 className="blog-article-h2">A note on the timeline</h2>
        <p>
          You have until August 31, 2026 — about four months from this post. Pick by June 1. Run both for two months. Cut over in August.
        </p>

        <h2 className="blog-article-h2">If skubase looks right</h2>
        <p>
          We built a one-step CSV importer for Stocky&apos;s standard product export — your SKUs, vendors, and on-hand counts intact, first ranked action in under ten minutes.
        </p>

        <div className="blog-article-cta">
          <Link href="/" className="button button-primary button-lg">Get early access</Link>
          <Link href="/goodbye-stocky" className="button button-ghost button-lg">See migration details</Link>
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
        <p className="marketing-footer-fine">© {new Date().getFullYear()} skubase</p>
      </footer>
    </div>
  );
}

'@ -Encoding UTF8
Write-Host 'Wrote: C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\blog\stocky-alternatives-2026\page.tsx'

Set-Content -Path 'C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\blog\why-six-month-moving-average-overstocks-you\page.tsx' -Value @'
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
          <time dateTime="2026-04-25">April 25, 2026</time> · 7 min read · Forecasting
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
          A six-month moving average gives equal weight to every week. If you&apos;re forecasting an October reorder using April-through-September data, your average is dominated by summer demand — which has nothing to do with what your customers buy in November.
        </p>
        <p>
          The fix is exponential smoothing (Holt-Winters or Holt double-exponential), which weights recent observations more heavily and decomposes the signal into level, trend, and seasonal components.
        </p>

        <h2 className="blog-article-h2">Why one buffer per SKU is wrong</h2>
        <p className="blog-article-formula">Safety stock = z × σ_LT</p>
        <p>
          The point of <em>z</em> is that <strong>different SKUs deserve different service levels.</strong> Top-revenue A-items want 99% (z ≈ 2.33). Lumpy C-items might be fine at 90%. A flat &quot;6 months&quot; applies the same z to everything. Result: overstocking C-items, understocking A-items, usually both.
        </p>

        <h2 className="blog-article-h2">A worked example</h2>
        <p>
          A-item shipping 150/wk, σ=20, lead time 30 days. Average lead-time demand ≈ 643 units. σ_LT ≈ 47 units.
        </p>
        <ul className="blog-article-ul">
          <li><strong>6-month rule:</strong> 150 × 26 = 3,900 units of cover. At $25/unit = $97,500 parked.</li>
          <li><strong>Service-level-segmented at 99%:</strong> ROP ≈ 753, plus cycle stock ≈ 900 total. At $25 = $22,500.</li>
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
          skubase runs Holt double-exponential with weekly seasonality on every SKU, classifies on ABC × XYZ, sets safety stock per class, scores suppliers, surfaces stockout probability. The math is visible — every recommended quantity explains itself.
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
        <p className="marketing-footer-fine">© {new Date().getFullYear()} skubase</p>
      </footer>
    </div>
  );
}

'@ -Encoding UTF8
Write-Host 'Wrote: C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\blog\why-six-month-moving-average-overstocks-you\page.tsx'

Set-Content -Path 'C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\changelog\page.tsx' -Value @'
import Link from "next/link";

import { WaitlistForm } from "@/components/waitlist-form";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "Changelog — skubase",
  description: "Every release lands here. Shipping transparently is how we counter the ''roadmap frozen'' pattern the rest of the market has earned.",
  alternates: { canonical: "/changelog" },
  openGraph: { title: "Changelog — skubase", description: "Every release, on the record.", url: "/changelog", type: "website" },
};

type ChangelogEntry = { version: string; date: string; title: string; items: { type: "Added" | "Changed" | "Fixed" | "Shipped"; text: string }[]; };

const entries: ChangelogEntry[] = [
  { version: "v0.4.0", date: "2026-04-25", title: "Pre-launch readiness", items: [
    { type: "Shipped", text: "Waitlist signup form replaces direct dashboard access — skubase enters private beta." },
    { type: "Shipped", text: "Demo-mode banner on /dashboard so visitors know they''re seeing example data." },
    { type: "Shipped", text: "Privacy Policy and Terms of Service pages, including the written price-lock clause." },
    { type: "Shipped", text: "Public blog at /blog with first two posts (Stocky alternatives, why moving averages overstock)." },
    { type: "Shipped", text: "Stocky and ShipStation CSV importers with sample test data." }
  ]},
  { version: "v0.3.0", date: "2026-04-24", title: "Strategic positioning release", items: [
    { type: "Shipped", text: "Public marketing surface: landing page, pricing, about, changelog." },
    { type: "Shipped", text: "Migration landers for Stocky (Aug 31, 2026) and Genie (Aug 31, 2025)." },
    { type: "Shipped", text: "Transparent pricing with a written price-lock clause in TOS." },
    { type: "Shipped", text: "Forecast explainability: every recommended quantity explains itself." },
    { type: "Changed", text: "Brand renamed from Inventory Command to skubase." },
    { type: "Added", text: "Alert rules persisted to database — they survive restarts." }
  ]},
  { version: "v0.2.0", date: "2026-04-23", title: "Intelligence surface", items: [
    { type: "Shipped", text: "Holt double-exponential smoothing with weekly seasonality and stockout probability." },
    { type: "Shipped", text: "ABC × XYZ classification and scorecards." },
    { type: "Shipped", text: "Service-level-segmented safety stock, ROP, and EOQ." },
    { type: "Shipped", text: "Supplier scorecards and tiering." },
    { type: "Shipped", text: "Bundle / kit bottleneck analysis." },
    { type: "Shipped", text: "Multi-location transfer recommendations." },
    { type: "Shipped", text: "Dead-stock liquidation plans." },
    { type: "Shipped", text: "Alert rule engine: email, SMS, Slack, webhook." }
  ]},
  { version: "v0.1.0", date: "2026-03-12", title: "Mock-data MVP and action feed", items: [
    { type: "Shipped", text: "Backend action engine with urgent / optimize / dead outputs." },
    { type: "Shipped", text: "Lead-time hierarchy with safety buffer." },
    { type: "Shipped", text: "Frontend homepage connected to live /actions." }
  ]}
];

const typeStyle: Record<string, string> = {
  Shipped: "changelog-tag changelog-tag-shipped",
  Added: "changelog-tag changelog-tag-added",
  Changed: "changelog-tag changelog-tag-changed",
  Fixed: "changelog-tag changelog-tag-fixed"
};

export default function ChangelogPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero">
        <p className="marketing-eyebrow">Changelog</p>
        <h1 className="marketing-hero-title">Every release, on the record.</h1>
        <p className="marketing-hero-sub">
          We ship transparently so you never have to wonder whether skubase is still being built.
        </p>
      </section>

      <section className="changelog-list">
        {entries.map((entry) => (
          <article key={entry.version} className="changelog-entry">
            <header className="changelog-entry-head">
              <div>
                <p className="changelog-entry-version">{entry.version}</p>
                <h2 className="changelog-entry-title">{entry.title}</h2>
              </div>
              <time className="changelog-entry-date" dateTime={entry.date}>{entry.date}</time>
            </header>
            <ul className="changelog-entry-items">
              {entry.items.map((item, idx) => (
                <li key={idx} className="changelog-entry-item">
                  <span className={typeStyle[item.type]}>{item.type}</span>
                  <span>{item.text}</span>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </section>

      <section className="marketing-section marketing-cta-section">
        <p className="marketing-section-kicker">Get early access</p>
        <h2 className="marketing-section-title">Shipping a public changelog because we plan to keep doing it.</h2>
        <p className="marketing-section-sub">
          Drop your email — we&apos;ll send your invite when paid plans launch.
        </p>
        <WaitlistForm source="changelog" ctaLabel="Get early access" />
      </section>

      <footer className="marketing-footer">
        <div className="marketing-footer-brand">
          <span className="marketing-brand-mark">sb</span>
          <span>skubase</span>
        </div>
        <div className="marketing-footer-links">
          <Link href="/">Home</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/about">About</Link>
          <Link href="/blog">Blog</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">© {new Date().getFullYear()} skubase</p>
      </footer>
    </div>
  );
}

'@ -Encoding UTF8
Write-Host 'Wrote: C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\changelog\page.tsx'

Set-Content -Path 'C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\page.tsx' -Value @'
import Link from "next/link";

import { HeroCta } from "@/components/hero-cta";
import { WaitlistForm } from "@/components/waitlist-form";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "skubase — The Shopify inventory tool that tells you what to do first",
  description:
    "Forecast 90 days. Rank every SKU. Score every supplier. Recover cash from dead stock. Shopify-first, founder-led, price-locked."
};

const pillars = [
  { kicker: "Forecasting", title: "Stockout probability, not stockout guesswork.", body: "Holt double-exponential smoothing with weekly seasonality and a real probability of stockout on every SKU — not a moving average with a guess on top.", href: "/forecast" },
  { kicker: "Suppliers", title: "Vendors you can measure.", body: "On-time delivery, fill rate, lead-time stability, and preferred / acceptable / at-risk tiering. 23 of the 25 tools we studied still treat vendors as contact records.", href: "/suppliers" },
  { kicker: "Liquidation", title: "Cash recovery on stale inventory.", body: "Every dead-stock SKU comes with a concrete plan: markdown, bundle, wholesale, or write-off — with the dollar impact attached. 24 of 25 competitors surface aged stock and stop.", href: "/liquidation" },
  { kicker: "Bundles", title: "Bundles that don''t lose components.", body: "Kits decompose at reorder time, so you never place a PO that leaves a component short. Bundle bottlenecks are called out on the dashboard.", href: "/bundles" },
  { kicker: "Dashboard", title: "What should I do today?", body: "An action-ranked queue — urgent, optimize, dead — instead of a wall of dashboards. Rank the list, work it from the top.", href: "/dashboard" },
  { kicker: "Alerts", title: "Alerts that reach you where you work.", body: "Email, SMS, Slack, and webhooks driven by a real rule engine. No ''email only'' limitation like the rest of the market.", href: "/alerts" }
];

const migrationCards = [
  { eyebrow: "Leaving Stocky?", date: "Shopify Stocky ends Aug 31, 2026", title: "Goodbye Stocky, hello skubase.", body: "Shopify sunset a tool thousands of POS Pro merchants depended on. We built the replacement you actually wanted: forecasting, supplier scorecards, and dead-stock plans in one product.", cta: "See the migration path", href: "/goodbye-stocky", tone: "urgent" },
  { eyebrow: "Forecasting in a spreadsheet?", date: "ShipStation export → Google Sheet → trailing average", title: "Better than your spreadsheet.", body: "If your reorder math is a 6-month moving average in a Google Sheet, you''re tying up cash you don''t need to and missing every seasonal ramp. skubase fixes both — drop in your ShipStation export and see real velocity in minutes.", cta: "See why", href: "/vs-spreadsheet", tone: "steady" },
  { eyebrow: "Leaving Genie?", date: "Genie closed Aug 31, 2025", title: "Genie is gone. skubase is the upgrade.", body: "Genie merchants loved simple. We kept the simple and added the math — forecasting, supplier metrics, and a real reorder engine.", cta: "See the migration path", href: "/goodbye-genie", tone: "steady" }
];

const positioning = [
  { title: "Independent. Founder-led.", body: "Eight of the tools you evaluate have been acquired by a parent that raised prices, slowed the roadmap, or broke support. skubase is structurally outside that pattern." },
  { title: "Shopify-first today. Multi-channel coming.", body: "Our deepest integration is Shopify. ShipStation imports already cover Amazon, eBay, and Walmart shipment history. Native Amazon and eBay writes are on the roadmap; until then, we replace the forecasting layer alongside whatever channel-sync tool you use." },
  { title: "Math you can see.", body: "Every recommended quantity explains itself — trailing demand, seasonality factor, service level, stockout probability. Explainability is a feature." },
  { title: "Fair pricing. Locked pricing.", body: "We publish our tiers. We commit in writing that renewals do not raise the price on your plan. We mean it." }
];

export default function HomePage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero">
        <p className="marketing-eyebrow">Inventory decisions, made in order.</p>
        <h1 className="marketing-hero-title">The Shopify inventory tool that tells you what to do first.</h1>
        <p className="marketing-hero-sub">
          Forecast the next 90 days, rank every SKU, score every supplier, and recover cash from dead stock — in one Shopify-first product, at a price that doesn&apos;t triple at renewal.
        </p>
        <HeroCta source="home_hero" />
        <p className="marketing-hero-trust">
          We&apos;re in private beta. <Link href="/dashboard">See a live demo</Link> ·
          <strong> Prices locked at renewal</strong>
        </p>
      </section>

      <section className="marketing-migration" aria-label="Migration windows">
        {migrationCards.map((card) => (
          <article key={card.href} className={`migration-card migration-card-${card.tone}`}>
            <p className="migration-card-eyebrow">{card.eyebrow}</p>
            <p className="migration-card-date">{card.date}</p>
            <h2 className="migration-card-title">{card.title}</h2>
            <p className="migration-card-body">{card.body}</p>
            <Link href={card.href} className="migration-card-cta">{card.cta} →</Link>
          </article>
        ))}
      </section>

      <section className="marketing-section" id="pillars">
        <p className="marketing-section-kicker">What skubase does</p>
        <h2 className="marketing-section-title">Six things the rest of the market gets wrong.</h2>
        <p className="marketing-section-sub">
          We studied twenty-five inventory products. These are the six gaps that appeared over and over — and every one of them ships in skubase today.
        </p>
        <div className="pillar-grid">
          {pillars.map((p) => (
            <article key={p.href} className="pillar-card">
              <p className="pillar-card-kicker">{p.kicker}</p>
              <h3 className="pillar-card-title">{p.title}</h3>
              <p className="pillar-card-body">{p.body}</p>
              <Link href={p.href} className="pillar-card-link">See in demo →</Link>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-section-alt">
        <p className="marketing-section-kicker">Positioning</p>
        <h2 className="marketing-section-title">Why the rest of the market is the way it is — and why skubase isn&apos;t.</h2>
        <div className="positioning-grid">
          {positioning.map((p) => (
            <article key={p.title} className="positioning-card">
              <h3 className="positioning-card-title">{p.title}</h3>
              <p className="positioning-card-body">{p.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-cta-section">
        <h2 className="marketing-section-title">See what your next reorder should be.</h2>
        <p className="marketing-section-sub">
          Get on the list and we&apos;ll send your invite when paid plans launch. In the meantime, the demo is live.
        </p>
        <WaitlistForm source="home_footer" />
      </section>

      <footer className="marketing-footer">
        <div className="marketing-footer-brand">
          <span className="marketing-brand-mark">sb</span>
          <span>skubase</span>
        </div>
        <div className="marketing-footer-links">
          <Link href="/">Home</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/about">About</Link>
          <Link href="/blog">Blog</Link>
          <Link href="/changelog">Changelog</Link>
          <Link href="/goodbye-stocky">Stocky migration</Link>
          <Link href="/goodbye-genie">Genie migration</Link>
          <Link href="/vs-spreadsheet">vs. spreadsheet</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">
          © {new Date().getFullYear()} skubase · Independent · Founder-led · Prices locked at renewal
        </p>
      </footer>
    </div>
  );
}

'@ -Encoding UTF8
Write-Host 'Wrote: C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\page.tsx'

Set-Content -Path 'C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\pricing\page.tsx' -Value @'
import Link from "next/link";

import { PricingTable } from "@/components/pricing-table";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "Pricing — skubase",
  description: "Three published tiers. No quote-only pricing. A written price-lock clause that renewals cannot raise the rate on your plan.",
  alternates: { canonical: "/pricing" },
  openGraph: {
    title: "Pricing — skubase",
    description: "Three published tiers ($49/$149/$349) with a written price-lock pledge. Pay annually, save 15%.",
    url: "/pricing",
    type: "website",
  },
};

const FAQ_LD = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: [
    { "@type": "Question", name: "Do you raise prices at renewal?", acceptedAnswer: { "@type": "Answer", text: "No. Every plan has a written price-lock clause in the terms of service: we will not raise the monthly or annual rate on a plan you are already subscribed to." } },
    { "@type": "Question", name: "Is there a free tier?", acceptedAnswer: { "@type": "Answer", text: "Every plan starts with a 14-day free trial, no credit card required. After the trial the Starter plan is $49/mo." } },
    { "@type": "Question", name: "How long does setup take?", acceptedAnswer: { "@type": "Answer", text: "Most merchants see their first ranked action in under ten minutes. We do not require a paid implementation partner." } },
    { "@type": "Question", name: "Can I pay annually?", acceptedAnswer: { "@type": "Answer", text: "Yes — pay annually and save 15%. Annual customers also get a contractual price lock on the annual rate." } },
  ],
};

const faqs = [
  { q: "Do you raise prices at renewal?", a: "No. Every plan has a written price-lock clause in the terms of service: we will not raise the monthly or annual rate on a plan you are already subscribed to for as long as you maintain the subscription." },
  { q: "What happens if I exceed my SKU or location limit?", a: "We notify you by email, the app shows a soft banner, and you get thirty days to decide whether to upgrade or prune. We will never silently auto-upgrade your plan." },
  { q: "Is there a free tier?", a: "Every plan starts with a 14-day free trial, no credit card required. After the trial the Starter plan is $49/mo." },
  { q: "How long does setup take?", a: "Most merchants see their first ranked action in under ten minutes. We do not require a paid implementation partner." },
  { q: "Can I pay annually?", a: "Yes — pay annually and save 15%. Annual customers also get a contractual price lock on the annual rate." },
  { q: "How do you compare to Stocky / Inventory Planner / Cin7?", a: "Compared with Stocky we add real forecasting, supplier scorecards, and dead-stock plans. Compared with Inventory Planner we publish our price and commit to not raising it. Compared with Cin7 we publish our price and do not require a 6-month implementation." }
];

export default function PricingPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero">
        <p className="marketing-eyebrow">Pricing</p>
        <h1 className="marketing-hero-title">Three tiers. Published. Locked.</h1>
        <p className="marketing-hero-sub">
          We publish our prices on this page because the rest of the market hides them behind a sales call &mdash; and raises them at renewal. We commit in writing that renewals do not raise the rate on your plan.
        </p>
      </section>

      <PricingTable />

      <section className="pricing-lock">
        <div className="pricing-lock-card">
          <p className="pricing-lock-kicker">The skubase price-lock pledge</p>
          <h2 className="pricing-lock-title">Your rate will not go up at renewal.</h2>
          <p className="pricing-lock-body">
            We built this product because the inventory market is full of tools whose prices triple at renewal after an acquisition. Inventory Planner users reported roughly a 3&times; price hike after Sage. Linnworks users reported a 681% hike after a PE rollup. We are not doing that to you.
          </p>
          <p className="pricing-lock-body">
            The specific commitment, which appears in the <Link href="/terms">terms of service</Link>: once you start a subscription at a published price, that price does not increase for as long as you maintain the subscription.
          </p>
        </div>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">FAQ</p>
        <h2 className="marketing-section-title">The questions we hear the most.</h2>
        <div className="faq-grid">
          {faqs.map((f) => (
            <article key={f.q} className="faq-card">
              <h3 className="faq-card-q">{f.q}</h3>
              <p className="faq-card-a">{f.a}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="marketing-footer">
        <div className="marketing-footer-brand">
          <span className="marketing-brand-mark">sb</span>
          <span>skubase</span>
        </div>
        <div className="marketing-footer-links">
          <Link href="/">Home</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/about">About</Link>
          <Link href="/blog">Blog</Link>
          <Link href="/changelog">Changelog</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">© {new Date().getFullYear()} skubase · Prices locked at renewal</p>
      </footer>

      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(FAQ_LD) }} />
    </div>
  );
}

'@ -Encoding UTF8
Write-Host 'Wrote: C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\pricing\page.tsx'

Set-Content -Path 'C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\goodbye-stocky\page.tsx' -Value @'
import Link from "next/link";

import { WaitlistForm } from "@/components/waitlist-form";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "Goodbye Stocky, hello skubase — skubase",
  description: "Shopify Stocky ends August 31, 2026. skubase is the Shopify-native replacement.",
  alternates: { canonical: "/goodbye-stocky" },
  keywords: ["Stocky alternative", "Stocky replacement", "Stocky sunset"],
  openGraph: { title: "Goodbye Stocky, hello skubase", description: "Shopify Stocky ends August 31, 2026.", url: "/goodbye-stocky", type: "website" },
};

const compareRows = [
  { capability: "Forecasting", stocky: "Trailing averages.", skubase: "Holt double-exponential with weekly seasonality and stockout probability." },
  { capability: "Supplier scorecards", stocky: "Vendors are free-text.", skubase: "On-time delivery, fill rate, lead-time stability, tiering." },
  { capability: "Dead-stock plans", stocky: "Aged-stock flag.", skubase: "Markdown / bundle / wholesale / write-off plans." },
  { capability: "Reorder math", stocky: "Manual reorder point.", skubase: "Service-level-segmented safety stock + ROP + EOQ." },
  { capability: "Alerts", stocky: "Basic.", skubase: "Rule engine for email, SMS, Slack, webhooks." },
  { capability: "Pricing", stocky: "POS Pro $89/mo.", skubase: "Published from $49/mo. No POS Pro requirement." },
  { capability: "Future", stocky: "Ending August 31, 2026.", skubase: "Independent, founder-led, public changelog." }
];

const steps = [
  { number: "1", title: "Get on the early-access list", body: "Drop your email and Shopify domain. We''ll send your invite when paid plans launch — well before August." },
  { number: "2", title: "Bring your Stocky data", body: "Export your Stocky Inventory On Hand and Vendor List. Our importer maps them in one step." },
  { number: "3", title: "See your first ranked action", body: "Under ten minutes, no consultant. Urgent / optimize / dead — work the queue from the top." },
  { number: "4", title: "Run side-by-side through August", body: "Use Stocky and skubase together. We don''t charge for the migration window." }
];

export default function GoodbyeStockyPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero marketing-hero-migration">
        <p className="marketing-eyebrow">Stocky sunset · August 31, 2026</p>
        <h1 className="marketing-hero-title">Goodbye Stocky. Hello skubase.</h1>
        <p className="marketing-hero-sub">
          Shopify is ending Stocky on August 31, 2026. We built the replacement — real forecasting, supplier scorecards, dead-stock plans, Shopify-native, no POS Pro requirement.
        </p>
        <WaitlistForm source="goodbye_stocky_hero" ctaLabel="Get early access" />
        <p className="marketing-hero-trust">
          Free during the first 30 days of migration · <strong>Prices locked at renewal</strong>
        </p>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">Side by side</p>
        <h2 className="marketing-section-title">What you had in Stocky, and what you get in skubase.</h2>
        <div className="compare-table-wrapper">
          <table className="compare-table">
            <thead><tr><th>Capability</th><th>Stocky</th><th>skubase</th></tr></thead>
            <tbody>
              {compareRows.map((row) => (
                <tr key={row.capability}>
                  <td className="compare-table-label">{row.capability}</td>
                  <td className="compare-table-old">{row.stocky}</td>
                  <td className="compare-table-new">{row.skubase}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="marketing-section marketing-section-alt">
        <p className="marketing-section-kicker">Migration path</p>
        <h2 className="marketing-section-title">Four steps. No consultant.</h2>
        <div className="migration-steps">
          {steps.map((s) => (
            <article key={s.number} className="migration-step">
              <span className="migration-step-number">{s.number}</span>
              <div>
                <h3 className="migration-step-title">{s.title}</h3>
                <p className="migration-step-body">{s.body}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-cta-section">
        <h2 className="marketing-section-title">Get a head start on August.</h2>
        <p className="marketing-section-sub">Migrating early means you don&apos;t have to rush in July.</p>
        <WaitlistForm source="goodbye_stocky_footer" ctaLabel="Get early access" />
      </section>

      <footer className="marketing-footer">
        <div className="marketing-footer-brand">
          <span className="marketing-brand-mark">sb</span>
          <span>skubase</span>
        </div>
        <div className="marketing-footer-links">
          <Link href="/">Home</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/about">About</Link>
          <Link href="/goodbye-stocky">Stocky migration</Link>
          <Link href="/goodbye-genie">Genie migration</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">© {new Date().getFullYear()} skubase · Prices locked at renewal</p>
      </footer>
    </div>
  );
}

'@ -Encoding UTF8
Write-Host 'Wrote: C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\goodbye-stocky\page.tsx'

Set-Content -Path 'C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\goodbye-genie\page.tsx' -Value @'
import Link from "next/link";

import { WaitlistForm } from "@/components/waitlist-form";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "Goodbye Genie, hello skubase — skubase",
  description: "Genie closed August 31, 2025. skubase kept the simple Shopify-native experience and added the math.",
  alternates: { canonical: "/goodbye-genie" },
  keywords: ["Genie alternative", "Genie replacement", "Genie shutdown"],
  openGraph: { title: "Goodbye Genie, hello skubase", description: "Genie closed Aug 31, 2025. skubase is the upgrade.", url: "/goodbye-genie", type: "website" },
};

const reasons = [
  { title: "Shopify-native simplicity, kept.", body: "Genie''s appeal was that it felt like a Shopify app, not an ERP bolt-on. skubase is built the same way." },
  { title: "The math, added.", body: "Genie merchants told reviewers the forecasting felt basic. skubase ships Holt double-exponential smoothing with weekly seasonality." },
  { title: "Suppliers, measured.", body: "Genie treated vendors as contacts. skubase scores them: on-time delivery, fill rate, lead-time stability, tiering." },
  { title: "Dead stock, acted on.", body: "Genie surfaced aged stock. skubase proposes a plan: markdown, bundle, wholesale, or write-off." }
];

const steps = [
  { number: "1", title: "Get on the early-access list", body: "Drop your email. We''ll send your invite when we open up." },
  { number: "2", title: "Bring your Genie CSV", body: "If you exported your Genie data before the sunset, our importer maps vendors and lead-time settings." },
  { number: "3", title: "See your first ranked action", body: "Under ten minutes, no consultant. The dashboard prioritizes urgent reorders." }
];

export default function GoodbyeGeniePage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero marketing-hero-migration">
        <p className="marketing-eyebrow">Genie closed August 31, 2025</p>
        <h1 className="marketing-hero-title">Genie is gone. skubase is the upgrade.</h1>
        <p className="marketing-hero-sub">
          Genie merchants loved simple. We kept the simple — and added the math, the supplier scorecards, and the dead-stock plans Genie never shipped.
        </p>
        <WaitlistForm source="goodbye_genie_hero" ctaLabel="Get early access" />
        <p className="marketing-hero-trust">
          Free 30-day trial · No credit card · <strong>Prices locked at renewal</strong>
        </p>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">What changes for you</p>
        <h2 className="marketing-section-title">Everything you liked, and four things Genie didn&apos;t do.</h2>
        <div className="beliefs-grid">
          {reasons.map((r) => (
            <article key={r.title} className="belief-card">
              <h3 className="belief-card-title">{r.title}</h3>
              <p className="belief-card-body">{r.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-section-alt">
        <p className="marketing-section-kicker">Migration path</p>
        <h2 className="marketing-section-title">Three steps.</h2>
        <div className="migration-steps">
          {steps.map((s) => (
            <article key={s.number} className="migration-step">
              <span className="migration-step-number">{s.number}</span>
              <div>
                <h3 className="migration-step-title">{s.title}</h3>
                <p className="migration-step-body">{s.body}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-cta-section">
        <h2 className="marketing-section-title">Stop improvising.</h2>
        <p className="marketing-section-sub">The CSV exports and spreadsheets were good under pressure. skubase is the permanent replacement.</p>
        <WaitlistForm source="goodbye_genie_footer" ctaLabel="Get early access" />
      </section>

      <footer className="marketing-footer">
        <div className="marketing-footer-brand">
          <span className="marketing-brand-mark">sb</span>
          <span>skubase</span>
        </div>
        <div className="marketing-footer-links">
          <Link href="/">Home</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/about">About</Link>
          <Link href="/goodbye-stocky">Stocky migration</Link>
          <Link href="/goodbye-genie">Genie migration</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">© {new Date().getFullYear()} skubase · Prices locked at renewal</p>
      </footer>
    </div>
  );
}

'@ -Encoding UTF8
Write-Host 'Wrote: C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\goodbye-genie\page.tsx'

Set-Content -Path 'C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\vs-spreadsheet\page.tsx' -Value @'
import Link from "next/link";

import { WaitlistForm } from "@/components/waitlist-form";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "Better than your spreadsheet — skubase",
  description: "If your forecasting lives in a Google Sheet with a trailing 6-month average, you''re tying up cash you don''t need to. skubase fixes that in ten minutes.",
  alternates: { canonical: "/vs-spreadsheet" },
  openGraph: {
    title: "Your spreadsheet is overstocking you — skubase",
    description: "ShipStation export → Google Sheet → 6-month moving average → reorder. That math is costing you money.",
    url: "/vs-spreadsheet",
    type: "website",
  },
};

const reasons = [
  { title: "A 6-month rule of thumb is a tax on your working capital.", body: "Holding 6 months of cover for an A-item with steady demand is statistically wasteful — that''s a 95th-percentile-plus stockout rule applied to SKUs that only need 30–60 days. The cash gap is real, and it compounds across every reorder cycle." },
  { title: "Trailing averages miss seasonality and trend.", body: "A 6-month moving average is half-blind on every Q4 ramp. skubase fits a Holt double-exponential model with a weekly seasonality factor, so a back-to-school SKU isn''t reordered like a steady-state one." },
  { title: "All SKUs are not equal.", body: "Your A-items deserve a 99% service level; your C-items don''t. skubase segments by ABC × XYZ and sets safety stock per class — the math the spreadsheet can''t do without becoming a part-time job." },
  { title: "Your suppliers are unmeasured.", body: "If your spreadsheet doesn''t track which vendors miss promised lead times, you''re carrying their failures as your stockouts. skubase scores every vendor on on-time, fill rate, and lead-time stability." },
  { title: "Dead stock is a cash recovery problem your sheet ignores.", body: "The Sheet shows you what you have. It does not propose a markdown plan, a bundle, a wholesale list, or a write-off. skubase does — with the dollar impact attached." }
];

const compare = [
  { metric: "Forecasting model", sheet: "Trailing 6-month moving average", skubase: "Holt double-exponential + weekly seasonality + stockout probability" },
  { metric: "Safety stock", sheet: "Same buffer for every SKU", skubase: "Service-level segmented by ABC × XYZ class" },
  { metric: "Reorder trigger", sheet: "Cover < 6 months", skubase: "Days-until-stockout < lead time + safety, ranked by $ impact" },
  { metric: "Supplier accuracy", sheet: "Not tracked", skubase: "On-time %, fill rate, lead-time stability, tiered" },
  { metric: "Bundle/kit logic", sheet: "Manual decomposition", skubase: "Auto-decomposes at reorder time" },
  { metric: "Dead stock action", sheet: "None", skubase: "Markdown / bundle / wholesale / write-off plans" },
  { metric: "Time to update", sheet: "30–60 minutes per week", skubase: "Zero — recomputes when shipments land" },
  { metric: "Auditability", sheet: "Whoever last touched it", skubase: "Every recommended quantity explains itself" }
];

const steps = [
  { n: "1", title: "Drop in your ShipStation export", body: "We accept the standard Orders or Shipments CSV — SKU, quantity, ship date are all we need. ShipStation aggregates Shopify, Amazon, eBay, Walmart, and most other channels, so the import covers everywhere you sell." },
  { n: "2", title: "See your real velocity", body: "Per-SKU 30 / 90 / 180-day shipped units. The number you''ve been eyeballing in the spreadsheet, computed correctly." },
  { n: "3", title: "Get ranked actions", body: "Skubase ranks every SKU into urgent reorders, overstock to draw down, and dead stock to liquidate. Work the queue; close the spreadsheet." }
];

export default function VsSpreadsheetPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero marketing-hero-migration">
        <p className="marketing-eyebrow">vs. your forecasting spreadsheet</p>
        <h1 className="marketing-hero-title">Your reorder math is costing you money.</h1>
        <p className="marketing-hero-sub">
          If your forecasting lives in a Google Sheet — ShipStation export pasted in, six-month trailing average computed, reorder when cover drops below six months — you&apos;re carrying more inventory than you need to and you&apos;re still missing seasonality. skubase fixes both, in under ten minutes.
        </p>
        <WaitlistForm source="vs_spreadsheet_hero" ctaLabel="Get early access" />
        <p className="marketing-hero-trust">
          14-day free trial · No credit card · <strong>Prices locked at renewal</strong>
        </p>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">Why the spreadsheet is wrong</p>
        <h2 className="marketing-section-title">Five things your sheet can&apos;t do — and skubase does by default.</h2>
        <div className="beliefs-grid">
          {reasons.map((r) => (
            <article key={r.title} className="belief-card">
              <h3 className="belief-card-title">{r.title}</h3>
              <p className="belief-card-body">{r.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-section-alt">
        <p className="marketing-section-kicker">Side by side</p>
        <h2 className="marketing-section-title">The math, made visible.</h2>
        <div className="compare-table-wrapper">
          <table className="compare-table">
            <thead>
              <tr><th>Metric</th><th>Your spreadsheet</th><th>skubase</th></tr>
            </thead>
            <tbody>
              {compare.map((row) => (
                <tr key={row.metric}>
                  <td className="compare-table-label">{row.metric}</td>
                  <td className="compare-table-old">{row.sheet}</td>
                  <td className="compare-table-new">{row.skubase}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">How it works</p>
        <h2 className="marketing-section-title">Three steps. No consultant.</h2>
        <div className="migration-steps">
          {steps.map((s) => (
            <article key={s.n} className="migration-step">
              <span className="migration-step-number">{s.n}</span>
              <div>
                <h3 className="migration-step-title">{s.title}</h3>
                <p className="migration-step-body">{s.body}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-cta-section">
        <h2 className="marketing-section-title">Stop reordering by averages. Start reordering by math.</h2>
        <p className="marketing-section-sub">
          The spreadsheet was a heroic fix. skubase is the permanent one.
        </p>
        <WaitlistForm source="vs_spreadsheet_footer" ctaLabel="Get early access" />
      </section>

      <footer className="marketing-footer">
        <div className="marketing-footer-brand">
          <span className="marketing-brand-mark">sb</span>
          <span>skubase</span>
        </div>
        <div className="marketing-footer-links">
          <Link href="/">Home</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/about">About</Link>
          <Link href="/blog">Blog</Link>
          <Link href="/vs-spreadsheet">vs. spreadsheet</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">© {new Date().getFullYear()} skubase · Prices locked at renewal</p>
      </footer>
    </div>
  );
}

'@ -Encoding UTF8
Write-Host 'Wrote: C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\vs-spreadsheet\page.tsx'

Set-Content -Path 'C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\privacy\page.tsx' -Value @'
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

'@ -Encoding UTF8
Write-Host 'Wrote: C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\privacy\page.tsx'

Set-Content -Path 'C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\terms\page.tsx' -Value @'
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
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">© {new Date().getFullYear()} skubase</p>
      </footer>
    </div>
  );
}

'@ -Encoding UTF8
Write-Host 'Wrote: C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\terms\page.tsx'


# Commit and push
git add frontend/app/about/page.tsx frontend/app/blog/page.tsx 'frontend/app/blog/stocky-alternatives-2026/page.tsx' 'frontend/app/blog/why-six-month-moving-average-overstocks-you/page.tsx' frontend/app/changelog/page.tsx frontend/app/page.tsx frontend/app/pricing/page.tsx frontend/app/goodbye-stocky/page.tsx frontend/app/goodbye-genie/page.tsx frontend/app/vs-spreadsheet/page.tsx frontend/app/privacy/page.tsx frontend/app/terms/page.tsx
git commit -m "Fix truncated marketing pages caused by WSL cache bug during nav extraction"
git push origin HEAD
Write-Host 'DONE' -ForegroundColor Green
pause