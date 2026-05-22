"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "skubase_stocky_migration_steps";

const STEPS = [
  {
    id: "connect-shopify",
    title: "Connect Shopify in read-only mode",
    body: "Import products, inventory, and orders without writing stock changes back to Shopify.",
    href: "/store-sync",
    cta: "Open store sync",
  },
  {
    id: "upload-stocky",
    title: "Upload Stocky or ShipStation exports",
    body: "Backfill order history so forecasts and ABC/XYZ classifications have enough demand signal.",
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
    title: "Create and receive first POs",
    body: "Save generated PO drafts, mark them sent, and receive them so supplier scorecards become real.",
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
      <div className="kpi-grid kpi-grid-tight">
        <div className="kpi-card">
          <p className="kpi-label">Migration progress</p>
          <p className="kpi-value">{pct}%</p>
          <p className="kpi-note">{completed} of {STEPS.length} steps complete</p>
        </div>
        <div className="kpi-card">
          <p className="kpi-label">Sync posture</p>
          <p className="kpi-value">Read-only</p>
          <p className="kpi-note">No Shopify stock writes without explicit approval.</p>
        </div>
        <div className="kpi-card">
          <p className="kpi-label">Goal</p>
          <p className="kpi-value">First PO</p>
          <p className="kpi-note">Use receipt history to unlock supplier performance.</p>
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
