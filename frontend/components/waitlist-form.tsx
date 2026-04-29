"use client";

import { useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type Props = {
  source: string;
  variant?: "primary" | "ghost" | "compact";
  ctaLabel?: string;
  successLabel?: string;
  className?: string;
};

export function WaitlistForm({
  source,
  variant = "primary",
  ctaLabel = "Start free trial",
  successLabel = "Check your email — we sent you a sign-in link.",
  className = "",
}: Props) {
  const [email, setEmail] = useState("");
  const [domain, setDomain] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!email.trim()) {
      setError("Please enter your email.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/auth/magic-link/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          shopify_domain: domain.trim() || null,
        }),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(body?.detail || `Request failed (${res.status}).`);
      }
      setSuccess(true);
      setEmail("");
      setDomain("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return (
      <div className={`waitlist-success ${className}`} role="status">
        <span className="waitlist-success-mark" aria-hidden>
          ✓
        </span>
        <span>{successLabel}</span>
      </div>
    );
  }

  return (
    <form
      className={`waitlist-form waitlist-form-${variant} ${className}`}
      onSubmit={handleSubmit}
    >
      <div className="waitlist-form-row">
        <input
          type="email"
          className="input-control waitlist-input"
          placeholder="you@yourshop.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={submitting}
          required
          aria-label="Email"
        />
        <input
          type="text"
          className="input-control waitlist-input"
          placeholder="yourshop.myshopify.com (optional)"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          disabled={submitting}
          aria-label="Shopify domain"
        />
        <button
          type="submit"
          className="button button-primary"
          disabled={submitting}
        >
          {submitting ? "Sending…" : ctaLabel}
        </button>
      </div>
      {error ? (
        <p className="waitlist-error" role="alert">
          {error}
        </p>
      ) : (
        <p className="waitlist-hint">
          14-day free trial. No card required. Prices locked at renewal.
        </p>
      )}
    </form>
  );
}
