import Link from "next/link";
import { BLOG_POSTS, blogDate } from "@/lib/blog-posts";

import { WaitlistForm } from "@/components/waitlist-form";
import { MarketingNav } from "@/components/marketing-nav";
import { MarketingFooter } from "@/components/marketing-footer";

export const metadata = {
  title: "Shopify inventory guides - skubase",
  description: "Practical guides to Shopify inventory planning, Stocky migration, reorder decisions, and slow-moving stock.",
  alternates: { canonical: "/blog" },
  openGraph: { title: "skubase blog", description: "Shopify inventory, forecasting, and supplier intelligence.", url: "/blog", type: "website" },
};

const posts = Object.entries(BLOG_POSTS).map(([slug, post]) => ({ slug, ...post }));

export default function BlogIndex() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero">
        <p className="marketing-eyebrow">Blog</p>
        <h1 className="marketing-hero-title">Inventory, written carefully.</h1>
        <p className="marketing-hero-sub">
          Practical guides to choosing what to reorder, freeing up inventory cash, and planning your next steps after Stocky.
        </p>
      </section>

      <section className="blog-list">
        {posts.map((p) => (
          <article key={p.slug} className="blog-list-item">
            <p className="blog-list-meta">
              Updated <time dateTime={p.updatedAt}>{blogDate(p.updatedAt)}</time>
              <span> &middot; {p.category}</span>
            </p>
            <h2 className="blog-list-title">
              <Link href={`/blog/${p.slug}`}>{p.title}</Link>
            </h2>
            <p className="blog-list-desc">{p.description}</p>
            <Link href={`/blog/${p.slug}`} className="blog-list-link">Read post &rarr;</Link>
          </article>
        ))}
      </section>

      <section className="marketing-section marketing-cta-section">
        <h2 className="marketing-section-title">See what your inventory is telling you.</h2>
        <p className="marketing-section-sub">
          Try the free inventory health check with a few product figures, or start a 14-day trial with supported CSV imports. No credit card required.
        </p>
        <p className="marketing-section-sub"><Link href="/tools/inventory-health-check">Try the free inventory health check</Link> or <Link href="/dashboard?demo=1">explore the sample dashboard</Link>.</p>
        <WaitlistForm source="blog_index" ctaLabel="Start free trial" />
      </section>

      <MarketingFooter />
    </div>
  );
}
