"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import Link from "next/link";
import { useEffect, useState } from "react";

import { WaitlistForm } from "@/components/waitlist-form";

const API_BASE = APP_API_BASE_URL;

type Mode = "loading" | "anonymous" | "authed";

export function HeroCta({ source }: { source: string }) {
  const [mode, setMode] = useState<Mode>("loading");
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetch(`${API_BASE}/auth/me`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled) return;
        if (data && typeof data.email === "string") {
          setEmail(data.email);
          setMode("authed");
        } else {
          setMode("anonymous");
        }
      })
      .catch(() => {
        if (!cancelled) setMode("anonymous");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (mode === "loading") {
    // Reserve space so the hero doesn't jump.
    return <div style={{ minHeight: "92px" }} aria-hidden />;
  }

  if (mode === "authed") {
    return (
      <div className="hero-authed">
        <p className="hero-authed-greeting">
          Signed in as <strong>{email}</strong>
        </p>
        <div className="hero-authed-actions">
          <Link href="/dashboard" className="button button-primary button-lg">
            Open dashboard
          </Link>
          <Link href="/billing" className="button button-ghost button-lg">
            Billing
          </Link>
        </div>
      </div>
    );
  }

  return <WaitlistForm source={source} />;
}
