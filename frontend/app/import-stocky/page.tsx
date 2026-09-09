"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { MarketingFooter } from "@/components/marketing-footer";

import {
  authenticatedFetch,
  getEmbeddedShopifyContext,
  isEmbeddedShopifyContext,
  redirectToShopifyInstall,
} from "@/lib/shopify-embedded";

type ImportResult = {
  shop_id: number;
  shopify_domain: string;
  products_processed: number;
  products_inserted: number;
  products_updated: number;
  inventory_rows_inserted: number;
  rows_skipped: number;
  skip_reasons: string[];
  inventory_source?: "shopify" | "csv";
  inventory_rows_skipped?: number;
  warnings?: string[];
};

const API_BASE = APP_API_BASE_URL;
const MAX_CSV_BYTES = 25 * 1024 * 1024;

function isImportResult(value: unknown): value is ImportResult {
  if (!value || typeof value !== "object") return false;
  const result = value as Record<string, unknown>;
  const counts = ["shop_id", "products_processed", "products_inserted", "products_updated", "inventory_rows_inserted", "rows_skipped"];
  if (!counts.every((key) => typeof result[key] === "number" && Number.isSafeInteger(result[key]) && Number(result[key]) >= 0) ||
    typeof result.shopify_domain !== "string" || !Array.isArray(result.skip_reasons) ||
    !result.skip_reasons.every((reason) => typeof reason === "string")) return false;
  if (result.inventory_source !== undefined && !["shopify", "csv"].includes(String(result.inventory_source))) return false;
  if (result.inventory_rows_skipped !== undefined && (!Number.isSafeInteger(result.inventory_rows_skipped) || Number(result.inventory_rows_skipped) < 0)) return false;
  if (result.warnings !== undefined && (!Array.isArray(result.warnings) || !result.warnings.every((warning) => typeof warning === "string"))) return false;
  return true;
}

