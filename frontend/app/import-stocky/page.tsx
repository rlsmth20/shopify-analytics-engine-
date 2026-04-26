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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

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
    if (!domain.trim()) return setError("Please enter your Shopify domain.");
    if (!file) return setError("Please choose your Stocky CSV.");
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("shopify_domain", domain.trim());
      fd.append("csv_file", file);
      const res = await fetch(`${API_BASE}/integrations/stocky/import`, { method: "POST", body: fd });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.detail || `Import failed (${res.status}).`);
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
          <Link href="/blog">Blog</Link>
          <Link href="/changelog">Changelog</Link>
        </nav>
      </header>

      <section className="marketing-hero marketing-hero-migration">
        <p className="marketing-eyebrow">Stocky migration</p>
        <h1 className="marketing-hero-title">Move your Stocky catalog to slelfly.</h1>
        <p className="marketing-hero-sub">
          Upload your Stocky products CSV and we&apos;ll create your slelfly workspace, import your SKUs, vendors, and inventory.
        </p>
      </section>

      <section className="import-card-wrap">
        <form className="import-card" onSubmit={handleSubmit}>
          <div className="import-step">
            <span className="import-step-num">1</span>
            <div className="import-step-body">
              <label htmlFor="domain" className="import-label">Your Shopify domain</label>
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
            </div>
          </div>

          <div className="import-step">
            <span className="import-step-num">2</span>
            <div className="import-step-body">
              <label htmlFor="file" className="import-label">Stocky products CSV</label>
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
                In Stocky, go to <em>Reports → Inventory On Hand</em> and export.
              </p>
            </div>
          </div>

          <div className="import-step">
            <span className="import-step-num">3</span>
            <div className="import-step-body">
              <button type="submit" className="button button-primary button-lg" disabled={submitting}>
                {submitting ? "Importing…" : "Start import"}
              </button>
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
                Imported {result.products_inserted + result.products_updated} products.
              </p>
              <ul className="import-success-stats">
                <li><strong>{result.products_processed}</strong> rows processed</li>
                <li><strong>{result.products_inserted}</strong> new products</li>
                <li><strong>{result.products_updated}</strong> updated</li>
                <li><strong>{result.inventory_rows_inserted}</strong> inventory rows</li>
                {result.rows_skipped > 0 ? (
                  <li><strong>{result.rows_skipped}</strong> rows skipped</li>
                ) : null}
              </ul>
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
            <li>The action engine ranks them within seconds.</li>
            <li>Set vendor lead times on the <Link href="/lead-time-settings">Lead Times</Link> page.</li>
            <li>Connect Shopify on the <Link href="/store-sync">Store Sync</Link> page when ready.</li>
          </ol>
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
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>
        <p className="marketing-footer-fine">© {new Date().getFullYear()} slelfly</p>
      </footer>
    </div>
  );
}
