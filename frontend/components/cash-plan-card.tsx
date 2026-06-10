"use client";

import { useEffect, useState } from "react";

import { API_BASE_URL } from "@/lib/api-base";
import { authenticatedFetch } from "@/lib/shopify-embedded";

type CashPlanVendor = {
  vendor: string;
  order_now_cost: number;
  deferrable_cost: number;
  item_count: number;
  max_lead_time_days: number;
};

type CashPlan = {
  order_now_cost: number;
  deferrable_cost: number;
  total_cost: number;
  order_now_items: number;
  deferrable_items: number;
  vendors: CashPlanVendor[];
  explanation: string;
};

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

export function CashPlanCard({
  serviceLevel,
  shippingCost,
}: {
  serviceLevel: number;
  shippingCost: number;
}) {
  const [plan, setPlan] = useState<CashPlan | null>(null);

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({
      service_level: String(serviceLevel),
      shipping_cost: String(shippingCost),
    });
    void authenticatedFetch(`${API_BASE_URL}/reorder/cash-plan?${params}`, {
      credentials: "include",
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data) setPlan(data as CashPlan);
      })
      .catch(() => {
        // The cash plan is additive; PO drafts still work without it.
      });
    return () => {
      cancelled = true;
    };
  }, [serviceLevel, shippingCost]);

  if (!plan || plan.total_cost <= 0) return null;

  return (
    <div className="chart-card">
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">Open to buy</p>
          <h2 className="section-title section-title-small">Cash your reorder queue needs</h2>
        </div>
      </div>
      <div className="kpi-grid kpi-grid-tight" style={{ marginTop: "12px" }}>
        <div className="kpi-card">
          <p className="kpi-label">Order this week</p>
          <p className="kpi-value">{money.format(plan.order_now_cost)}</p>
          <p className="kpi-note">{plan.order_now_items} SKUs at/below reorder point</p>
        </div>
        <div className="kpi-card">
          <p className="kpi-label">Deferrable</p>
          <p className="kpi-value">{money.format(plan.deferrable_cost)}</p>
          <p className="kpi-note">{plan.deferrable_items} top-ups that can wait if cash is tight</p>
        </div>
        <div className="kpi-card">
          <p className="kpi-label">Total recommended</p>
          <p className="kpi-value">{money.format(plan.total_cost)}</p>
          <p className="kpi-note">At the current service level setting</p>
        </div>
      </div>
      {plan.vendors.length > 0 ? (
        <div className="signal-list" style={{ marginTop: "16px" }}>
          {plan.vendors.slice(0, 6).map((vendor) => (
            <div key={vendor.vendor} className="signal-item">
              <div>
                <p className="signal-title">{vendor.vendor}</p>
                <p className="signal-copy">
                  {vendor.item_count} SKU{vendor.item_count === 1 ? "" : "s"} - longest lead time{" "}
                  {vendor.max_lead_time_days}d
                </p>
              </div>
              <div style={{ textAlign: "right" }}>
                <strong>{money.format(vendor.order_now_cost)}</strong>
                {vendor.deferrable_cost > 0 ? (
                  <p className="signal-copy">+{money.format(vendor.deferrable_cost)} deferrable</p>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}
      <p className="section-copy" style={{ marginTop: "12px" }}>{plan.explanation}</p>
    </div>
  );
}
