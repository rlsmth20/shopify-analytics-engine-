"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

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
    title: "Inventory command center",
    description:
      "Real-time view of demand, risk, and capital across your Shopify catalog."
  },
  "/actions": {
    eyebrow: "Command",
    title: "Action queue",
    description:
      "Ranked inventory actions — stockout risk, overstock, dead stock — ready to triage."
  },
  "/alerts": {
    eyebrow: "Command",
    title: "Alerts & notification rules",
    description:
      "Get pinged the moment something needs a human — email, SMS, Slack, or webhook."
  },
  "/forecast": {
    eyebrow: "Intelligence",
    title: "Demand forecast",
    description:
      "30/60/90-day projections with seasonality, trend, and stockout probability."
  },
  "/analytics": {
    eyebrow: "Intelligence",
    title: "ABC · XYZ scorecards",
    description:
      "Segment the catalog by revenue contribution and demand variability."
  },
  "/suppliers": {
    eyebrow: "Intelligence",
    title: "Supplier scoreboard",
    description:
      "Vendor on-time delivery, fill rate, and lead-time stability at a glance."
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
    title: "Bundle & kit health",
    description:
      "See which bundles are bottlenecked and how much component capital is stranded."
  },
  "/liquidation": {
    eyebrow: "Operations",
    title: "Dead-stock liquidator",
    description:
      "Markdown, bundle, wholesale, or write-off — cash recovery plans for stale inventory."
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

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [shopifyDomain, setShopifyDomain] = useState("");

  useEffect(() => {
    const storedDomain = window.localStorage.getItem(SHOPIFY_DOMAIN_STORAGE_KEY);
    if (storedDomain) {
      setShopifyDomain(storedDomain);
    }
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
          <span className="brand-mark">IC</span>
          <div>
            <p className="brand-name">Inventory Command</p>
            <p className="brand-copy">Forecast · Replenish · Alert</p>
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
          <p className="sidebar-note-title">Built for Shopify</p>
          <p className="sidebar-note-copy">
            Forecasting, replenishment, supplier scoring, and multi-channel
            alerting in one place.
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
            <span className="header-chip">Live mode</span>
          </div>
        </header>

        <main className="page-container">{children}</main>
      </div>
    </div>
  );
}
