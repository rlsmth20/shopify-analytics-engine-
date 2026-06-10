"use client";

import { useEffect, useState } from "react";

import { API_BASE_URL } from "@/lib/api-base";
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

  return (
    <div className="chart-card">
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">Clear dead stock</p>
          <h2 className="section-title section-title-small">
            Bundle slow movers with your best sellers
          </h2>
        </div>
        <span className="status-badge status-failed">
          {money.format(data.dead_stock_capital)} tied up
        </span>
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
