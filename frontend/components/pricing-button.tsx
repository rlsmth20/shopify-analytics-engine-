"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type Plan =
  | "starter_monthly"
  | "growth_monthly"
  | "scale_monthly"
  | "starter_annual"
  | "growth_annual"
  | "scale_annual";

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
      // Check if user is already authenticated.
      const meRes = await fetch(`${API_BASE}/auth/me`, { credentials: "include" }).catch(() => null);
      if (!meRes || !meRes.ok) {
        // Not signed in — send to login. After magic-link sign-in the user
        // lands on /dashboard; they can return to /pricing and subscribe.
        window.location.href = `/login?next=${encodeURIComponent("/pricing")}`;
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
        if (res.status === 503) {
          // Billing not yet wired — fall back to the waitlist.
          window.location.href = "/#waitlist";
          return;
        }
        alert(body?.detail || `Could not start checkout (${res.status}).`);
        return;
      }
      if (body?.url) {
        window.location.href = body.url;
      }
    } catch {
      // Network error — fall back gracefully to login.
      window.location.href = `/login?next=${encodeURIComponent("/pricing")}`;
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
