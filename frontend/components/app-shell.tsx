"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { AskSkubaseChat } from "@/components/ask-skubase-chat";
import { useAuth } from "@/components/auth-guard";
import { SHOPIFY_DOMAIN_STORAGE_KEY } from "@/lib/app-helpers";
import { fetchEntitlements, type Entitlements } from "@/lib/entitlements";
import {
  planDisplayName,
  planToTier,
  tierAllows,
} from "@/lib/plans";
import { authenticatedFetch, isEmbeddedShopifyContext } from "@/lib/shopify-embedded";
import { findWorkspacePages, productDataPresent, type NavItem } from "@/lib/workspace-navigation";
import { accountPlanConfirmed, readAccountConnection } from "@/lib/account-data";
import styles from "./app-shell.module.css";
import { WorkspaceIcon } from "@/components/workspace-icon";

type PageMeta = { eyebrow: string; title: string; description: string };

const pageMeta: Record<string, PageMeta> = {
  "/privacy-requests": {
    eyebrow: "Settings",
    title: "Privacy requests",
    description: "Review customer data requests sent by Shopify and export the matching retained records."
  },
  "/dashboard": {
    eyebrow: "Command",
    title: "Overview",
    description:
      "What should I do today? Start with the highest-impact inventory signals in your Shopify catalog."
  },
  "/actions": {
    eyebrow: "Command",
    title: "Action queue",
    description:
      "Ranked SKU recommendations grouped by urgency, cash impact, and what to do next."
  },
  "/alerts": {
    eyebrow: "Command",
    title: "Inventory alerts and rules",
    description:
      "Create stockout, dead-stock, reorder, supplier, and forecast alerts. Send through the channels you enable."
  },
  "/forecast": {
    eyebrow: "Intelligence",
    title: "Forecast and replenishment",
    description:
      "See which SKUs may run short, how lead time affects timing, and what should be reordered."
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
      "Choose a report, filter the products you need, and export the results."
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
      "Review slow-moving inventory and recovery options. Add recorded unit costs before relying on a clearance price or cash estimate."
  },
  "/store-sync": {
    eyebrow: "Settings",
    title: "Connect & import",
    description:
      "Connect Shopify, refresh your store data, or import a Stocky or ShipStation CSV."
  },
  "/lead-time-settings": {
    eyebrow: "Settings",
    title: "Lead times & stock rules",
    description:
      "Set global, supplier, category, and SKU lead-time rules for reorder recommendations."
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
  },
  "/import-stocky": {
    eyebrow: "Setup", title: "Import Stocky CSV", description: "Upload your export, match its columns, and review the result before relying on the recommendations."
  },
  "/import-shipstation": {
    eyebrow: "Setup", title: "Import ShipStation CSV", description: "Bring shipment history into Skubase to help assess product demand."
  },
  "/growth": {
    eyebrow: "Owner", title: "Growth dashboard", description: "Follow qualified customer signals, active conversations, experiments, and the next growth action."
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

const API_BASE = APP_API_BASE_URL;

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [embedded, setEmbedded] = useState(false);
  const [navigationOpen, setNavigationOpen] = useState(false);
  const [navigationQuery, setNavigationQuery] = useState("");
  const navigationSearch = useRef<HTMLInputElement>(null);
  const accountMenu = useRef<HTMLDetailsElement>(null);
  const navigationToggle = useRef<HTMLButtonElement>(null);
  const [shopifyDomain, setShopifyDomain] = useState<string | null>(null);
  const [storeLoaded, setStoreLoaded] = useState(false);
  const [connectionStatusFailed, setConnectionStatusFailed] = useState(false);
  const [lastSyncAt, setLastSyncAt] = useState<string | null>(null);
  const [syncConnected, setSyncConnected] = useState<boolean>(false);
  const [subscription, setSubscription] = useState<Entitlements | null>(null);
  const [subscriptionLoaded, setSubscriptionLoaded] = useState(false);
  const [subscriptionStatusFailed, setSubscriptionStatusFailed] = useState(false);
  // hasRealData: true once the shop has any products in the DB. Hides the
  // "Sample data" chip and the yellow demo-mode banner so paid customers
  // don't see "demo" labels on their own data.
  const [hasRealData, setHasRealData] = useState<boolean | null>(null);
  const [inventoryStatusFailed, setInventoryStatusFailed] = useState(false);

  useEffect(() => {
    const closeAccount = (event: PointerEvent) => {
      if (accountMenu.current && !accountMenu.current.contains(event.target as Node)) accountMenu.current.open = false;
    };
    document.addEventListener("pointerdown", closeAccount);
    return () => document.removeEventListener("pointerdown", closeAccount);
  }, []);

  useEffect(() => { if (accountMenu.current) accountMenu.current.open = false; }, [pathname]);

  useEffect(() => {
    if (navigationOpen && window.matchMedia("(max-width: 1024px)").matches) {
      navigationToggle.current?.scrollIntoView({ block: "start" });
      navigationSearch.current?.focus({ preventScroll: true });
    }
  }, [navigationOpen]);


  // Trial countdown - only meaningful for real (non-demo) users.
  const trialDaysLeft: number | null = (() => {
    if (user.id === 0 || !user.trial_ends_at) return null;
    const ms = new Date(user.trial_ends_at).getTime() - Date.now();
    const days = Math.ceil(ms / (1000 * 60 * 60 * 24));
    return days > 0 ? days : 0;
  })();

  useEffect(() => {
    setEmbedded(isEmbeddedShopifyContext());
    if (user.id !== 0) return; // Real store identity comes only from the authenticated API.
    const urlShop = new URLSearchParams(window.location.search).get("shop");
    let storedDomain = urlShop;
    try {
      storedDomain ||= window.localStorage.getItem(SHOPIFY_DOMAIN_STORAGE_KEY);
      if (urlShop) window.localStorage.setItem(SHOPIFY_DOMAIN_STORAGE_KEY, urlShop);
    } catch {
      // Storage can be blocked inside Shopify; the authenticated connection
      // remains the source of truth for the store displayed below.
    }
    setShopifyDomain((previous) => storedDomain || previous || "");
    if (user.id === 0) setStoreLoaded(true);
  }, [pathname, user.id]);

  useEffect(() => {
    setSubscriptionLoaded(false);
    setSubscriptionStatusFailed(false);
    if (user.id === 0) {
      setSubscription(null);
      setSubscriptionLoaded(true);
      return;
    }

    let cancelled = false;
    void fetchEntitlements()
      .then((data) => {
        if (!accountPlanConfirmed(data)) throw new Error("Plan status unavailable");
        if (!cancelled) setSubscription(data);
      })
      .catch(() => {
        if (!cancelled) {
          setSubscription(null);
          setSubscriptionStatusFailed(true);
        }
      })
      .finally(() => {
        if (!cancelled) setSubscriptionLoaded(true);
      });

    return () => {
      cancelled = true;
    };
  }, [user.id, pathname]);

  useEffect(() => {
    if (user.id === 0) return;
    let cancelled = false;
    setStoreLoaded(false);
    setConnectionStatusFailed(false);
    void authenticatedFetch(`${API_BASE}/integrations/shopify/connection`, {
      credentials: "include",
    })
      .then(async r => { if (!r.ok) throw new Error("Connection status unavailable"); return readAccountConnection(await r.json()); })
      .then(conn => {
        if (cancelled) return;
        setShopifyDomain(conn.connected ? conn.shopify_domain : null);
        setSyncConnected(conn.connected);
        setLastSyncAt(conn.last_sync_at ?? null);
      })
      .catch(() => {
        if (!cancelled) { setConnectionStatusFailed(true); setSyncConnected(false); setLastSyncAt(null); }
      })
      .finally(() => { if (!cancelled) setStoreLoaded(true); });
    return () => {
      cancelled = true;
    };
  }, [user.id, pathname]);

  useEffect(() => {
    if (user.id === 0) return;
    let cancelled = false;
    void authenticatedFetch(`${API_BASE}/skus/summary`, { credentials: "include" })
      .then((r) => { if (!r.ok) throw new Error("Inventory status unavailable"); return r.json(); })
      .then((summary: unknown) => {
        if (cancelled) return;
        const present = productDataPresent(summary);
        if (present === null) throw new Error("Inventory status unavailable");
        setHasRealData(present);
        setInventoryStatusFailed(false);
      })
      .catch(() => {
        if (!cancelled) { setHasRealData(null); setInventoryStatusFailed(true); }
      });
    return () => {
      cancelled = true;
    };
  }, [pathname, user.id]);

  // Sync freshness chip — silent sync breakage is the #1 trust killer in
  // competing tools, so surface staleness instead of hiding it.
  const syncChip = (() => {
    if (user.id === 0 || !syncConnected) return null;
    if (!lastSyncAt) {
      return { label: "Never synced", warn: true, title: "Run a sync from Store Sync." };
    }
    const ageMs = Date.now() - new Date(lastSyncAt).getTime();
    if (!Number.isFinite(ageMs)) return null;
    const hours = ageMs / (1000 * 60 * 60);
    if (hours < 1) return { label: "Synced just now", warn: false, title: "Shopify data is fresh." };
    if (hours < 26) {
      return {
        label: `Synced ${Math.round(hours)}h ago`,
        warn: false,
        title: "Shopify data is fresh.",
      };
    }
    const days = Math.floor(hours / 24);
    return {
      label: `Sync stale (${days}d)`,
      warn: true,
      title: "Data may be out of date - run a sync from the Store Sync page.",
    };
  })();

  const meta = pageMeta[pathname] ?? pageMeta["/dashboard"];
  const isWideAppRoute = WIDE_APP_ROUTES.has(pathname);
  const appContainerClassName = `page-container${isWideAppRoute ? " page-container-wide" : ""}`;
  const headerClassName = `top-header${isWideAppRoute ? " top-header-wide" : ""}`;

  const visibleNav = findWorkspacePages(navigationQuery, user.is_admin);
  const groupedNav = SECTION_ORDER.map((section) => ({
    section,
    items: visibleNav.filter((item) => item.section === section)
  })).filter(group => group.items.length > 0);

  const paidTier =
    subscription?.subscription_status === "active" || subscription?.subscription_status === "trialing"
      ? planToTier(subscription.plan_id)
      : null;
  const hasActiveSubscription = subscriptionLoaded && paidTier !== null;
  const isShopifyInstalled = Boolean(subscription?.is_shopify_installed);
  const directTrialAccess =
    Boolean(user.in_trial) && !isShopifyInstalled && !isEmbeddedShopifyContext();
  const unlockAll = user.id === 0 || directTrialAccess || !subscriptionLoaded || subscriptionStatusFailed;
  const planChipLabel =
    user.id === 0
      ? "Sample workspace"
      : !subscriptionLoaded
      ? "Loading plan..."
      : subscriptionStatusFailed
      ? "Plan status unavailable"
      : subscription?.subscription_status === "active" || subscription?.subscription_status === "trialing"
      ? planDisplayName(subscription.plan_id)
      : "No active plan";

  return (
    <div className={`app-shell ${styles.shell}`} onKeyDown={event => {
      if (event.key !== "Escape") return;
      if (accountMenu.current?.open) { accountMenu.current.open = false; accountMenu.current.querySelector("summary")?.focus(); }
      if (navigationOpen) { setNavigationOpen(false); navigationToggle.current?.focus(); }
    }}>
      <a className={styles.skipLink} href="#workspace-content">Skip to content</a>
      <aside className="sidebar" data-navigation-open={navigationOpen}>
        <div className={styles.mobileHeader}>
        <div className="sidebar-brand">
          <span className="brand-mark">sb</span>
          <div>
            <p className="brand-name">skubase</p>
            <p className="brand-copy">Forecast - Replenish - Recover</p>
          </div>
        </div>
        <button type="button" ref={navigationToggle} className={styles.navigationToggle} aria-expanded={navigationOpen}
          aria-controls="workspace-navigation" onClick={() => setNavigationOpen(!navigationOpen)}>
          <WorkspaceIcon name="menu" /> {navigationOpen ? "Close" : "Menu"}
        </button>
        </div>

        <div className={styles.navigationSearch}>
          <label htmlFor="workspace-search">Find a page or task</label>
          <div className={styles.searchControl}>
            <input id="workspace-search" ref={navigationSearch} type="search" value={navigationQuery}
              placeholder="Try “email alerts”" autoComplete="off" aria-controls="workspace-navigation"
              onChange={event => setNavigationQuery(event.target.value)}
              onKeyDown={event => { if (event.key === "Escape" && navigationQuery) { setNavigationQuery(""); event.stopPropagation(); } }} />
            {navigationQuery ? <button type="button" aria-label="Clear page search" onClick={() => { setNavigationQuery(""); navigationSearch.current?.focus(); }}>×</button> : null}
          </div>
          {navigationQuery.trim() ? <p role="status">{visibleNav.length} matching page{visibleNav.length === 1 ? "" : "s"}</p> : null}
        </div>

        <nav id="workspace-navigation" className="sidebar-nav" aria-label="Primary">
          {groupedNav.length === 0 ? <p className={styles.noResults}>No page found. Try “import”, “reorder”, “alerts”, or “billing”.</p> : null}
          {groupedNav.map((group) => (
            <div key={group.section} className="sidebar-nav-group">
              <p className="sidebar-nav-heading">{{ Command: "Workspace", Intelligence: "Inventory", Operations: "Operations", Settings: "Manage" }[group.section]}</p>
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
                    href={item.href}
                    onClick={() => { if (navigationOpen) navigationToggle.current?.focus(); setNavigationOpen(false); setNavigationQuery(""); }}
                    aria-current={isActive ? "page" : undefined}
                    className={`nav-link${isActive ? " nav-link-active" : ""}${
                      isLocked ? " nav-link-locked" : ""
                    }`}
                    title={isLocked ? `${item.label} is included on ${planDisplayName(item.minTier!)}.` : undefined}
                  >
                    <span className="nav-link-icon" aria-hidden>
                      <WorkspaceIcon name={item.icon} />
                    </span>
                    <span className="nav-link-label">{item.href === "/dashboard" ? "Overview" : item.label}</span>
                    {isLocked ? (
                      <span className="nav-link-gate">{planDisplayName(item.minTier!)}</span>
                    ) : null}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        <div className={styles.sidebarAccount}>
          <Link href="/account"><WorkspaceIcon name="AC" /><span>Workspace settings<small>{planChipLabel}</small></span></Link>
          <Link href="/billing">Manage billing →</Link>
        </div>
      </aside>

      <div className="app-main">
        <div className={styles.utilityBar}>
          <p className={styles.breadcrumb}>{meta.eyebrow}<span aria-hidden="true">/</span><strong>{meta.title}</strong></p>
          <div className={styles.utilities}>
            <div className={styles.syncStatus}>            {syncChip ? (
              <span
                className={`header-chip ${syncChip.warn ? "header-chip-warning" : "header-chip-success"}`}
                title={syncChip.title}
              >
                {syncChip.label}
              </span>
            ) : null}
</div>
            <AskSkubaseChat />
            <details className={styles.accountMenu} ref={accountMenu}>
              <summary aria-label="Workspace account"><WorkspaceIcon name="AC" /><span>Workspace</span></summary>
              <div className={styles.accountPanel}>
            <span className="header-chip header-chip-tone">
              {user.id === 0 ? "Sample workspace" : !storeLoaded ? "Loading store..." : connectionStatusFailed ? "Connection status unavailable" : shopifyDomain || "No store connected"}
            </span>
            {user.id === 0 ? <span className="header-chip">Sample data</span> : hasRealData === false ? <span className="header-chip">No product data</span> : inventoryStatusFailed ? <span className="header-chip">Inventory status unavailable</span> : null}
            {user.id !== 0 && !embedded ? (
              // Embedded users authenticate via Shopify; their synthetic
              // shopify-admin+... address would only confuse.
              <span className="header-chip header-chip-user" title={user.email}>
                {user.email}
              </span>
            ) : null}
            {user.id !== 0 ? (
              <span className={`header-chip ${hasActiveSubscription ? "header-chip-success" : "header-chip-warning"}`}>
                {planChipLabel}
              </span>
            ) : null}
            {user.id !== 0 ? (
              embedded ? null : (
                // No sign-out inside Shopify admin — the session belongs to
                // Shopify, and logging out would strand the iframe on the
                // marketing site.
                <button
                  type="button"
                  onClick={() => { void logout(); }}
                  className="header-logout"
                >
                  Sign out
                </button>
              )
            ) : (
              <Link href="/login" className="button button-primary button-sm">
                Sign up free
              </Link>
            )}
          </div>
            </details>
          </div>
        </div>
        {user.id === 0 ? (
          // Demo mode - synthetic user injected by AuthGuard when ?demo=1.
          <div className="demo-banner demo-banner-preview" role="status">
            <span className="demo-banner-mark" aria-hidden>o</span>
            <span>
              <strong>This is sample data - not your store.</strong>{" "}
              <Link href="/tools/inventory-health-check" className="demo-banner-link">
                Check your own inventory for free
              </Link>{" "}
              with a CSV summary, no installation required. Skubase is in Shopify review and is not yet listed in the App Store.
            </span>
          </div>
        ) : hasRealData === false ? (
          <div className="demo-banner" role="status">
            <span className="demo-banner-mark" aria-hidden>*</span>
            <span>
              <strong>No product data yet.</strong>{" "}
              <Link href="/store-sync" className="demo-banner-link">
                Choose a connection or import option
              </Link>{" "}
              to get started. Recommendations need current stock and sales history.
            </span>
          </div>
        ) : null}

        {user.id !== 0 && !isShopifyInstalled && subscriptionLoaded && !subscriptionStatusFailed && !hasActiveSubscription && trialDaysLeft !== null && trialDaysLeft <= 7 ? (
          <div className={`demo-banner ${trialDaysLeft <= 2 ? "demo-banner-preview" : ""}`} role="status">
            <span className="demo-banner-mark" aria-hidden>*</span>
            <span>
              {trialDaysLeft === 0 ? (
                <>
                  <strong>Your trial has ended.</strong>{" "}
                  <Link href="/billing" className="demo-banner-link">
                    Choose a plan
                  </Link>{" "}
                  to keep access to your data and recommendations.
                </>
              ) : (
                <>
                  <strong>{trialDaysLeft} day{trialDaysLeft === 1 ? "" : "s"} left in your trial.</strong>{" "}
                  <Link href="/billing" className="demo-banner-link">
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


        </header>

        <main id="workspace-content" tabIndex={-1} className={appContainerClassName}>{children}</main>
      </div>
      <nav className={styles.bottomNav} aria-label="Mobile workspace">
        {[{ href: "/dashboard", label: "Overview", icon: "DB" }, { href: "/actions", label: "Actions", icon: "AQ" }, { href: "/purchase-orders", label: "Orders", icon: "PO" }].map(item => (
          <Link key={item.href} href={item.href} aria-current={pathname === item.href ? "page" : undefined} onClick={() => setNavigationOpen(false)}><WorkspaceIcon name={item.icon} /><span>{item.label}</span></Link>
        ))}
        <button type="button" aria-expanded={navigationOpen} aria-controls="workspace-navigation" onClick={() => setNavigationOpen(open => !open)}><WorkspaceIcon name="menu" /><span>More</span></button>
      </nav>
    </div>
  );
}
