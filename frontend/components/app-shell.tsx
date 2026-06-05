"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { AskSkubaseChat } from "@/components/ask-skubase-chat";
import { useAuth } from "@/components/auth-guard";
import { SHOPIFY_DOMAIN_STORAGE_KEY } from "@/lib/app-helpers";
import { planToTier, tierAllows, type PlanTierKey } from "@/lib/plans";
import { authenticatedFetch } from "@/lib/shopify-embedded";

type NavItem = {
  href: string;
  label: string;
  section: "Command" | "Intelligence" | "Operations" | "Settings";
  icon: string;
  minTier?: PlanTierKey;
};

const navigationItems: NavItem[] = [
  { href: "/dashboard", label: "Today", section: "Command", icon: ">" },
  { href: "/actions", label: "Action Queue", section: "Command", icon: "o" },
  { href: "/alerts", label: "Alerts & Rules", section: "Command", icon: "*" },
  { href: "/forecast", label: "Forecast", section: "Intelligence", icon: "o" },
  { href: "/analytics", label: "Inventory Health", section: "Intelligence", icon: "<>" },
  { href: "/reports", label: "Reports & Exports", section: "Intelligence", icon: ">" },
  { href: "/suppliers", label: "Suppliers", section: "Intelligence", icon: "o", minTier: "growth" },
  { href: "/purchase-orders", label: "Reorder / POs", section: "Operations", icon: "o" },
  { href: "/stocky-migration", label: "Stocky Migration", section: "Operations", icon: ">" },
  { href: "/transfers", label: "Transfers", section: "Operations", icon: "*", minTier: "growth" },
  { href: "/bundles", label: "Bundle Opportunities", section: "Operations", icon: "<>", minTier: "growth" },
  { href: "/liquidation", label: "Dead Stock", section: "Operations", icon: "o", minTier: "growth" },
  { href: "/store-sync", label: "Store Sync", section: "Settings", icon: ">" },
  { href: "/lead-time-settings", label: "Lead Times", section: "Settings", icon: "*" },
  { href: "/billing", label: "Billing", section: "Settings", icon: "<>" },
  { href: "/account", label: "Account", section: "Settings", icon: "o" },
  { href: "/feedback", label: "Contact & Feedback", section: "Settings", icon: "o" }
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
      "Ranked Action Queue - urgent, optimize, dead - ready to triage."
  },
  "/alerts": {
    eyebrow: "Command",
    title: "Alerts that reach you where you work.",
    description:
      "Email, SMS, Slack, and webhooks driven by a real rule engine - not an 'email only' limitation."
  },
  "/forecast": {
    eyebrow: "Intelligence",
    title: "Stockout probability, not stockout guesswork.",
    description:
      "Holt double-exponential smoothing with weekly seasonality. Every recommended quantity explains itself."
  },
  "/analytics": {
    eyebrow: "Intelligence",
    title: "Inventory health",
    description:
      "Segment the catalog by revenue contribution and demand variability - meet your A-items first."
  },
  "/reports": {
    eyebrow: "Intelligence",
    title: "Reports & exports",
    description:
      "A lightweight library of the inventory reports and exports already wired into skubase."
  },
  "/suppliers": {
    eyebrow: "Intelligence",
    title: "Suppliers you can measure.",
    description:
      "On-time delivery, fill rate, lead-time stability, and preferred / acceptable / at-risk tiering."
  },
  "/purchase-orders": {
    eyebrow: "Operations",
    title: "Reorder plan and PO drafts",
    description:
      "Supplier-grouped PO drafts, ready to review and email manually."
  },
  "/stocky-migration": {
    eyebrow: "Operations",
    title: "Stocky migration checklist",
    description:
      "A first-run workflow for replacing Stocky with safe sync, lead times, forecasting, and reorder review."
  },
  "/transfers": {
    eyebrow: "Operations",
    title: "Inter-location transfers",
    description:
      "Rebalance inventory between locations before placing new orders."
  },
  "/bundles": {
    eyebrow: "Operations",
    title: "Bundle opportunities",
    description:
      "Find products customers buy together; component tracking requires mappings."
  },
  "/liquidation": {
    eyebrow: "Operations",
    title: "Dead stock recovery.",
    description:
      "Every dead-stock SKU comes with a plan - markdown, bundle, wholesale, or write-off - and a dollar-impact estimate."
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
      "Global defaults, safety buffer, and supplier/category overrides."
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
  },
  "/feedback": {
    eyebrow: "Support",
    title: "Contact us",
    description: "Report a bug, ask a question, or share feedback - we reply within one business day."
  },
  "/contact": {
    eyebrow: "Support",
    title: "Contact us",
    description: "Report a bug, ask a question, or share feedback - we reply within one business day."
  }
};

