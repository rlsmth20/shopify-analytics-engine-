"use client";

import { useState } from "react";

import type { PlanKey } from "@/lib/plans";
import { authenticatedFetch, isEmbeddedShopifyContext } from "@/lib/shopify-embedded";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export function PricingButton({
  plan,
  label,
  variant = "ghost",
}: {
  plan: PlanKey;
  label: string;
  variant?: "primary" | "ghost";
}) {
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    setLoading(true);
    const embedded = isEmbeddedShopifyContext();
    const popup = embedded ? window.open("about:blank", "_blank") : null;
    if (popup) {
      popup.opener = null;
      popup.document.title = "Opening billing approval...";
    }

    try {
      const meRes = await authenticatedFetch(`${API_BASE}/auth/me`, {
        credentials: "include",
      }).catch(() => null);
      if (!meRes || !meRes.ok) {
        if (popup && !popup.closed) popup.close();
        window.location.href = `/login?next=${encodeURIComponent("/pricing")}`;
        return;
      }

      const billingRes = await authenticatedFetch(`${API_BASE}/billing/me`, {
        credentials: "include",
      }).catch(() => null);
      const billing = billingRes?.ok ? await billingRes.json().catch(() => null) : null;
      const endpoint =
        billing?.billing_provider === "shopify" || billing?.shopify_installed
          ? "/billing/shopify/subscribe"
          : "/billing/checkout";

      const res = await authenticatedFetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ plan }),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        if (popup && !popup.closed) popup.close();
        if (res.status === 503) {
          window.location.href = "/#waitlist";
          return;
        }
        alert(body?.detail || `Could not start billing approval (${res.status}).`);
        return;
      }
      if (body?.url) {
        if (embedded) {
          if (popup && !popup.closed) {
            popup.location.href = body.url;
          } else {
            window.open(body.url, "_blank", "noopener,noreferrer");
          }
        } else {
          window.location.href = body.url;
        }
      } else if (popup && !popup.closed) {
        popup.close();
      }
    } catch {
      if (popup && !popup.closed) popup.close();
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
      {loading ? "One moment..." : label}
    </button>
  );
}
