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
  batch_id?: string | null;
  replayed?: boolean;
  duplicate_rows?: number;
  rows_held?: number;
  shopify_rows_excluded?: number;
  invalid_rows?: number;
  hold_reasons?: string[];
  source_scope?: "unknown" | "non_shopify";
};

const API_BASE = APP_API_BASE_URL;

export default function ImportShipStationPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [upgradeNeeded, setUpgradeNeeded] = useState(false);
  const [sourceScope, setSourceScope] = useState<"unknown" | "non_shopify">("unknown");
  const feedback = result ? importFeedback(result) : null;
  const invalidRows = result?.invalid_rows ?? (result?.duplicate_rows === undefined ? result?.rows_skipped ?? 0 : 0);

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
      fd.append("source_scope", sourceScope);
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
                onChange={(e) => { setFile(e.target.files?.[0] ?? null); setSourceScope("unknown"); setResult(null); setError(null); }}
                disabled={submitting}
                required
              />
              <p className="import-help">
                In ShipStation, go to <em>Orders → All Orders → Export</em>.
                Include SKU, quantity, and a ship or order date. For overlapping exports,
                include Shipment ID together with Line Item ID or Order Item ID,
                plus sales-channel or Store ID columns. A generic Item ID alone
                does not identify a unique shipment line. CSV files up to 50 MB and 100,000 data rows.
              </p>
            </div>
          </div>

          <div className="import-step">
            <span className="import-step-num">2</span>
            <div className="import-step-body">
              <label htmlFor="shipment-source-scope" className="import-label">Which sales channels are in this file?</label>
              <select id="shipment-source-scope" className="input-control import-input" style={{ maxWidth: "100%", minWidth: 0 }}
                value={sourceScope} disabled={submitting} aria-describedby="shipment-source-help"
                onChange={(event) => { setSourceScope(event.target.value as "unknown" | "non_shopify"); setResult(null); setError(null); }}>
                <option value="unknown">Mixed channels, or I’m unsure</option>
                <option value="non_shopify">Only non-Shopify orders</option>
              </select>
              <p id="shipment-source-help" className="import-help">Choose “Only non-Shopify orders” only if you have checked that the export excludes Shopify orders. Otherwise, rows without a clear sales channel are held for review. Recognized Shopify rows are always excluded here to avoid counting the same sales through both imports.</p>
            </div>
          </div>

          <div className="import-step">
            <span className="import-step-num">3</span>
            <div className="import-step-body">
              <button type="submit" className="button button-primary button-lg" disabled={submitting}>
                {submitting ? "Checking shipment history…" : "Check and import shipment history"}
              </button>
            </div>
          </div>

          {error ? (
            <div className="import-error" role="alert"><strong>Import not confirmed.</strong> {error}{upgradeNeeded ? <> <Link href="/billing">Review your plan</Link></> : null}</div>
          ) : null}

          {result && feedback ? (
            <div className={feedback.tone === "success" ? "import-success" : feedback.tone === "error" ? "import-error" : "sync-safety-note"} role={feedback.tone === "error" ? "alert" : "status"}>
              <p className="import-success-title">
                {feedback.title}
              </p>
              <ul className="import-success-stats">
                <li><strong>{result.rows_processed.toLocaleString()}</strong> rows processed</li>
                <li><strong>{result.line_items_inserted.toLocaleString()}</strong> newly imported</li>
                <li><strong>{result.rows_skipped.toLocaleString()}</strong> not added in total</li>
                {result.duplicate_rows !== undefined ? <li><strong>{result.duplicate_rows.toLocaleString()}</strong> already recorded</li> : null}
                {result.rows_held !== undefined ? <li><strong>{result.rows_held.toLocaleString()}</strong> held for review</li> : null}
                {result.shopify_rows_excluded !== undefined ? <li><strong>{result.shopify_rows_excluded.toLocaleString()}</strong> Shopify rows excluded</li> : null}
                {result.invalid_rows !== undefined ? <li><strong>{result.invalid_rows.toLocaleString()}</strong> invalid rows</li> : null}
                {result.line_items_inserted > 0 && result.earliest_ship_date && result.latest_ship_date ? (
                  <li>Newly imported window: <strong>{result.earliest_ship_date}</strong> → <strong>{result.latest_ship_date}</strong></li>
                ) : null}
              </ul>
              {result.duplicate_rows !== undefined ? <p className="import-help">The “not added” total includes already recorded, held, Shopify, and invalid rows. These rows do not increase your sales totals.</p> : null}
              {result.duplicate_rows === undefined ? <p className="import-help">This result does not report duplicate or overlap checks. Only the added and skipped totals are confirmed. Review earlier imports and Shopify history before adding more shipments.</p> : null}
              {(result.rows_held ?? 0) > 0 ? <div>
                <p><strong>Held rows have not been added.</strong> Their source or possible overlap needs review.</p>
                <ul>{(result.hold_reasons ?? []).map((reason, index) => <li key={`${index}-${reason}`}>{reason}</li>)}</ul>
                <p>If the issue is an unknown sales channel, check the export. Choose “Only non-Shopify orders” and submit it again only if that statement is true. For missing identifiers or possible historical overlap, include more source details or <a href="mailto:info@skubase.io?subject=ShipStation%20held%20rows">ask us to review the issue</a>.</p>
              </div> : null}
              {invalidRows > 0 ? <div><p>Review the reported row issues before using the results:</p><ul>{result.skip_reasons.map((reason, index) => <li key={`${index}-${reason}`}>{reason}</li>)}</ul>{result.skip_reasons.length === 0 ? <p>No row details were provided. Check that the export includes SKU, positive quantity, and a valid ship or order date.</p> : <p>The import reports up to 10 example issues.</p>}</div> : null}
              {(result.shopify_rows_excluded ?? 0) > 0 ? <p>Shopify rows were left out to keep them separate from Shopify sync. <Link href="/store-sync">Check Shopify access and sync</Link>, or <Link href="/tools/inventory-health-check">use the free inventory health check</Link> while the app is in review.</p> : null}

              {result.line_items_inserted > 0 && !result.replayed && result.top_skus_by_velocity.length > 0 ? (
                <div className="import-velocity">
                  <p className="import-velocity-title">Most-shipped SKUs in the newly imported rows</p>
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
              </> : (result.rows_held ?? 0) > 0 ? <p>No new shipment history was added. Resolve the held-row issues before relying on this file for demand planning.</p>
                : invalidRows > 0 ? <p>Check the export and the reported row issues, then choose a corrected CSV. No new shipment history is available from this upload.</p>
                : (result.duplicate_rows ?? 0) > 0 ? <p>No repeat shipment rows were added. You can <Link href="/actions">review your existing inventory actions</Link>. Earlier imports have not been changed.</p>
                : <p>No new shipment history was added by this upload.</p>}
            </div>
          ) : null}
        </form>

        <aside className="import-side">
          <h3 className="import-side-title">What this import adds</h3>
          <p className="import-side-note">
            Eligible shipments from this export add sales history for matching SKUs.
            Recognized repeat rows are skipped. Shopify orders and uncertain
            overlaps are not added. Older imports are not changed by this upload.
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
  const breakdownKeys = ["duplicate_rows", "rows_held", "shopify_rows_excluded", "invalid_rows"];
  if (breakdownKeys.some(key => key in result && !count(result[key]))) return false;
  if ("replayed" in result && typeof result.replayed !== "boolean") return false;
  if (result.replayed === true && result.line_items_inserted !== 0) return false;
  if ("hold_reasons" in result && (!Array.isArray(result.hold_reasons) || !result.hold_reasons.every(reason => typeof reason === "string"))) return false;
  if ("source_scope" in result && result.source_scope !== "unknown" && result.source_scope !== "non_shopify") return false;
  if (breakdownKeys.every(key => count(result[key]))) {
    const excluded = breakdownKeys.reduce((sum, key) => sum + Number(result[key]), 0);
    if (excluded !== result.rows_skipped || excluded + Number(result.line_items_inserted) !== result.rows_processed) return false;
  }
  return ["rows_processed", "line_items_inserted", "rows_skipped", "distinct_skus"].every((key) => count(result[key]))
    && Array.isArray(result.skip_reasons) && result.skip_reasons.every((reason) => typeof reason === "string")
    && ["earliest_ship_date", "latest_ship_date"].every((key) => result[key] === null || typeof result[key] === "string")
    && Array.isArray(result.top_skus_by_velocity) && result.top_skus_by_velocity.every((item) => item && typeof item === "object"
      && typeof item.sku === "string" && [item.units_30d, item.units_90d, item.units_180d].every(count)
      && typeof item.daily_average_180d === "number" && Number.isFinite(item.daily_average_180d) && item.daily_average_180d >= 0);
}

function importFeedback(result: ImportResult): { tone: "success" | "review" | "error"; title: string } {
  const needsReview = (result.rows_held ?? 0) > 0 || (result.invalid_rows ?? (result.duplicate_rows === undefined ? result.rows_skipped : 0)) > 0;
  if (result.replayed) return { tone: "review", title: "This file was already checked. No new shipment rows were added." };
  if (result.line_items_inserted > 0) return { tone: needsReview ? "review" : "success", title: `Imported ${result.line_items_inserted.toLocaleString()} shipment line item${result.line_items_inserted === 1 ? "" : "s"} across ${result.distinct_skus} SKU${result.distinct_skus === 1 ? "" : "s"}.` };
  if ((result.rows_held ?? 0) > 0) return { tone: "review", title: "Shipment rows need review. Nothing new was imported." };
  if ((result.duplicate_rows ?? 0) > 0 || (result.shopify_rows_excluded ?? 0) > 0) return { tone: "review", title: "Import check complete. No new shipment rows were added." };
  return { tone: "error", title: "No shipment rows were imported." };
}
