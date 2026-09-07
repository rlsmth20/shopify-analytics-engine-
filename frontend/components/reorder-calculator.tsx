"use client";

import { useState } from "react";
import Link from "next/link";
import { trackGrowthEvent } from "@/lib/analytics";

export function ReorderCalculator() {
  const [values, setValues] = useState({ demand: "5", lead: "14", safety: "20", onHand: "60", incoming: "0", committed: "0" });
  const [result, setResult] = useState<{ point: number; position: number } | null>(null);
  const [error, setError] = useState("");
  const fields: { key: keyof typeof values; label: string; unit: string }[] = [
    { key: "demand", label: "Average daily demand", unit: "units / day" },
    { key: "lead", label: "Supplier lead time", unit: "days" },
    { key: "safety", label: "Safety stock", unit: "units" },
    { key: "onHand", label: "On-hand inventory", unit: "units" },
    { key: "incoming", label: "Confirmed incoming stock", unit: "units" },
    { key: "committed", label: "Committed, not deducted yet", unit: "units" },
  ];
  return <section style={{ padding: 24, margin: "28px 0", border: "1px solid #d5ded4", borderRadius: 14, background: "#f5f7f1" }}>
    <form onSubmit={event => {
      event.preventDefault();
      const numbers = Object.fromEntries(Object.entries(values).map(([key, value]) => [key, Number(value)])) as Record<keyof typeof values, number>;
      if (Object.values(values).some(v => v.trim() === "") || Object.values(numbers).some(v => !Number.isFinite(v) || v < 0 || v > 10000000)) {
        setError("Enter a number from 0 to 10,000,000 in each field."); setResult(null); return;
      }
      setError("");
      setResult({ point: Math.ceil(numbers.demand * numbers.lead + numbers.safety), position: numbers.onHand + numbers.incoming - numbers.committed });
      void trackGrowthEvent("CALCULATOR_USED");
    }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 18 }}>
        {fields.map(field => <label key={field.key} style={{ display: "grid", gap: 6, fontSize: 14 }}>
          <strong>{field.label}</strong><input type="number" min="0" max="10000000" step="any" required value={values[field.key]}
            onChange={e => { setValues({ ...values, [field.key]: e.target.value }); setResult(null); }}
            style={{ padding: 12, borderRadius: 7, border: "1px solid #b9c7b5", background: "white", color: "#163c2f", fontSize: 18 }} />
          <span style={{ color: "#687363", fontSize: 12 }}>{field.unit}</span>
        </label>)}
      </div>
      <button type="submit" className="button button-primary" style={{ marginTop: 22 }}>Calculate reorder point</button>
      {error && <p role="alert">{error}</p>}
    </form>
    {result && <div role="status" style={{ marginTop: 24, borderTop: "1px solid #cedbc7", paddingTop: 20 }}>
      <p style={{ fontSize: 30, margin: "0 0 12px" }}><strong>{result.point.toLocaleString()} units</strong> <span style={{ fontSize: 14 }}>reorder point</span></p>
      <p>Inventory position: <strong>{result.position.toLocaleString()} units</strong>. {result.position <= result.point ? "At or below your trigger: review a reorder and the timing of incoming stock." : "Above your trigger: keep monitoring demand and supplier lead time."}</p>
      <p>Want to check more than one SKU?</p>
      <Link className="button button-primary" href="/tools/inventory-health-check?utm_source=free_tool&utm_medium=organic&utm_campaign=reorder-calculator-v1">Check a SKU summary</Link>
      <p><Link href="/inventory-risk-snapshot?utm_source=free_tool&utm_medium=organic&utm_campaign=reorder-calculator-v1">Or request a free review with Skubase</Link>.</p>
    </div>}
  </section>;
}
