import Link from "next/link";

export const metadata = {
  title: "Page not found · skubase",
};

export default function NotFound() {
  return (
    <div className="error-shell">
      <div className="error-card">
        <p className="error-eyebrow">404</p>
        <h1 className="error-title">This page doesn&apos;t exist.</h1>
        <p className="error-copy">
          The link is broken, the page moved, or you typed it wrong. Either way, it&apos;s not here.
        </p>
        <div className="error-actions">
          <Link href="/" className="button button-primary">Go home</Link>
          <Link href="/dashboard?demo=1" className="button button-ghost">Open the demo</Link>
        </div>
      </div>
    </div>
  );
}
