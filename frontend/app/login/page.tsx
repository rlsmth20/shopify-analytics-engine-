"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    if (!email.trim()) {
      setError("Enter the email you used to join the skubase waitlist.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/auth/magic-link/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
        credentials: "include",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body?.detail || "We couldn't send the link right now. Try again in a moment.");
        return;
      }
      setSent(true);
    } catch {
      setError("Network error — check your connection and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <Link href="/" className="auth-brand">
          <span className="auth-brand-mark">sb</span>
          <span className="auth-brand-name">skubase</span>
        </Link>

        {sent ? (
          <div className="auth-success">
            <h1 className="auth-title">Check your email.</h1>
            <p className="auth-copy">
              We sent a sign-in link to <strong>{email}</strong>. The link
              works once and expires in 15 minutes.
            </p>
            <p className="auth-fine">
              Didn&apos;t arrive in 30 seconds? Check spam, then{" "}
              <button
                type="button"
                onClick={() => {
                  setSent(false);
                  setEmail("");
                }}
                className="auth-link-button"
              >
                try a different email
              </button>
              .
            </p>
          </div>
        ) : (
          <>
            <h1 className="auth-title">Sign in or create your workspace</h1>
            <p className="auth-copy">
              We&apos;ll email you a one-time sign-in link. No password. New
              email = new workspace, automatically.
            </p>
            <form onSubmit={handleSubmit} className="auth-form">
              <label className="auth-field">
                <span className="auth-field-label">Email</span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  autoFocus
                  className="auth-input"
                  placeholder="you@yourstore.com"
                />
              </label>
              {error ? <p className="auth-error">{error}</p> : null}
              <button
                type="submit"
                disabled={submitting}
                className="button button-primary button-full"
              >
                {submitting ? "Sending link..." : "Email me a sign-in link"}
              </button>
            </form>
            <p className="auth-fine">
              See <Link href="/pricing" className="auth-link">pricing</Link> ·{" "}
              <Link href="/" className="auth-link">back to home</Link> ·{" "}
              <Link href="/dashboard?demo=1" className="auth-link">view the demo →</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
