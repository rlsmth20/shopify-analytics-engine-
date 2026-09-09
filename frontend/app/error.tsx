"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log to console; future: send to Sentry.
    console.error("Application error:", error);
  }, [error]);

  return (
    <div className="error-shell">
      <div className="error-card">
        <p className="error-eyebrow">500</p>
        <h1 className="error-title">Something went sideways.</h1>
        <p className="error-copy">
          Try again, or reload to get the latest version of Skubase. If it keeps
          happening, contact info@skubase.io.
        </p>
        <div className="error-actions">
          <button type="button" onClick={reset} className="button button-primary">
            Try again
          </button>
          <button type="button" onClick={() => window.location.reload()} className="button button-ghost">
            Reload latest version
          </button>
          <Link href="/" className="button button-ghost">Go home</Link>
        </div>
        {error.digest ? (
          <p className="error-digest">Reference: {error.digest}</p>
        ) : null}
      </div>
    </div>
  );
}
