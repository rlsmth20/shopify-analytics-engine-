"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import Link from "next/link";
import { useEffect, useState } from "react";
import { loginDestination, loginError } from "@/lib/login";

const API_BASE = APP_API_BASE_URL;

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [returnTo, setReturnTo] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setReturnTo(loginDestination(params.get("return_to")));
  }, []);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    if (!email.trim()) {
      setError("Enter your email to sign in or start a free trial.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/auth/magic-link/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase(), return_to: returnTo }),
        credentials: "include",
        signal: AbortSignal.timeout(20_000),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(loginError(body));
        return;
      }
      setSent(true);
    } catch {
      setError("Network error - check your connection and try again.");
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
            <h1 className="auth-title">Check your inbox.</h1>
            <p className="auth-copy">
              We sent a sign-in link to <strong>{email}</strong>. Click it to
              continue - the link expires in 15 minutes.
            </p>
            <p className="auth-fine">
              Didn&apos;t arrive within 30 seconds? Check spam, then{" "}
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
            <h1 className="auth-title">Sign in to skubase</h1>
            <p className="auth-copy">
              Enter your email and we&apos;ll send you a one-click sign-in link.
              No password required.
            </p>

            <form onSubmit={handleSubmit} className="auth-form">
              <label className="auth-field">
                <span className="auth-field-label">Work email</span>
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
              {error ? <p className="auth-error" role="alert">{error}</p> : null}
              <button
                type="submit"
                disabled={submitting}
                className="button button-primary button-full"
              >
                {submitting ? "Sending link..." : "Send sign-in link"}
              </button>
            </form>

            <div className="auth-trial-callout">
              <p className="auth-trial-callout-title">New to skubase?</p>
              <ul className="auth-checklist">
                <li>Free 14-day trial - no credit card required</li>
                <li>Import Stocky inventory and ShipStation shipment CSVs</li>
                <li>Use current stock and sales history to review inventory risks</li>
              </ul>
              <p className="auth-fine">Skubase is in Shopify App Store review and is not listed yet. <a className="auth-link" href="mailto:info@skubase.io?subject=Skubase%20Shopify%20access">Contact us about Shopify access</a>, or start with CSV imports.</p>
              <p className="auth-fine">Plans from $29/mo after trial - Cancel any time</p>
            </div>

            <p className="auth-fine">
              <Link href="/dashboard?demo=1" className="auth-link">View demo first →</Link>
              {" · "}<Link href="/tools/inventory-health-check" className="auth-link">Try a free inventory health check</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
