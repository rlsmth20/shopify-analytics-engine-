"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import Link from "next/link";
import { useEffect, useState } from "react";

const API_BASE = APP_API_BASE_URL;

type AuthState = "loading" | "signed-out" | "signed-in";

/**
 * Shared marketing-site header nav.
 *
 * Used on every public-facing page so CTA buttons and nav links stay
 * consistent without copy-paste. To update nav links or CTAs, change
 * this file only.
 */
export function MarketingNav() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [authState, setAuthState] = useState<AuthState>("loading");

  useEffect(() => {
    let cancelled = false;
    void fetch(`${API_BASE}/auth/me`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled) return;
        setAuthState(data?.email ? "signed-in" : "signed-out");
      })
      .catch(() => {
        if (!cancelled) setAuthState("signed-out");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <header className="marketing-nav" data-menu-open={menuOpen} onKeyDown={event => { if (event.key === "Escape") { setMenuOpen(false); event.currentTarget.querySelector<HTMLButtonElement>(".marketing-menu-toggle")?.focus(); } }}>
      <Link href="/" className="marketing-brand">
        <span className="marketing-brand-mark">sb</span>
        <span className="marketing-brand-name">skubase</span>
      </Link>
      <button className="marketing-menu-toggle" type="button" aria-expanded={menuOpen} aria-controls="marketing-navigation" onClick={() => setMenuOpen(open => !open)}>{menuOpen ? "Close" : "Menu"}</button>
      <nav id="marketing-navigation" className="marketing-nav-links" aria-label="Primary" onClick={() => setMenuOpen(false)}>
        <Link href="/features">Features</Link>
        <Link href="/pricing">Pricing</Link>
        <Link href="/about">About</Link>
        <Link href="/blog">Blog</Link>
        <Link href="/changelog">Changelog</Link>
      </nav>
      <div className="marketing-nav-ctas">
        <Link href="/dashboard?demo=1" className="button button-ghost button-sm">
          View demo
        </Link>
        {authState === "loading" ? (
          <span className="marketing-link-subtle" aria-hidden>
            &nbsp;
          </span>
        ) : authState === "signed-in" ? (
          <Link href="/dashboard" className="marketing-link-subtle">
            Dashboard
          </Link>
        ) : (
          <Link href="/login" className="marketing-link-subtle">
            Sign in
          </Link>
        )}
      </div>
    </header>
  );
}
