import Link from "next/link";

import { WaitlistForm } from "@/components/waitlist-form";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "Blog — skubase",
  description: "Posts about Shopify inventory, forecasting, supplier scoring, dead stock, and the rest of the math the spreadsheet can't do.",
  alternates: { canonical: "/blog" },
  openGraph: { title: "skubase blog", description: "Shopify inventory, forecasting, and supplier intelligence.", url: "/blog", type: "website" },
};

const posts = [
  { slug: "stocky-alternatives-2026", title: "Stocky alternatives for Shopify merchants in 2026", date: "2026-04-25", description: "Shopify is shutting down Stocky on August 31, 2026. Here are the realistic replacements.", minutes: 8 },
  { slug: "why-six-month-moving-average-overstocks-you", title: "Why a 6-month moving average is overstocking you", date: "2026-04-25", description: "If you reorder when cover drops below six months, you're carrying more inventory than you need to.", minutes: 7 },
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
          <Link href="/terms">Terms</Lin