export default function ImportStockyPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [upgradeNeeded, setUpgradeNeeded] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [embedded, setEmbedded] = useState(false);

  useEffect(() => {
    setEmbedded(isEmbeddedShopifyContext());
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setUpgradeNeeded(false);
    setResult(null);
    if (!file) return setError("Please choose your Stocky CSV.");
    if (!file.name.toLowerCase().endsWith(".csv")) {
      return setError("Please upload a .csv file exported from Stocky.");
    }
    if (file.size === 0) {
      return setError("That CSV is empty. Export Inventory On Hand from Stocky and try again.");
    }
    if (file.size > MAX_CSV_BYTES) {
      return setError(
        "That CSV is larger than 25 MB. Export a smaller Stocky file or split the export before importing."
      );
    }
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("csv_file", file);
      const res = await postStockyImport(fd);
      if (res.status === 401) {
        if (getEmbeddedShopifyContext()) {
          redirectToShopifyInstall();
        } else {
          router.replace(`/login?return_to=${encodeURIComponent("/import-stocky")}`);
        }
        return;
      }
      const body = await res.json().catch(() => null);
      if (res.status === 402) {
        setUpgradeNeeded(true);
        setError(body?.detail || "Your trial has ended. Subscribe to continue using skubase.");
        return;
      }
      if (!res.ok) throw new Error(body?.detail || `Import failed (${res.status}).`);
      if (!isImportResult(body)) throw new Error("The import result could not be confirmed. Check your catalog before uploading again, or contact info@skubase.io for help.");
      setResult(body);
    } catch (err) {
      setError(importErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="marketing-shell">
      {embedded ? null : (
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
      )}

      <section className="marketing-hero marketing-hero-migration">
        <p className="marketing-eyebrow">Stocky migration</p>
        <h1 className="marketing-hero-title">Move your Stocky catalog to skubase.</h1>
        <p className="marketing-hero-sub">
          Import product details from your Stocky CSV. If Shopify is connected or its catalog is already synced, Shopify remains the source for stock on hand.
        </p>
      </section>

      <section className="import-card-wrap">
        <form className="import-card" onSubmit={handleSubmit}>
          <div className="import-step">
            <span className="import-step-num">1</span>
            <div className="import-step-body">
              <label htmlFor="file" className="import-label">Stocky products CSV</label>
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
                In Stocky, go to <em>Reports → Inventory On Hand</em> and export.
              </p>
            </div>
          </div>

          <div className="import-step">
            <span className="import-step-num">2</span>
            <div className="import-step-body">
              <button type="submit" className="button button-primary button-lg" disabled={submitting}>
                {submitting ? "Importing…" : "Start import"}
              </button>
            </div>
          </div>

          {error ? (
            <div className="import-error" role="alert">
                <strong>Import needs attention.</strong> {error}
              {upgradeNeeded ? (
                <>
                  {" "}
                  <Link href="/billing" className="auth-link">
                    Open billing
                  </Link>
                </>
              ) : null}
            </div>
          ) : null}

          {result ? (
            <div className="import-success" role={result.products_inserted + result.products_updated > 0 ? "status" : "alert"}>
              <p className="import-success-title">
                {result.products_inserted + result.products_updated > 0
                  ? `Imported or updated ${result.products_inserted + result.products_updated} product records.`
                  : "No product records changed."}
              </p>
              {result.inventory_source === "shopify" ? <p className="import-help">Shopify stock on hand was preserved. This CSV can update matching product details, such as costs and lead times, but does not add another inventory count.</p> : null}
              {result.inventory_source === "csv" ? <p className="import-help">Stock on hand comes from this CSV snapshot. Keep it up to date; this file does not include sales history.</p> : null}
              <ul className="import-success-stats">
                <li><strong>{result.products_processed}</strong> rows processed</li>
                <li><strong>{result.products_inserted}</strong> new products</li>
                <li><strong>{result.products_updated}</strong> updated</li>
                <li><strong>{result.inventory_rows_inserted}</strong> new inventory records</li>
                {typeof result.inventory_rows_skipped === "number" && result.inventory_rows_skipped > 0 ? <li><strong>{result.inventory_rows_skipped}</strong> inventory rows kept unchanged</li> : null}
                {result.rows_skipped > 0 ? (
                  <li><strong>{result.rows_skipped}</strong> rows skipped</li>
                ) : null}
              </ul>
              {result.warnings?.length ? <ul className="import-help">{result.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul> : null}
              {result.skip_reasons.length ? <details className="import-help" open={result.products_inserted + result.products_updated === 0}><summary>Review skipped rows</summary><ul>{result.skip_reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul></details> : null}
              <div className="button-row">
                <Link href={result.inventory_source === "shopify" ? "/store-sync" : "/dashboard"} className="button button-primary button-lg">
                  {result.inventory_source === "shopify" ? "Check Shopify sync" : "Review my inventory"}
                </Link>
                <a href="mailto:info@skubase.io" className="button button-secondary">Get import help</a>
              </div>
            </div>
          ) : null}
        </form>

        <aside className="import-side">
          <h3 className="import-side-title">What happens next</h3>
          <ol className="import-side-list">
            <li>Review which products were imported, updated, or skipped.</li>
            <li>Reorder recommendations also need usable sales history. A stock snapshot alone cannot establish demand.</li>
            <li>Set vendor lead times on the <Link href="/lead-time-settings">Lead Times</Link> page.</li>
            <li>Connect Shopify on the <Link href="/store-sync">Store Sync</Link> page when ready.</li>
          </ol>
          {embedded ? null : (
            <p className="import-help" style={{ marginTop: "16px" }}>
          You need to be signed in to import. <Link href="/login?return_to=%2Fimport-stocky">Sign in</Link> if you haven&apos;t already.
            </p>
          )}
        </aside>
      </section>

      {embedded ? null : (
      <MarketingFooter />
      )}
    </div>
  );
}

async function postStockyImport(formData: FormData): Promise<Response> {
  const embedded = getEmbeddedShopifyContext() !== null;
  const primaryUrl = embedded ? "/api/stocky-import" : `${API_BASE}/integrations/stocky/import`;
  return authenticatedFetch(primaryUrl, { method: "POST", body: formData, credentials: "include" });
}

function importErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (isNetworkFetchError(error)) {
    return (
      "The connection ended before we could confirm the import result. It may already have been saved. " +
      "Check your catalog before uploading again, or contact info@skubase.io with your store domain and CSV file size."
    );
  }
  return message;
}

function isNetworkFetchError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return /failed to fetch|networkerror|load failed/i.test(message);
}
