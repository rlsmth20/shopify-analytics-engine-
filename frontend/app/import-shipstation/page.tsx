"use client";

import Link from "next/link";
import { useState } from "react";

type Velocity = {
  sku: string;
  units_30d: number;
  units_90d: number;
  units_180d: number;
  daily_average_180d: number;
};

type ImportResult = {
  shop_id: number;
  shopify_domain: string;
  rows_processed: number;
  line_items_inserted: number;
  rows_skipped: number;
  skip_reasons: string[];
  distinct_skus: number;
  earliest_ship_date: string | null;
  latest_ship_date: string | null;
  top_skus_by_velocity: Velocity[];
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export default function ImportShipStationPage() {
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
      setError("Please enter your Shopify domain.");
      return;
    }
    if (!file) {
      setError("Please choose your ShipStation export CSV.");
      return;
    }
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("shopify_domain", domain.trim());
      fd.append("csv_file", file);
      const res = await fetch(`${API_BASE}/integrations/shipstation/import`, {
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
        <p className="marketing-eyebrow">ShipStation → slelfly</p>
        <h1 className="marketing-hero-title">
          Bring your shipment history. Stop guessing.
        </h1>
        <p className="marketing-hero-sub">
          Drop in your ShipStation export and we&apos;ll compute your real
          per-SKU velocity, project the next 90 days, and tell you exactly
          which SKUs to reorder before they stock out — instead of a
          trailing six-month average in a Google Sheet.
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
                We use this to create your slelfly workspace. Sell on Amazon
                or eBay too? See the multi-channel note below.
              </p>
            </div>
          </div>

          <div className="import-step">
            <span className="import-step-num">2</span>
            <div className="import-step-body">
              <label htmlFor="file" className="import-label">
                ShipStation orders / shipments CSV
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
                In ShipStation, go to <em>Orders → All Orders → Export</em>{" "}
                (or <em>Reports → Shipments</em>). We read SKU, quantity,
                and ship date from any standard export.
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
                {submitting ? "Crunching the numbers…" : "Compute my velocity"}
              </button>
              <p className="import-help">
                Free during your 14-day trial. You&apos;ll see your top SKUs
                by velocity right after the import lands.
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
                Imported {result.line_items_inserted.toLocaleString()}{" "}
                shipment line items across {result.distinct_skus.toLocaleString()}{" "}
                SKUs.
              </p>
              <ul className="import-success-stats">
                <li>
                  <strong>{result.rows_processed.toLocaleString()}</strong>{" "}
                  rows processed
                </li>
                <li>
                  <strong>{result.line_items_inserted.toLocaleString()}</strong>{" "}
                  line items recorded
                </li>
                {result.rows_skipped > 0 ? (
                  <li>
                    <strong>{result.rows_skipped.toLocaleString()}</strong>{" "}
                    rows skipped
                  </li>
                ) : null}
                {result.earliest_ship_date && result.latest_ship_date ? (
                  <li>
                    Window: <strong>{result.earliest_ship_date}</strong> →{" "}
                    <strong>{result.latest_ship_date}</strong>
                  </li>
                ) : null}
              </ul>

              {result.top_skus_by_velocity.length > 0 ? (
                <div className="import-velocity">
                  <p className="import-velocity-title">
                    Top 10 SKUs by 180-day velocity
                  </p>
                  <table className="import-velocity-table">
                    <thead>
                      <tr>
                        <th>SKU</th>
                        <th>30d</th>
                        <th>90d</th>
                        <th>180d</th>
                        <th>Daily avg</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.top_skus_by_velocity.map((v) => (
                        <tr key={v.sku}>
                          <td>{v.sku}</td>
                          <td>{v.units_30d.toLocaleString()}</td>
                          <td>{v.units_90d.toLocaleString()}</td>
                          <td>{v.units_180d.toLocaleString()}</td>
                          <td>{v.daily_average_180d.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}

              <Link href="/dashboard" className="button button-primary button-lg">
                See ranked actions for these SKUs →
              </Link>
            </div>
          ) : null}
        </form>

        <aside className="import-side">
          <h3 className="import-side-title">Multi-channel?</h3>
          <p className="import-side-note">
            ShipStation typically aggregates orders from Shopify, Amazon,
            eBay, Walmart, and more. That means your import will include
            non-Shopify channels automatically — slelfly&apos;s forecasting
            uses whatever shipped, regardless of source.
          </p>
          <p className="import-side-note">
            Native multi-channel <em>writes</em> (auto-disable Amazon when
            Shopify drains) are on the roadmap. Today, we replace your
            forecasting layer; you keep your channel-sync tool.
          </p>
          <h3 className="import-side-title" style={{ marginTop: 18 }}>
            Already have Stocky data?
          </h3>
          <p className="import-side-note">
            Use the <Link href="/import-stocky">Stocky importer</Link>{" "}
            instead — it pulls SKU, vendor, cost, and on-hand counts.
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
          <Link href="/import-stocky">Stocky import</Link>
          <Link href="/import-shipstation">ShipStation import</Link>
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
