"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { useAuth } from "@/components/auth-guard";
import { SHOPIFY_DOMAIN_STORAGE_KEY } from "@/lib/app-helpers";

type NavItem = {
  href: string;
  label: string;
  section: "Command" | "Intelligence" | "Operations" | "Settings";
  icon: string;
};

const navigationItems: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", section: "Command", icon: "⬒" },
  { href: "/actions", label: "Action Queue", section: "Command", icon: "◉" },
  { href: "/alerts", label: "Alerts & Rules", section: "Command", icon: "◈" },
  { href: "/forecast", label: "Forecast", section: "Intelligence", icon: "◎" },
  { href: "/analytics", label: "Analytics", section: "Intelligence", icon: "◇" },
  { href: "/suppliers", label: "Suppliers", section: "Intelligence", icon: "◉" },
  { href: "/purchase-orders", label: "Purchase Orders", section: "Operations", icon: "◎" },
  { href: "/transfers", label: "Transfers", section: "Operations", icon: "◈" },
  { href: "/bundles", label: "Bundles & Kits", section: "Operations", icon: "◇" },
  { href: "/liquidation", label: "Liquidation", section: "Operations", icon: "◉" },
  { href: "/store-sync", label: "Store Sync", section: "Settings", icon: "⬒" },
  { href: "/lead-time-settings", label: "Lead Times", section: "Settings", icon: "◈" },
  { href: "/billing", label: "Billing", section: "Settings", icon: "◇" },
  { href: "/account", label: "Account", section: "Settings", icon: "◎" }
];

type PageMeta = { eyebrow: string; title: string; description: string };

const pageMeta: Record<string, PageMeta> = {
  "/dashboard": {
    eyebrow: "Command",
    title: "What should I do today?",
    description:
      "An action-ranked queue over your Shopify catalog. Work it from the top."
  },
  "/actions": {
    eyebrow: "Command",
    title: "Action queue",
    description:
      "Ranked inventory actions — urgent, optimize, dead — ready to triage."
  },
  "/alerts": {
    eyebrow: "Command",
    title: "Alerts that reach you where you work.",
    description:
      "Email, SMS, Slack, and webhooks driven by a real rule engine — not an 'email only' limitation."
  },
  "/forecast": {
    eyebrow: "Intelligence",
    title: "Stockout probability, not stockout guesswork.",
    description:
      "Holt double-exponential smoothing with weekly seasonality. Every recommended quantity explains itself."
  },
  "/analytics": {
    eyebrow: "Intelligence",
    title: "ABC × XYZ scorecards",
    description:
      "Segment the catalog by revenue contribution and demand variability — meet your A-items first."
  },
  "/suppliers": {
    eyebrow: "Intelligence",
    title: "Vendors you can measure.",
    description:
      "On-time delivery, fill rate, lead-time stability, and preferred / acceptable / at-risk tiering."
  },
  "/purchase-orders": {
    eyebrow: "Operations",
    title: "Purchase order drafts",
    description:
      "Auto-consolidated POs by vendor, ready to review and send."
  },
  "/transfers": {
    eyebrow: "Operations",
    title: "Inter-location transfers",
    description:
      "Rebalance inventory between locations before placing new orders."
  },
  "/bundles": {
    eyebrow: "Operations",
    title: "Bundles that don't lose components.",
    description:
      "Kits decompose at reorder time so a PO never leaves a component short."
  },
  "/liquidation": {
    eyebrow: "Operations",
    title: "Cash recovery on stale inventory.",
    description:
      "Every dead-stock SKU comes with a plan — markdown, bundle, wholesale, or write-off — and a dollar-impact estimate."
  },
  "/store-sync": {
    eyebrow: "Settings",
    title: "Manual Shopify sync",
    description:
      "Trigger ingestion and inspect the latest sync run."
  },
  "/lead-time-settings": {
    eyebrow: "Settings",
    title: "Lead time configuration",
    description:
      "Global defaults, safety buffer, and vendor/category overrides."
  },
  "/billing": {
    eyebrow: "Settings",
    title: "Plan and billing",
    description: "Plan selection and invoicing history."
  },
  "/account": {
    eyebrow: "Settings",
    title: "Workspace settings",
    description: "User profile, team, and workspace preferences."
  }
};

const SECTION_ORDER: NavItem["section"][] = [
  "Command",
  "Intelligence",
  "Operations",
  "Settings"
];

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [shopifyDomain, setShopifyDomain] = useState("");
  // hasRealData: true once the shop has any products in the DB. Hides the
  // "Demo data" chip and the yellow demo-mode banner so paid customers
  // don't see "demo" labels on their own data.
  const [hasRealData, setHasRealData] = useState<boolean | null>(null);

  useEffect(() => {
    const storedDomain = window.localStorage.getItem(SHOPIFY_DOMAIN_STORAGE_KEY);
    if (storedDomain) {
      setShopifyDomain(storedDomain);
    }
  }, [pathname]);

  useEffect(() => {
    let cancelled = false;
    void fetch(`${API_BASE}/skus`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : []))
      .then((skus: unknown) => {
        if (cancelled) return;
        setHasRealData(Array.isArray(skus) && skus.length > 0);
      })
      .catch(() => {
        if (!cancelled) setHasRealData(false);
      });
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  const meta = pageMeta[pathname] ?? pageMeta["/dashboard"];

  const groupedNav = SECTION_ORDER.map((section) => ({
    section,
    items: navigationItems.filter((item) => item.section === section)
  }));

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark">sf</span>
          <div>
            <p className="brand-name">slelfly</p>
            <p className="brand-copy">Forecast · Replenish · Recover</p>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Primary">
          {groupedNav.map((group) => (
            <div key={group.section} className="sidebar-nav-group">
              <p className="sidebar-nav-heading">{group.section}</p>
              {group.items.map((item) => {
                const isActive =
                  pathname === item.href || pathname.startsWith(`${item.href}/`);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`nav-link${isActive ? " nav-link-active" : ""}`}
                  >
                    <span className="nav-link-icon" aria-hidden>
                      {item.icon}
                    </span>
                    <span className="nav-link-label">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="sidebar-note">
          <p className="sidebar-note-title">Independent · Shopify-first</p>
          <p className="sidebar-note-copy">
            No PE squeeze. No surprise renewal hikes. Founder-led and
            shipping on a public changelog.
          </p>
          <Link href="/" className="sidebar-note-link">
            See positioning →
          </Link>
        </div>
      </aside>

      <div className="app-main">
        {hasRealData === false ? (
          <div className="demo-banner" role="status">
            <span className="demo-banner-mark" aria-hidden>•</span>
            <span>
              <strong>No data yet.</strong> Import your Stocky or ShipStation
              CSV — or{" "}
              <Link href="/store-sync" className="demo-banner-link">
                connect your Shopify store
              </Link>{" "}
              — to see real recommendations.
            </span>
          </div>
        ) : null}

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
            {hasRealData === false ? (
              <span className="header-chip">Demo data</span>
            ) : null}
            <span className="header-chip header-chip-user" title={user.email}>
              {user.email}
            </span>
            <button
              type="button"
              onClick={() => {
                void logout();
              }}
              className="header-logout"
            >
              Sign out
            </button>
          </div>
        </header>

        <main className="page-container">{children}</main>
      </div>
    </div>
  );
}
