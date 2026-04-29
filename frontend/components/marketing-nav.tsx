import Link from "next/link";

/**
 * Shared marketing-site header nav.
 *
 * Used on every public-facing page so CTA buttons and nav links stay
 * consistent without copy-paste. To update nav links or CTAs, change
 * this file only.
 */
export function MarketingNav() {
  return (
    <header className="marketing-nav">
      <Link href="/" className="marketing-brand">
        <span className="marketing-brand-mark">sb</span>
        <span className="marketing-brand-name">skubase</span>
      </Link>
      <nav className="marketing-nav-links" aria-label="Primary">
        <Link href="/#pillars">Product</Link>
        <Link href="/pricing">Pricing</Link>
        <Link href="/about">About</Link>
        <Link href="/blog">Blog</Link>
        <Link href="/changelog">Changelog</Link>
      </nav>
      <div className="marketing-nav-ctas">
        <Link href="/dashboard?demo=1" className="button button-ghost button-sm">
          View demo
        </Link>
        <Link href="/login" className="marketing-link-subtle">
          Sign in
        </Link>
      </div>
    </header>
  );
}
