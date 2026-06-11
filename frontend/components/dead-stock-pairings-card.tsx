"use client";

import { useEffect, useState } from "react";

import { API_BASE_URL } from "@/lib/api-base";
import { exportFormattedReport } from "@/lib/report-export";
import { authenticatedFetch } from "@/lib/shopify-embedded";

type DeadStockPairing = {
  id: string;
  anchor_product_name: string;
  anchor_monthly_units: number;
  anchor_price: number;
  dead_product_name: string;
  dead_on_hand: number;
  dead_days_since_last_sale: number;
  dead_price: number;
  dead_capital_tied_up: number;
  match_reason: string;
  suggested_bundle_price: number;
  bundle_unit_cost: number;
  bundle_margin_pct: number;
  estimated_monthly_bundles: number;
  estimated_months_to_clear: number | null;
  projected_cash_recovered: number;
  explanation: string;
};

type PairingsResponse = {
  pairings: DeadStockPairing[];
  dead_stock_sku_count: number;
  dead_stock_capital: number;
};

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function isGiftSeason(): boolean {
  const month = new Date().getMonth(); // 8 = September, 10 = November
  return month >= 8 && month <= 10;
}

export function DeadStockPairingsCard() {
  const [data, setData] = useState<PairingsResponse | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void authenticatedFetch(`${API_BASE_URL}/bundles/dead-stock-pairings`, {
      credentials: "include",
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((body) => {
        if (!cancelled && body) setData(body as PairingsResponse);
      })
      .catch(() => {
        // Additive section; co-purchase opportunities still render without it.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!data || data.pairings.length === 0) return null;

  function exportPairings() {
    if (!data) return;
    void exportFormattedReport({
      title: "Dead-stock Bundle Plan",
      subtitle:
        "Slow movers paired with fast sellers to clear stale inventory without a storewide markdown.",
      filename: `skubase-dead-stock-bundles-${new Date().toISOString().slice(0, 10)}.xlsx`,
      detailSheetName: "Pairings",
      kpis: [
        { label: "Pairings", value: String(data.pairings.length) },
        { label: "Dead SKUs", value: String(data.dead_stock_sku_count), tone: "danger" },
        { label: "Capital tied up", value: money.format(data.dead_stock_capital), tone: "danger" },
        {
          label: "Projected recovery (90d)",
          value: money.format(
            data.pairings.reduce((sum, pairing) => sum + pairing.projected_cash_recovered, 0),
          ),
          tone: "good",
        },
      ],
      charts: [
        {
          title: "Capital freed per pairing",
          points: [...data.pairings]
            .sort((l, r) => r.dead_capital_tied_up - l.dead_capital_tied_up)
            .slice(0, 8)
            .map((pairing) => ({
              label: `${pairing.anchor_product_name} + ${pairing.dead_product_name}`,
              value: pairing.dead_capital_tied_up,
              display: money.format(pairing.dead_capital_tied_up),
              tone: "danger",
            })),
        },
      ],
      todos: [
        { label: "Build the largest pairings first", detail: "They free the most cash per bundle created.", tone: "danger" },
        { label: "Price at the suggested bundle price", detail: "The discount is on the slow item only, protecting your anchor's margin.", tone: "warning" },
        { label: "Revisit in 30 days", detail: "Re-export to compare actual sell-through against the projection.", tone: "good" },
      ],
      tableTitle: "Dead-stock Pairings",
      rows: data.pairings,
      columns: [
        { key: "anchor", label: "Anchor (fast mover)", width: 30, format: (p) => p.anchor_product_name },
        { key: "dead", label: "Dead stock item", width: 30, format: (p) => p.dead_product_name },
        { key: "match", label: "Match", width: 24, format: (p) => p.match_reason },
        {
          key: "deadUnits",
          label: "Dead units",
          align: "right",
          width: 12,
          format: (p) => String(p.dead_on_hand),
          numericValue: (p) => p.dead_on_hand,
          numFmt: "#,##0",
          summarize: "sum",
        },
        {
          key: "staleDays",
          label: "Days stale",
          align: "right",
          width: 12,
          format: (p) => String(p.dead_days_since_last_sale),
          numericValue: (p) => p.dead_days_since_last_sale,
          numFmt: "#,##0",
          tone: (p) => (p.dead_days_since_last_sale >= 120 ? "danger" : "warning"),
        },
        {
          key: "bundlePrice",
          label: "Bundle price",
          align: "right",
          width: 14,
          format: (p) => money.format(p.suggested_bundle_price),
          numericValue: (p) => p.suggested_bundle_price,
          numFmt: '"$"#,##0.00',
        },
        {
          key: "margin",
          label: "Margin",
          align: "right",
          width: 10,
          format: (p) => `${p.bundle_margin_pct.toFixed(0)}%`,
          numericValue: (p) => p.bundle_margin_pct / 100,
          numFmt: "0%",
          tone: (p) => (p.bundle_margin_pct >= 40 ? "good" : null),
        },
        {
          key: "monthly",
          label: "Bundles/mo",
          align: "right",
          width: 12,
          format: (p) => String(p.estimated_monthly_bundles),
          numericValue: (p) => p.estimated_monthly_bundles,
          numFmt: "#,##0",
        },
        {
          key: "capital",
          label: "Capital tied up",
          align: "right",
          width: 15,
          format: (p) => money.format(p.dead_capital_tied_up),
          numericValue: (p) => p.dead_capital_tied_up,
          numFmt: '"$"#,##0',
          tone: () => "danger",
          summarize: "sum",
        },
        {
          key: "recovery",
          label: "Recovery (90d)",
          align: "right",
          width: 15,
          format: (p) => money.format(p.projected_cash_recovered),
          numericValue: (p) => p.projected_cash_recovered,
          numFmt: '"$"#,##0',
          tone: () => "good",
          summarize: "sum",
        },
        { key: "explanation", label: "The math", width: 70, format: (p) => p.explanation },
      ],
    });
  }

  return (
    <div className="chart-card">
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">Clear dead stock</p>
          <h2 className="section-title section-title-small">
            Bundle slow movers with your best sellers
          </h2>
        </div>
        <div className="button-row" style={{ alignItems: "center", gap: "8px" }}>
          <span className="status-badge status-failed">
            {money.format(data.dead_stock_capital)} tied up
          </span>
          <button type="button" className="button button-ghost" onClick={exportPairings}>
            Export Excel
          </button>
        </div>
      </div>
      <p className="section-copy">
        {data.dead_stock_sku_count} SKU{data.dead_stock_sku_count === 1 ? " has" : "s have"} not
        sold in 45+ days. Attaching them to a fast mover moves volume without a
        visible storewide markdown.
        {isGiftSeason()
          ? " Gift season tip: these pairings make natural Q4 gift boxes - build them before Black Friday."
          : ""}
      </p>
      <div className="signal-list" style={{ marginTop: "12px" }}>
        {data.pairings.slice(0, 6).map((pairing) => (
          <div key={pairing.id} className="signal-item" style={{ alignItems: "flex-start" }}>
            <div style={{ flex: 1 }}>
              <p className="signal-title">
                {pairing.anchor_product_name} + {pairing.dead_product_name}
              </p>
              <p className="signal-copy">
                {pairing.dead_product_name}: {pairing.dead_on_hand} units,{" "}
                {pairing.dead_days_since_last_sale}d without a sale ({pairing.match_reason})
              </p>
              <p className="signal-copy">
                Suggested bundle {money.format(pairing.suggested_bundle_price)} -{" "}
                {pairing.bundle_margin_pct.toFixed(0)}% margin - ~
                {pairing.estimated_monthly_bundles} bundles/mo
                {pairing.estimated_months_to_clear !== null
                  ? ` - clears in ~${pairing.estimated_months_to_clear} months`
                  : ""}
              </p>
              {expanded === pairing.id ? (
                <p className="signal-copy" style={{ marginTop: "8px" }}>
                  {pairing.explanation}
                </p>
              ) : null}
              <button
                type="button"
                className="auth-link-button"
                onClick={() =>
                  setExpanded((current) => (current === pairing.id ? null : pairing.id))
                }
              >
                {expanded === pairing.id ? "Hide the math" : "Show the math"}
              </button>
            </div>
            <div style={{ textAlign: "right" }}>
              <strong>{money.format(pairing.projected_cash_recovered)}</strong>
              <p className="signal-copy">projected recovery (90d)</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
