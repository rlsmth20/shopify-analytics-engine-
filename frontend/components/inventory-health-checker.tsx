"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { trackGrowthEvent } from "@/lib/analytics";
import { analyzeInventoryHealth, containsSampleHealthRows, HEALTH_CHECK_MAX_BYTES, HEALTH_CHECK_TEMPLATE, HEALTH_STATUS, healthResultsCsv,
  type HealthRow, type HealthSettings, type HealthStatus } from "@/lib/inventory-health-check";
import styles from "./inventory-health-checker.module.css";

const number = (n: number) => n.toLocaleString(undefined, { maximumFractionDigits: 1 });
const statuses = Object.keys(HEALTH_STATUS) as HealthStatus[];

function download(text: string, name: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1_000);
}

export function InventoryHealthChecker() {
  const [csv, setCsv] = useState("");
  const [settings, setSettings] = useState({ salesDays: "30", defaultLeadDays: "14", targetCoverDays: "60" });
  const [currency, setCurrency] = useState("USD");
  const [rows, setRows] = useState<HealthRow[] | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [sample, setSample] = useState(false);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<HealthStatus | "all">("all");
  const [shown, setShown] = useState(50);
  const [loading, setLoading] = useState(false);
  const filtered = useMemo(() => (rows || []).filter(row => (filter === "all" || row.status === filter) &&
    row.sku.toLowerCase().includes(search.trim().toLowerCase())), [rows, filter, search]);
  const totals = useMemo(() => {
    const counts = Object.fromEntries(statuses.map(s => [s, 0])) as Record<HealthStatus, number>;
    let knownExcessCost = 0, missingCost = 0;
    for (const row of rows || []) {
      counts[row.status]++;
      if ((row.excessUnits ?? 0) > 0) {
        if (row.excessCost === null) missingCost++;
        else knownExcessCost += row.excessCost;
      }
    }
    return { counts, knownExcessCost, missingCost };
  }, [rows]);
  const money = (n: number) => new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: n > 0 && n < 100 ? 2 : 0 }).format(n);
  const invalidate = () => { setRows(null); setErrors([]); };

  return <div className={styles.checker}>
    <form className={styles.form} onSubmit={event => {
      event.preventDefault();
      const numeric = Object.fromEntries(Object.entries(settings).map(([key, value]) => [key, Number(value)])) as HealthSettings;
      const result = analyzeInventoryHealth(csv, numeric);
      const isSample = sample || containsSampleHealthRows(result.rows);
      setSample(isSample);
      setErrors(result.errors); setRows(result.errors.length ? null : result.rows);
      setFilter("all"); setSearch(""); setShown(50);
      // Sample runs are product demonstrations, not merchant acquisition evidence.
      if (!result.errors.length && !isSample) void trackGrowthEvent("CALCULATOR_USED");
    }}>
      <div className={styles.stepHeading}><span>1</span><div><h2>Start with a SKU summary</h2><p>No account or app installation required. Your SKU entries are processed in this browser and are not sent to Skubase.</p></div></div>
      <div className={styles.toolbar}>
        <button type="button" className="button button-secondary" onClick={() => { setCsv(HEALTH_CHECK_TEMPLATE); setSample(true); invalidate(); }}>Try sample data</button>
        <button type="button" className="button button-ghost" onClick={() => download(HEALTH_CHECK_TEMPLATE, "skubase-inventory-summary-template.csv")}>Download template</button>
        <label className={styles.fileLabel}>Choose a CSV<input type="file" accept=".csv,text/csv" disabled={loading} onChange={async event => {
          const file = event.target.files?.[0];
          if (!file) return;
          invalidate();
          if (file.size > HEALTH_CHECK_MAX_BYTES) { setErrors(["Choose a CSV smaller than 500 KB."]); event.target.value = ""; return; }
          setLoading(true);
          try { setCsv(await file.text()); setSample(false); }
          catch { setErrors(["Could not read that file. Try pasting its summary below."]); }
          finally { setLoading(false); }
        }} /></label>
      </div>
      <label className={styles.csvLabel} htmlFor="health-summary">Or paste CSV summary data</label>
      <textarea id="health-summary" value={csv} rows={7} spellCheck={false} placeholder="sku,on_hand,units_sold,unit_cost,lead_time_days,safety_stock" onChange={event => { setCsv(event.target.value); setSample(false); invalidate(); }} aria-describedby="health-columns" />
      <p id="health-columns" className={styles.hint}><strong>Required:</strong> sku, on_hand, units_sold. <strong>Optional:</strong> unit_cost, lead_time_days, safety_stock. Use units sold over the same period for every SKU. Aggregate raw order exports first; omit customer details. Up to 1,000 unique SKUs.</p>
      <div className={styles.stepHeading}><span>2</span><div><h2>Choose the planning assumptions</h2><p>Use a representative sales period and include production, transit and receiving in lead time.</p></div></div>
      <div className={styles.settings}>
        {([{ key: "salesDays", label: "Sales period", help: "Days covered by units_sold" },
          { key: "defaultLeadDays", label: "Default supplier lead time", help: "Used when a SKU’s lead time is blank" },
          { key: "targetCoverDays", label: "Target stock coverage", help: "Your comparison target, not an optimized order" }] as const).map(field =>
          <label key={field.key}>{field.label}<div className={styles.inputUnit}><input type="number" min="1" max="3650" step="1" required value={settings[field.key]} onChange={event => { setSettings({ ...settings, [field.key]: event.target.value }); invalidate(); }} /><span>days</span></div><small>{field.help}</small></label>)}
        <label>Cost currency<select value={currency} onChange={event => setCurrency(event.target.value)}>
          {['USD', 'CAD', 'GBP', 'EUR', 'AUD', 'NZD'].map(code => <option key={code} value={code}>{code}</option>)}
        </select><small>Use the same currency for all unit costs</small></label>
      </div>
      <p className={styles.caution}>Recent stockouts can make sales look lower than demand; promotions can make them look higher. Review those SKUs separately. Blank safety stock means no additional buffer; missing unit costs remain unknown.</p>
      <button type="submit" className="button button-primary button-lg" disabled={loading}>{loading ? "Reading summary…" : "Check inventory priorities"}</button>
      {errors.length > 0 && <div className={styles.error} role="alert"><strong>Check the summary before continuing</strong><ul>{errors.map(error => <li key={error}>{error}</li>)}</ul></div>}
    </form>

    {rows && <section className={styles.results} aria-label="Inventory health results">
      <div className={styles.resultHeading}><div><p className={styles.eyebrow}>{sample ? "Sample results · Not your store" : "Your inventory summary"}</p><h2>{number(rows.length)} SKUs, prioritized for review</h2><p role="status">{number(totals.counts.stockout_risk)} stockout risks and {number(totals.counts.reorder_review)} additional reorder reviews under your assumptions.</p><p>{settings.salesDays}-day sales period · {settings.targetCoverDays}-day stock target · Costs in {currency}</p></div>
        <button type="button" className="button button-secondary" onClick={() => download(healthResultsCsv(rows, currency,
          { salesDays: Number(settings.salesDays), defaultLeadDays: Number(settings.defaultLeadDays), targetCoverDays: Number(settings.targetCoverDays) }), "skubase-inventory-health-check.csv")}>Download results</button></div>
      <div className={styles.overview}>
        <div className={styles.distribution} aria-label="SKU counts by review priority">{statuses.map(status => <button type="button" key={status} onClick={() => { setFilter(filter === status ? "all" : status); setShown(50); }} className={styles.distributionRow} aria-pressed={filter === status}>
          <span>{HEALTH_STATUS[status].label}</span><span className={styles.track}><span data-status={status} style={{ width: `${totals.counts[status] / rows.length * 100}%` }} /></span><strong>{number(totals.counts[status])}</strong>
        </button>)}</div>
        <aside className={styles.costCard}><span>Cost of stock above your cover target ({currency})</span><strong>{totals.missingCost && totals.knownExcessCost === 0 ? "Unknown" : money(totals.knownExcessCost)}</strong><p>{totals.missingCost ? `Known-cost subtotal; ${number(totals.missingCost)} above-target SKUs have no unit cost.` : "Based on the unit costs provided. This is stock value to review, not guaranteed recoverable cash."}</p><small>No-sales items are excluded: this check cannot establish whether that stock is excess.</small></aside>
      </div>
      <div className={styles.resultFilters}><label>Find a SKU<input value={search} onChange={event => { setSearch(event.target.value); setShown(50); }} placeholder="Search SKU" /></label>
        <label>Review priority<select value={filter} onChange={event => { setFilter(event.target.value as HealthStatus | "all"); setShown(50); }}><option value="all">All priorities</option>{statuses.map(s => <option key={s} value={s}>{HEALTH_STATUS[s].label}</option>)}</select></label>
        <p>{number(filtered.length)} matching SKUs</p></div>
      <div className={styles.tableWrap} tabIndex={0} role="region" aria-label="Inventory results table; scroll horizontally for all columns"><table><caption>Coverage and reorder triggers use the sales period and lead times above. A trigger is not an order quantity.</caption><thead><tr><th scope="col">SKU / next step</th><th scope="col">Priority</th><th scope="col" className={styles.numeric}>On hand<br /><small>units</small></th><th scope="col" className={styles.numeric}>Stock cover<br /><small>days</small></th><th scope="col" className={styles.numeric}>Lead time<br /><small>days</small></th><th scope="col" className={styles.numeric}>Reorder trigger<br /><small>units</small></th><th scope="col" className={styles.numeric}>Above target<br /><small>units</small></th></tr></thead>
        <tbody>{filtered.slice(0, shown).map(row => <tr key={row.sku}><th scope="row"><strong>{row.sku}</strong><details><summary aria-label={`Review next step for ${row.sku}`}>Review next step</summary><p>{HEALTH_STATUS[row.status].action}</p></details></th><td><span className={styles.badge} data-status={row.status}>{HEALTH_STATUS[row.status].label}</span></td><td className={styles.numeric}>{number(row.onHand)}</td><td className={styles.numeric}>{row.daysCover === null ? "Unknown" : number(row.daysCover)}</td><td className={styles.numeric}>{number(row.leadDays)}</td><td className={styles.numeric}>{row.unitsSold === 0 ? "Unknown" : number(row.reorderPoint)}</td><td className={styles.numeric}>{row.excessUnits === null ? "Unknown" : number(row.excessUnits)}</td></tr>)}</tbody></table>
        {!filtered.length && <p className={styles.noMatches}>No SKUs match these filters. Clear the search or choose another priority.</p>}</div>
      {filtered.length > shown && <button type="button" className="button button-secondary" onClick={() => setShown(shown + 50)}>Show next {Math.min(50, filtered.length - shown)} SKUs</button>}
      <div className={styles.nextStep}><div><h3>Want help interpreting the priorities?</h3><p>Skubase is an inventory-planning app for Shopify merchants. Request a free review of 5–10 products and the inventory problem you want to solve. If a workflow needs a missing feature, we can work with you to understand the gap.</p><p>Skubase is currently in Shopify&apos;s review process and is not yet listed in the Shopify App Store.</p></div><Link className="button button-primary" href="/inventory-risk-snapshot?utm_source=free_tool&utm_medium=organic&utm_campaign=inventory-health-check-v1">Request a free review</Link></div>
    </section>}
  </div>;
}
