"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import { useState } from "react";

import { useAuth } from "@/components/auth-guard";
import { SectionCard } from "@/components/section-card";
import { contactResponseError, isShopifyIdentityEmail } from "@/lib/contact";
import { authenticatedFetch } from "@/lib/shopify-embedded";

const API_BASE = APP_API_BASE_URL;

type ContactType = "bug" | "feedback" | "billing" | "general";

const TYPE_LABELS: Record<ContactType, string> = {
  bug: "Bug report",
  feedback: "Feature / feedback",
  billing: "Billing question",
  general: "General",
};

export default function FeedbackPage() {
  const { user } = useAuth();

  const [name, setName] = useState("");
  const [email, setEmail] = useState(
    user.id !== 0 && !isShopifyIdentityEmail(user.email) ? user.email : "",
  );
  const [type, setType] = useState<ContactType>("general");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (isShopifyIdentityEmail(email)) {
      setError("Enter an email address where you can receive a reply.");
      return;
    }
    setLoading(true);
    try {
      const res = await authenticatedFetch(`${API_BASE}/contact/submit`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), email: email.trim(), type, message }),
      });
      const body = await res.json().catch(() => null);
      const submissionError = contactResponseError(res.ok, body);
      if (submissionError) {
        setError(submissionError);
        return;
      }
      setSent(true);
    } catch {
      setError("Network error. Try emailing hello@skubase.io directly.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <SectionCard>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Support</p>
            <h2 className="section-title">Contact us</h2>
          </div>
        </div>

        {sent ? (
          <div style={{ padding: "24px 0" }}>
            <p
              className="section-copy"
              style={{ fontSize: "18px", fontWeight: 600, marginBottom: "8px" }}
            >
              Your message has been sent to support.
            </p>
            <p className="section-copy">
              We will use <strong>{email.trim()}</strong> to reply.
              You can also reach us directly at{" "}
              <a href="mailto:hello@skubase.io" style={{ color: "inherit" }}>
                hello@skubase.io
              </a>
              .
            </p>
            <button
              type="button"
              className="button button-ghost"
              style={{ marginTop: "20px" }}
              onClick={() => {
                setSent(false);
                setMessage("");
              }}
            >
              Send another message
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="auth-form" style={{ maxWidth: "560px" }}>
            <label className="auth-field">
              <span className="auth-field-label">Your name</span>
              <input
                type="text"
                className="auth-input"
                placeholder="Rainer Smith"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                disabled={loading}
              />
            </label>

            <label className="auth-field">
              <span className="auth-field-label">Reply email</span>
              <input
                type="email"
                className="auth-input"
                placeholder="you@yourstore.com"
                autoComplete="email"
                maxLength={320}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={loading}
              />
              <span className="section-copy">Use an inbox you can access so support can reply.</span>
            </label>

            <label className="auth-field">
              <span className="auth-field-label">Type</span>
              <select
                className="auth-input"
                value={type}
                onChange={(e) => setType(e.target.value as ContactType)}
                disabled={loading}
                style={{ cursor: "pointer" }}
              >
                {(Object.entries(TYPE_LABELS) as [ContactType, string][]).map(
                  ([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  )
                )}
              </select>
            </label>

            <label className="auth-field">
              <span className="auth-field-label">Message</span>
              <textarea
                className="auth-input"
                placeholder="Describe the bug, what you expected, and what actually happened..."
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                required
                minLength={10}
                rows={6}
                disabled={loading}
                style={{ resize: "vertical", fontFamily: "inherit", fontSize: "inherit" }}
              />
            </label>

            {error ? <p className="auth-error" role="alert">{error}</p> : null}

            <button type="submit" className="button button-primary" disabled={loading}>
              {loading ? "Sending..." : "Send message"}
            </button>

            <p
              className="section-copy"
              style={{ marginTop: "12px", fontSize: "13px", color: "var(--text-muted, #64748b)" }}
            >
              Or email us directly at{" "}
              <a href="mailto:hello@skubase.io" style={{ color: "inherit" }}>
                hello@skubase.io
              </a>
              .
            </p>
          </form>
        )}
      </SectionCard>
    </div>
  );
}
