"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "skubase_stocky_migration_steps";

const STEPS = [
  {
    id: "connect-shopify",
    title: "Choose your data sources",
    body: "Open Store Sync for CSV import options. If Skubase is already installed for your store, sync Shopify products, inventory, and orders in read-only mode.",
    href: "/store-sync",
    cta: "Open store sync",
  },
  {
    id: "upload-stocky",
    title: "Import your Stocky catalog",
    body: "Stocky supplies catalog details and a stock snapshot for CSV-only workspaces. With Shopify connected or already synced, CSVs only enrich supported costs and lead times for unambiguous variants. Add non-Shopify shipment history separately through ShipStation on Store Sync; Stocky CSVs do not supply sales history.",
    href: "/import-stocky",
    cta: "Import Stocky CSV",
  },
  {
    id: "lead-times",
    title: "Set vendor and category lead times",
    body: "Replace Stocky's flat assumptions with vendor-specific planning inputs.",
    href: "/lead-time-settings",
    cta: "Set lead times",
  },
  {
    id: "forecast-review",
    title: "Review forecast trust",
    body: "Check backtest error, confidence, and warnings before turning recommendations into buys.",
    href: "/forecast",
    cta: "Review forecasts",
  },
  {
    id: "reorder-queue",
    title: "Work the first reorder queue",
    body: "Prioritize urgent stockouts, then optimize overstock and dead inventory.",
    href: "/actions",
    cta: "Open action queue",
  },
  {
    id: "purchase-orders",
    title: "Prepare PO drafts and record receipts",
    body: "Use your purchasing system to send orders and receive goods. Record those receipts in Skubase for supplier analysis when included in your plan; these records do not change Shopify stock.",
    href: "/purchase-orders",
    cta: "Open purchase orders",
  },
];

export default function StockyMigrationPage() {
  const [done, setDone] = useState<Record<string, boolean>>({});

  useEffect(() => {
    try {
      setDone(JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}"));
    } catch {
      setDone({});
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(done));
  }, [done]);

  const completed = useMemo(
    () => STEPS.filter((step) => done[step.id]).length,
    [done],
  );
  const pct = Math.round((completed / STEPS.length) * 100);

  return (
    <div className="page-stack">
      <p className="section-copy">
        Skubase is in Shopify&apos;s review process and is not yet listed in the Shopify App Store.
        Start with CSV imports, or <Link href="/tools/inventory-health-check">try the free browser inventory check</Link> without installation.
      </p>
      <div className="kpi-grid kpi-grid-tight">
        <div className="kpi-card">
          <p className="kpi-label">Migration progress</p>
          <p className="kpi-value">{pct}%</p>
          <p className="kpi-note">{completed} of {STEPS.length} steps complete</p>
        </div>
        <div className="kpi-card">
          <p className="kpi-label">Sync posture</p>
          <p className="kpi-value">Read-only</p>
          <p className="kpi-note">This planning workflow does not change Shopify stock.</p>
        </div>
        <div className="kpi-card">
          <p className="kpi-label">Goal</p>
          <p className="kpi-value">First PO</p>
          <p className="kpi-note">Supplier scorecards require receipt history and an included plan.</p>
        </div>
      </div>

      <div className="signal-list migration-checklist">
        {STEPS.map((step, index) => (
          <div key={step.id} className="signal-item migration-checklist-row">
            <div>
              <p className="signal-title">{index + 1}. {step.title}</p>
              <p className="signal-copy">{step.body}</p>
            </div>
            <div className="migration-step-actions">
              <button
                type="button"
                className={`button ${done[step.id] ? "button-ghost" : "button-primary"}`}
                onClick={() => setDone((current) => ({ ...current, [step.id]: !current[step.id] }))}
              >
                {done[step.id] ? "Done" : "Mark done"}
              </button>
              <Link href={step.href} className="button button-ghost">
                {step.cta}
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