const SECTION_ORDER: NavItem["section"][] = [
  "Command",
  "Intelligence",
  "Operations",
  "Settings"
];

const WIDE_APP_ROUTES = new Set([
  "/actions",
  "/analytics",
  "/reports",
  "/purchase-orders",
  "/forecast",
  "/suppliers",
  "/liquidation",
  "/bundles",
  "/transfers",
]);

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type Subscription = {
  plan: string;
  status: string;
};

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [shopifyDomain, setShopifyDomain] = useState<string | null>(null);
  const [storeLoaded, setStoreLoaded] = useState(false);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [subscriptionLoaded, setSubscriptionLoaded] = useState(false);
  // hasRealData: true once the shop has any products in the DB. Hides the
  // "Sample data" chip and the yellow demo-mode banner so paid customers
  // don't see "demo" labels on their own data.
  const [hasRealData, setHasRealData] = useState<boolean | null>(null);

  // Trial countdown - only meaningful for real (non-demo) users.
  const trialDaysLeft: number | null = (() => {
    if (user.id === 0 || !user.trial_ends_at) return null;
    const ms = new Date(user.trial_ends_at).getTime() - Date.now();
    const days = Math.ceil(ms / (1000 * 60 * 60 * 24));
    return days > 0 ? days : 0;
  })();

  useEffect(() => {
    const storedDomain = window.localStorage.getItem(SHOPIFY_DOMAIN_STORAGE_KEY);
    setShopifyDomain(storedDomain || "");
    setStoreLoaded(true);
  }, [pathname]);

  useEffect(() => {
    setSubscriptionLoaded(false);
    if (user.id === 0) {
      setSubscription(null);
      setSubscriptionLoaded(true);
      return;
    }

    let cancelled = false;
    void authenticatedFetch(`${API_BASE}/billing/me`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: Subscription | null) => {
        if (!cancelled) setSubscription(data);
      })
      .catch(() => {
        if (!cancelled) setSubscription(null);
      })
      .finally(() => {
        if (!cancelled) setSubscriptionLoaded(true);
      });

    return () => {
      cancelled = true;
    };
  }, [user.id]);

  useEffect(() => {
    let cancelled = false;
    void authenticatedFetch(`${API_BASE}/skus/summary`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : { product_count: 0 }))
      .then((summary: unknown) => {
        if (cancelled) return;
        const productCount =
          typeof summary === "object" &&
          summary !== null &&
          "product_count" in summary &&
          typeof summary.product_count === "number"
            ? summary.product_count
            : 0;
        setHasRealData(productCount > 0);
      })
      .catch(() => {
        if (!cancelled) setHasRealData(false);
      });
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  const meta = pageMeta[pathname] ?? pageMeta["/dashboard"];
  const isWideAppRoute = WIDE_APP_ROUTES.has(pathname);
  const appContainerClassName = `page-container${isWideAppRoute ? " page-container-wide" : ""}`;
  const headerClassName = `top-header${isWideAppRoute ? " top-header-wide" : ""}`;

  const groupedNav = SECTION_ORDER.map((section) => ({
    section,
    items: navigationItems.filter((item) => item.section === section)
  }));

  const paidTier =
    subscription?.status === "active" || subscription?.status === "trialing"
      ? planToTier(subscription.plan)
      : null;
  const hasActiveSubscription = subscriptionLoaded && paidTier !== null;
  const unlockAll = user.id === 0 || Boolean(user.in_trial) || Boolean(user.is_admin) || !subscriptionLoaded;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark">sb</span>
          <div>
            <p className="brand-name">skubase</p>
            <p className="brand-copy">Forecast - Replenish - Recover</p>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Primary">
          {groupedNav.map((group) => (
            <div key={group.section} className="sidebar-nav-group">
              <p className="sidebar-nav-heading">{group.section}</p>
              {group.items.map((item) => {
                const isActive =
                  pathname === item.href || pathname.startsWith(`${item.href}/`);
                const isLocked =
                  Boolean(item.minTier) &&
                  !unlockAll &&
                  !tierAllows(paidTier, item.minTier!);

                return (
                  <Link
                    key={item.href}
                    href={isLocked ? "/pricing" : item.href}
                    className={`nav-link${isActive ? " nav-link-active" : ""}${
                      isLocked ? " nav-link-locked" : ""
                    }`}
                    title={isLocked ? `${item.label} is included on Growth and Scale.` : undefined}
                  >
                    <span className="nav-link-icon" aria-hidden>
                      {item.icon}
                    </span>
                    <span className="nav-link-label">{item.label}</span>
                    {isLocked ? (
                      <span className="nav-link-gate">Growth</span>
                    ) : null}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="sidebar-note">
          <p className="sidebar-note-title">Independent - Shopify-first</p>
          <p className="sidebar-note-copy">
            No PE squeeze. No surprise renewal hikes. Founder-led and
            shipping on a public changelog.
          </p>
          <Link href="/" className="sidebar-note-link">
            See positioning -&gt;
          </Link>
        </div>
      </aside>

      <div className="app-main">
        {user.id === 0 ? (
          // Demo mode - synthetic user injected by AuthGuard when ?demo=1.
          <div className="demo-banner demo-banner-preview" role="status">
            <span className="demo-banner-mark" aria-hidden>o</span>
            <span>
              <strong>This is sample data - not your store.</strong>{" "}
              <Link href="/login" className="demo-banner-link">
                Start your free 14-day trial
              </Link>{" "}
              to connect Shopify and see your actual stockouts, reorder queue, and dead stock. No credit card required.
            </span>
          </div>
        ) : hasRealData === false ? (
          <div className="demo-banner" role="status">
            <span className="demo-banner-mark" aria-hidden>*</span>
            <span>
              <strong>No data yet.</strong> Import your Stocky or ShipStation
              CSV - or{" "}
              <Link href="/store-sync" className="demo-banner-link">
                connect your Shopify store
              </Link>{" "}
              - to see real recommendations.
            </span>
          </div>
        ) : null}

        {user.id !== 0 && subscriptionLoaded && !hasActiveSubscription && trialDaysLeft !== null && trialDaysLeft <= 7 ? (
          <div className={`demo-banner ${trialDaysLeft <= 2 ? "demo-banner-preview" : ""}`} role="status">
            <span className="demo-banner-mark" aria-hidden>*</span>
            <span>
              {trialDaysLeft === 0 ? (
                <>
                  <strong>Your trial has ended.</strong>{" "}
                  <Link href="/pricing" className="demo-banner-link">
                    Choose a plan
                  </Link>{" "}
                  to keep access to your data and recommendations.
                </>
              ) : (
                <>
                  <strong>{trialDaysLeft} day{trialDaysLeft === 1 ? "" : "s"} left in your trial.</strong>{" "}
                  <Link href="/pricing" className="demo-banner-link">
                    See plans
                  </Link>{" "}
                  - 14-day free, no credit card required at signup.
                </>
              )}
            </span>
          </div>
        ) : null}
        <header className={headerClassName}>
          <div>
            <p className="header-eyebrow">{meta.eyebrow}</p>
            <h1 className="header-title">{meta.title}</h1>
            <p className="header-copy">{meta.description}</p>
          </div>

          <div className="header-meta">
            <span className="header-chip header-chip-tone">
              {storeLoaded ? (shopifyDomain ? shopifyDomain : "No store selected") : "Loading store..."}
            </span>
            {hasRealData === false ? (
              <span className="header-chip">Sample data</span>
            ) : null}
            {user.id !== 0 ? (
              <span className="header-chip header-chip-user" title={user.email}>
                {user.email}
              </span>
            ) : null}
            {user.id !== 0 ? (
              <button
                type="button"
                onClick={() => { void logout(); }}
                className="header-logout"
              >
                Sign out
              </button>
            ) : (
              <Link href="/login" className="button button-primary button-sm">
                Sign up free
              </Link>
            )}
          </div>
        </header>

        <main className={appContainerClassName}>{children}</main>
      </div>
      <AskSkubaseChat />
    </div>
  );
}
