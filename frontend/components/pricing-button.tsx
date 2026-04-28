"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type Plan = "starter_monthly" | "growth_monthly" | "scale_monthly";

export function PricingButton({
  plan,
  label,
  variant = "ghost",
}: {
  plan: Plan;
  label: string;
  variant?: "primary" | "ghost";
}) {
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    setLoading(true);
    try {
      // First confirm the user is authenticated. If not, scroll to the
      // waitlist anchor — they'll join the list rather than see a 401.
      const meRes = await fetch(`${API_BASE}/auth/me`, { credentials: "include" });
      if (!meRes.ok) {
        const el = document.getElementById("waitlist");
        if (el) el.scrollIntoView({ behavior: "smooth" });
        return;
      }

      // Authenticated — start a Checkout session and redirect.
      const res = await fetch(`${API_BASE}/billing/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ plan }),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        // 503 means Stripe not configured yet — fall back to waitlist.
        if (res.status === 503) {
          const el = document.getElementById("waitlist");
          if (el) el.scrollIntoView({ behavior: "smooth" });
          return;
        }
        alert(body?.detail || `Could not start checkout (${res.status}).`);
        return;
      }
      if (body?.url) {
        window.location.href = body.url;
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={loading}
      className={`button ${variant === "primary" ? "button-primary" : "button-ghost"} button-full`}
    >
      {loading ? "One moment…" : label}
    </button>
  );
}
