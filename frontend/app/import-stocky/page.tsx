"use client";

import Link from "next/link";
import { useState } from "react";

type ImportResult = {
  shop_id: number;
  shopify_domain: string;
  products_processed: number;
  products_inserted: number;
  products_updated: number;
  inventory_rows_inserted: number;
  rows_skipped: number;
  skip_reasons: string[];
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export default function ImportStockyPage() {
  const [domain, setDomain] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    if (!domain.trim()) {
      setError("Please enter your Shopify domain (e.g. yourshop.myshopify.com).");
      return;
    }
    if (!file) {
      setError("Please choose your Stocky products CSV file.");
      return;
    }
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("shopify_domain", domain.trim());
      fd.append("csv_file", file);
      const res = await fetch(`${API_BASE}/integrations/stocky/import`, {
        method: "POST",
        body: fd,
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(body?.detail || `Import failed (${res.status}).`);
      }
      setResult(body as ImportResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="marketing-shell">
      <header className="marketing-nav">
        <Link href="/" className="marketing-brand">
          <span className="marketing-brand-mark">sf</span>
          <span className="marketing-brand-name">slelfly</span>
        </Link>
        <nav className="marketing-nav-links" aria-label="Primary">
          <Link href="/#pillars">Product</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/about">About</Link>
          <Link href="/changelog">Changelog</Link>
        </nav>
        <div className="marketing-nav-ctas">
          <Link href="/login" className="marketing-link-subtle">
            Sign in
          </Link>
          <Link href="/dashboard" className="button button-primary">
            Open app
          </Link>
        </div>
      </header>

      <section className="marketing-hero marketing-hero-migration">
        <p className="marketing-eyebrow">Stocky migration</p>
        <h1 className="marketing-hero-title">
          Move your Stocky catalog to slelfly.
        </h1>
        <p className="marketing-hero-sub">
          Upload your Stocky products CSV and we&apos;ll create your slelfly
          workspace, import your SKUs, vendors, and inventory, and surface
          your first ranked action — usually in under a minute.
        </p>
      </section>

      <section className="import-card-wrap">
        <form className="import-card" onSubmit={handleSubmit}>
          <div className="import-step">
            <span className="import-step-num">1</span>
            <div className="import-step-body">
              <label htmlFor="domain" className="import-label">
                Your Shopify domain
              </label>
              <input
                id="domain"
                type="text"
                className="input-control import-input"
                placeholder="yourshop.myshopify.com"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                disabled={submitting}
                required
              />
              <p className="import-help">
                Enter the full myshopify.com domain. We&apos;ll create your
                workspace under this name.
              </p>
            </div>
          </div>

          <div className="import-step">
            <span className="import-step-num">2</span>
            <div className="import-step-body">
              <label htmlFor="file" className="import-label">
                Stocky products CSV
              </label>
              <input
                id="file"
                type="file"
                accept=".csv,text/csv"
                className="input-control import-input"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                disabled={submitting}
                required
              />
              <p className="import-help">
                In Stocky, go to <em>Reports → Inventory On Hand</em> and
                export the CSV. We accept Stocky&apos;s standard column names
                (SKU, Product, Vendor, Cost, Price, Inventory).
              </p>
            </div>
          </div>

          <div className="import-step">
            <span className="import-step-num">3</span>
            <div className="import-step-body">
              <button
                type="submit"
                className="button button-primary button-lg"
                disabled={submitting}
              >
                {submitting ? "Importing…" : "Start import"}
              </button>
              <p className="import-help">
                Free during your 14-day trial. We never charge for the
                import itself.
              </p>
            </div>
          </div>

          {error ? (
            <div className="import-error" role="alert">
              <strong>Import failed.</strong> {error}
            </div>
          ) : null}

          {result ? (
            <div className="import-success" role="status">
              <p className="import-success-title">
                Imported {result.products_inserted + result.products_updated}{" "}
                products into your slelfly workspace.
              </p>
              <ul className="import-success-stats">
                <li>
                  <strong>{result.products_processed}</strong> rows processed
                </li>
                <li>
                  <strong>{result.products_inserted}</strong> new products
                  created
                </li>
                <li>
                  <strong>{result.products_updated}</strong> existing products
                  updated
                </li>
                <li>
                  <strong>{result.inventory_rows_inserted}</strong> inventory
                  rows added
                </li>
                {result.rows_skipped > 0 ? (
                  <li>
                    <strong>{result.rows_skipped}</strong> rows skipped
                  </li>
                ) : null}
              </ul>
              {result.skip_reasons.length > 0 ? (
                <details className="import-skip-details">
                  <summary>Skipped row reasons</summary>
                  <ul>
                    {result.skip_reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </details>
              ) : null}
              <Link href="/dashboard" className="button button-primary button-lg">
                Open my dashboard →
              </Link>
            </div>
          ) : null}
        </form>

        <aside className="import-side">
          <h3 className="import-side-title">What happens next</h3>
          <ol className="import-side-list">
            <li>Your products land in slelfly&apos;s catalog.</li>
            <li>
              The action engine ranks them — urgent reorders, overstock, dead
              stock — within seconds.
            </li>
            <li>
              Set vendor lead times on the{" "}
              <Link href="/lead-time-settings">Lead Times</Link> page (your
              Stocky lead-time exports import in a separate step).
            </li>
            <li>
              Connect Shopify on the{" "}
              <Link href="/store-sync">Store Sync</Link> page when you&apos;re
              ready to switch off Stocky entirely.
            </li>
          </ol>
          <p className="import-side-note">
            Need a hand? Email{" "}
            <a href="mailto:hello@slelfly.com">hello@slelfly.com</a> and a
            human will help.
          </p>
        </aside>
      </section>

      <footer className="marketing-footer">
        <div className="marketing-footer-brand">
          <span className="marketing-brand-mark">sf</span>
          <span>slelfly</span>
        </div>
        <div className="marketing-footer-links">
          <Link href="/">Home</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/about">About</Link>
          <Link href="/changelog">Changelog</Link>
          <Link href="/goodbye-stocky">Stocky migration</Link>
          <Link href="/goodbye-genie">Genie migration</Link>
          <Link href="/login">Sign in</Link>
        </div>
        <p className="marketing-footer-fine">
          © {new Date().getFullYear()} slelfly · Independent · Founder-led ·
          Prices locked at renewal
        </p>
      </footer>
    </div>
  );
}
