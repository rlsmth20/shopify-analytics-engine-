import Link from "next/link";

/**
 * Shared marketing-site footer.
 *
 * Every public-facing page renders this so the link set and fine print stay
 * consistent — previously each page carried its own copy and they drifted.
 */
export function MarketingFooter() {
  return (
    <footer className="marketing-footer">
      <div className="marketing-footer-brand">
        <span className="marketing-brand-mark">sb</span>
        <span>skubase</span>
      </div>
      <div className="marketing-footer-links">
        <Link href="/">Home</Link>
        <Link href="/features">Features</Link>
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
        © {new Date().getFullYear()} skubase — Independent — Founder-led — Prices locked at renewal
      </p>
    </footer>
  );
}
