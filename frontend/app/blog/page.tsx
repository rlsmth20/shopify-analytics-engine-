import Link from "next/link";

export const metadata = {
  title: "Blog — slelfly",
  description:
    "Posts about Shopify inventory, forecasting, supplier scoring, dead stock, and the rest of the math the spreadsheet can't do.",
  alternates: { canonical: "/blog" },
  openGraph: {
    title: "slelfly blog",
    description: "Shopify inventory, forecasting, and supplier intelligence — explained without jargon.",
    url: "/blog",
    type: "website",
  },
};

const posts = [
  {
    slug: "stocky-alternatives-2026",
    title: "Stocky alternatives for Shopify merchants in 2026",
    date: "2026-04-25",
    description:
      "Shopify is shutting down Stocky on August 31, 2026. Here are the realistic replacements, what each one is good and bad at, and a side-by-side feature comparison.",
    minutes: 8,
  },
  {
    slug: "why-six-month-moving-average-overstocks-you",
    title: "Why a 6-month moving average is overstocking you",
    date: "2026-04-25",
    description:
      "If you reorder when cover drops below six months, you're carrying more inventory than you need to and still missing every seasonal ramp. Here's the math.",
    minutes: 7,
  },
];

export default function BlogIndex() {
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
          <Link href="/login" className="marketing-link-subtle">
            Sign in
          </Link>
          <Link href="/dashboard" className="button button-primary">
            Open app
          </Link>
        </div>
      </header>

      <section className="marketing-hero">
        <p className="marketing-eyebrow">Blog</p>
        <h1 className="marketing-hero-title">Inventory, written carefully.</h1>
        <p className="marketing-hero-sub">
          Posts about forecasting, supplier scoring, dead stock, and the rest
          of the math the spreadsheet can&apos;t do — without the jargon.
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
            <Link href={`/blog/${p.slug}`} className="blog-list-link">
              Read post →
            </Link>
          </article>
        ))}
      </section>

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
          <Link href="/goodbye-stocky">Stocky migration</Link>
          <Link href="/vs-spreadsheet">vs. spreadsheet</Link>
          <Link href="/login">Sign in</Link>
        </div>
        <p className="marketing-footer-fine">
          © {new Date().getFullYear()} slelfly · Independent · Founder-led ·
          Prices locked at renewal
        </p>
      </footer>
    </div>
  );
}
