"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { SHOPIFY_DOMAIN_STORAGE_KEY } from "@/lib/app-helpers";

const navigationItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/actions", label: "Actions" },
  { href: "/analytics", label: "Analytics" },
  { href: "/store-sync", label: "Store Sync" },
  { href: "/lead-time-settings", label: "Lead Time Settings" },
  { href: "/billing", label: "Billing" },
  { href: "/account", label: "Account" }
];

const pageMeta = {
  "/dashboard": {
    eyebrow: "Overview",
    title: "Inventory command center",
    description:
      "Executive view of urgent inventory risk, cash exposure, and sync health."
  },
  "/actions": {
    eyebrow: "Actions",
    title: "Decision queue",
    description:
      "Work the prioritized action feed with live backend ranking, filtering, and export."
  },
  "/analytics": {
    eyebrow: "Analytics",
    title: "Risk and capital signals",
    description:
      "Read the current action mix, impact concentration, and lead-time pressure in one place."
  },
  "/store-sync": {
    eyebrow: "Store Sync",
    title: "Manual Shopify sync",
    description:
      "Run ingestion, inspect the latest sync run, and confirm the live data path is healthy."
  },
  "/lead-time-settings": {
    eyebrow: "Settings",
    title: "Lead time configuration",
    description:
      "Manage global defaults, safety buffer, mock fallback, and vendor/category overrides."
  },
  "/billing": {
    eyebrow: "Billing",
    title: "Plan and billing",
    description:
      "Placeholder billing surfaces for a future commercial SaaS release."
  },
  "/account": {
    eyebrow: "Account",
    title: "Workspace settings",
    description:
      "Placeholder account, workspace, and preference surfaces for the current MVP."
  }
} as const;

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [shopifyDomain, setShopifyDomain] = useState("");

  useEffect(() => {
    const storedDomain = window.localStorage.getItem(SHOPIFY_DOMAIN_STORAGE_KEY);
    if (storedDomain) {
      setShopifyDomain(storedDomain);
    }
  }, [pathname]);

  const meta = pageMeta[pathname as keyof typeof pageMeta] ?? pageMeta["/dashboard"];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark">IC</span>
          <div>
            <p className="brand-name">Inventory Command</p>
            <p className="brand-copy">Shopify inventory decisions</p>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Primary">
          {navigationItems.map((item) => {
            const isActive =
              pathname === item.href || pathname.startsWith(`${item.href}/`);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-link${isActive ? " nav-link-active" : ""}`}
              >
                <span className="nav-link-label">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="sidebar-note">
          <p className="sidebar-note-title">Live Shopify MVP</p>
          <p className="sidebar-note-copy">
            Manual sync mode with DB-backed actions and controlled mock fallback.
          </p>
        </div>
      </aside>

      <div className="app-main">
        <header className="top-header">
          <div>
            <p className="header-eyebrow">{meta.eyebrow}</p>
            <h1 className="header-title">{meta.title}</h1>
            <p className="header-copy">{meta.description}</p>
          </div>

          <div className="header-meta">
            <span className="header-chip header-chip-tone">
              {shopifyDomain ? shopifyDomain : "No store selected"}
            </span>
            <span className="header-chip">Manual sync mode</span>
          </div>
        </header>

        <main className="page-container">{children}</main>
      </div>
    </div>
  );
}
