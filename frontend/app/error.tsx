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
          We&apos;ve logged the error. Try again in a moment — if it keeps
          happening, drop us a note at hello@slelfly.com.
        </p>
        <div className="error-actions">
          <button type="button" onClick={reset} className="button button-primary">
            Try again
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
