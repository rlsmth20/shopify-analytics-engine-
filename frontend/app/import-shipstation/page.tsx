"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { authenticatedFetch, getEmbeddedShopifyContext, redirectToShopifyInstall } from "@/lib/shopify-embedded";
import { MarketingFooter } from "@/components/marketing-footer";

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

const API_BASE = APP_API_BASE_URL;

export default function ImportShipStationPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [upgradeNeeded, setUpgradeNeeded] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setUpgradeNeeded(false);
    const fileError = shipmentFileError(file);
    if (fileError || !file) return setError(fileError);
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("csv_file", file);
      const res = await authenticatedFetch(`${API_BASE}/integrations/shipstation/import`, {
        method: "POST",
        body: fd,
        credentials: "include",
      });
      if (res.status === 401) {
        if (getEmbeddedShopifyContext()) redirectToShopifyInstall();
        else router.replace(`/login?return_to=${encodeURIComponent("/import-shipstation")}`);
        return;
      }
      const body = await res.json().catch(() => null);
      if (res.status === 402) setUpgradeNeeded(true);
      if (!res.ok) throw new Error(typeof body?.detail === "string" ? body.detail : `Import failed (${res.status}).`);
      if (!isImportResult(body)) throw new Error("The import result could not be confirmed. Check your workspace before uploading the same file again.");
      setResult(body);
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
          <span className="marketing-brand-mark">sb</span>
          <span className="marketing-brand-name">skubase</span>
        </Link>
        <nav className="marketing-nav-links" aria-label="Primary">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/blog">Blog</Link>
        </nav>
      </header>

      <section className="marketing-hero marketing-hero-migration">
        <p className="marketing-eyebrow">ShipStation → skubase</p>
        <h1 className="marketing-hero-title">Add shipment history to your inventory plan.</h1>
        <p className="marketing-hero-sub">
          Import a ShipStation export to review units shipped by SKU. Combine it
          with current inventory and supplier lead times in Skubase before relying
          on stockout estimates or reorder quantities.
        </p>
      </section>

      <section className="import-card-wrap">
        <form className="import-card" onSubmit={handleSubmit}>
          <div className="import-step">
            <span className="import-step-num">1</span>
            <div className="import-step-body">
              <label htmlFor="file" className="import-label">ShipStation orders/shipments CSV</label>
              <input
                id="file"
                type="file"
                accept=".csv,text/csv"
                className="input-control import-input"
                onChange={(e) => { setFile(e.target.files?.[0] ?? null); setResult(null); setError(null); }}
                disabled={submitting}
                required
              />
              <p className="import-help">
                In ShipStation, go to <em>Orders → All Orders → Export</em>.
                Include SKU, quantity, and a ship or order date. CSV files up to 50 MB.
              </p>
            </div>
          </div>

          <div className="import-step">
            <span className="import-step-num">2</span>
            <div className="import-step-body">
              <button type="submit" className="button button-primary button-lg" disabled={submitting}>
                {submitting ? "Importing shipment history…" : "Import shipment history"}
              </button>
            </div>
          </div>

          {error ? (
            <div className="import-error" role="alert"><strong>Import not confirmed.</strong> {error}{upgradeNeeded ? <> <Link href="/billing">Review your plan</Link></> : null}</div>
          ) : null}

          {result ? (
            <div className={result.line_items_inserted > 0 ? "import-success" : "import-error"} role={result.line_items_inserted > 0 ? "status" : "alert"}>
              <p className="import-success-title">
                {result.line_items_inserted > 0
                  ? `Imported ${result.line_items_inserted.toLocaleString()} shipment line items across ${result.distinct_skus} SKUs.`
                  : "No shipment rows were imported."}
              </p>
              <ul className="import-success-stats">
                <li><strong>{result.rows_processed.toLocaleString()}</strong> rows processed</li>
                <li><strong>{result.line_items_inserted.toLocaleString()}</strong> recorded</li>
                <li><strong>{result.rows_skipped.toLocaleString()}</strong> skipped</li>
                {result.earliest_ship_date && result.latest_ship_date ? (
                  <li>Window: <strong>{result.earliest_ship_date}</strong> → <strong>{result.latest_ship_date}</strong></li>
                ) : null}
              </ul>
              {result.rows_skipped > 0 ? <div><p>Some rows could not be imported. Review these reported issues before using the results:</p><ul>{result.skip_reasons.map((reason, index) => <li key={`${index}-${reason}`}>{reason}</li>)}</ul>{result.skip_reasons.length === 0 ? <p>No row details were provided. Check that the export includes SKU, positive quantity, and a valid ship or order date.</p> : <p>The import reports up to 10 example issues.</p>}</div> : null}

              {result.top_skus_by_velocity.length > 0 ? (
                <div className="import-velocity">
                  <p className="import-velocity-title">Most-shipped SKUs in this file</p>
                  <p className="import-help">The 30, 90, and 180-day windows end on {result.latest_ship_date ?? "the latest shipment date in the file"}, not today. Daily average uses a 180-day window. This does not measure current stock.</p>
                  <table className="import-velocity-table">
                    <thead><tr><th>SKU</th><th>30d</th><th>90d</th><th>180d</th><th>Daily avg</th></tr></thead>
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

              {result.line_items_inserted > 0 ? <>
                <p><strong>Next: make sure current inventory is available.</strong> Shipment history does not include stock on hand. Import a Stocky inventory export with matching SKUs, or sync Shopify if you already have app access, then check supplier lead times.</p>
                <div className="button-row">
                  <Link href="/import-stocky" className="button button-primary">Add current inventory</Link>
                  <Link href="/store-sync" className="button button-ghost">Check imports & Shopify access</Link>
                </div>
                <p className="import-help">Already added current inventory? <Link href="/lead-time-settings">Check lead times</Link>, then <Link href="/actions">review inventory actions</Link>.</p>
              </> : <p>Check the export and the reported row issues, then choose a corrected CSV. No new shipment history is available from this upload.</p>}
            </div>
          ) : null}
        </form>

        <aside className="import-side">
          <h3 className="import-side-title">What this import adds</h3>
          <p className="import-side-note">
            Only the shipments in your selected export are imported. Match the SKU
            values to your inventory catalog. To avoid counting sales twice, do not
            include shipments whose orders are already imported through Shopify
            or an earlier CSV upload.
          </p>
          <p className="import-help">Need stock quantities too? <Link href="/import-stocky">Import Stocky current inventory</Link>. Skubase is in Shopify App Store review and is not listed yet; CSV imports are available now.</p>
          <p className="import-help" style={{ marginTop: "16px" }}>
            You need to be signed in to import. <Link href="/login?return_to=%2Fimport-shipstation">Sign in</Link> if you haven&apos;t already.
          </p>
        </aside>
      </section>

      <MarketingFooter />
    </div>
  );
}

