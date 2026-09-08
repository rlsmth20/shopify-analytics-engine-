import Link from "next/link";

/** This public tool remains usable when account data or connection reads fail. */
export function BrowserHealthCheckOption() {
  return <aside className="sync-safety-note" aria-label="Free browser inventory health check">
    <Link className="button button-secondary" href="/tools/inventory-health-check">Free inventory health check</Link>
    <p className="section-copy" style={{ marginTop: 8 }}>
      Bring a summary with SKU, on_hand and units_sold, then set the sales period in days.
      This browser-only check does not import data or results into your account.
    </p>
  </aside>;
}