function shipmentFileError(file: { name: string; size: number } | null): string | null {
  if (!file) return "Please choose your ShipStation CSV.";
  if (!file.name.toLowerCase().endsWith(".csv")) return "Choose a .csv file exported from ShipStation.";
  if (file.size === 0) return "That CSV is empty. Export your shipment history and try again.";
  if (file.size > 50 * 1024 * 1024) return "This CSV is larger than 50 MB. Export a smaller date range before importing.";
  return null;
}

function isImportResult(value: unknown): value is ImportResult {
  if (!value || typeof value !== "object") return false;
  const result = value as Record<string, unknown>;
  const count = (number: unknown) => typeof number === "number" && Number.isSafeInteger(number) && number >= 0;
  return ["rows_processed", "line_items_inserted", "rows_skipped", "distinct_skus"].every((key) => count(result[key]))
    && Array.isArray(result.skip_reasons) && result.skip_reasons.every((reason) => typeof reason === "string")
    && ["earliest_ship_date", "latest_ship_date"].every((key) => result[key] === null || typeof result[key] === "string")
    && Array.isArray(result.top_skus_by_velocity) && result.top_skus_by_velocity.every((item) => item && typeof item === "object"
      && typeof item.sku === "string" && [item.units_30d, item.units_90d, item.units_180d].every(count)
      && typeof item.daily_average_180d === "number" && Number.isFinite(item.daily_average_180d) && item.daily_average_180d >= 0);
}
