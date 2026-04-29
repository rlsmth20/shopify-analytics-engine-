// ---------------------------------------------------------------------------
// demo-data.ts
// Realistic mock responses for every authenticated API endpoint.
// Returned by api.ts / api-v2.ts when sessionStorage.skubase_demo === "1"
// so the demo dashboard works without a real backend session.
// ---------------------------------------------------------------------------

// ── helpers ────────────────────────────────────────────────────────────────

function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString();
}

function daysFromNow(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

// ── Dashboard ───────────────────────────────────────────────────────────────

function buildRevenueTrend(): { label: string; value: number }[] {
  const base = 1580;
  const trend: { label: string; value: number }[] = [];
  for (let i = 29; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const label = d.toISOString().slice(0, 10);
    // weekend bump + some noise
    const dow = d.getDay();
    const weekendMult = dow === 0 || dow === 6 ? 1.35 : 1.0;
    const noise = 0.85 + Math.abs(Math.sin(i * 7.3)) * 0.35;
    trend.push({ label, value: Math.round(base * weekendMult * noise) });
  }
  return trend;
}

export const DEMO_DASHBOARD = {
  kpis: [
    { label: "Revenue (30d)", value: 48230, unit: "currency" as const, delta_pct: 12.4, tone: "positive" as const },
    { label: "Urgent SKUs", value: 23, unit: "count" as const, delta_pct: -8.3, tone: "negative" as const },
    { label: "Dead-stock capital", value: 18400, unit: "currency" as const, delta_pct: 3.1, tone: "negative" as const },
    { label: "Avg days of cover", value: 34, unit: "days" as const, delta_pct: 5.7, tone: "positive" as const },
  ],
  revenue_trend_30d: buildRevenueTrend(),
  stock_health_breakdown: [
    { label: "Healthy", value: 312 },
    { label: "Urgent", value: 23 },
    { label: "Overstock", value: 67 },
    { label: "Dead", value: 41 },
  ],
  top_movers: [
    { label: "Premium Linen Shirt", value: 9840 },
    { label: "Organic Cotton Hoodie", value: 7610 },
    { label: "Slim Fit Chinos", value: 6230 },
    { label: "Wool Blend Sweater", value: 5480 },
    { label: "Classic Polo", value: 4790 },
    { label: "Canvas Tote Bag", value: 3920 },
    { label: "Denim Jacket", value: 3670 },
    { label: "Running Shorts", value: 2850 },
  ],
  abc_distribution: [
    { label: "A — Top 80%", value: 84 },
    { label: "B — Next 15%", value: 201 },
    { label: "C — Tail 5%", value: 158 },
  ],
  cash_at_risk_by_vendor: [
    { label: "Coastal Apparel Co.", value: 7200 },
    { label: "NorthThread Supply", value: 4850 },
    { label: "Pacific Goods Ltd.", value: 2960 },
    { label: "Atlas Basics", value: 1840 },
    { label: "SunRise Textiles", value: 990 },
    { label: "BlueLine Imports", value: 560 },
  ],
  forecast_vs_actual_7d: [
    { label: "Mon", value: 4.2 },
    { label: "Tue", value: -2.1 },
    { label: "Wed", value: 7.8 },
    { label: "Thu", value: -1.4 },
    { label: "Fri", value: 3.3 },
    { label: "Sat", value: -5.6 },
    { label: "Sun", value: 2.0 },
  ],
  alert_counts_by_severity: [
    { label: "Critical", value: 3 },
    { label: "Warning", value: 11 },
    { label: "Info", value: 28 },
  ],
  generated_at: new Date().toISOString(),
};

// ── Forecasts ────────────────────────────────────────────────────────────────

function buildForecastPoints(baseDemand: number, horizon = 30) {
  return Array.from({ length: horizon }, (_, i) => ({
    day_offset: i + 1,
    expected_units: Math.round(baseDemand * (0.9 + Math.sin(i * 0.9) * 0.15)),
    lower_bound: Math.round(baseDemand * 0.7),
    upper_bound: Math.round(baseDemand * 1.3),
  }));
}

export const DEMO_FORECASTS = {
  forecasts: [
    {
      sku_id: "sku_premium-linen-shirt-navy-m",
      horizon_days: 30,
      method: "holt_double_exponential",
      trend: "rising" as const,
      seasonality: "weekend_heavy" as const,
      weekly_index: [0.82, 0.88, 0.91, 0.95, 1.18, 1.42, 1.29],
      confidence: "high" as const,
      projected_30_day_demand: 186,
      projected_60_day_demand: 379,
      projected_90_day_demand: 573,
      stockout_probability_30d: 0.74,
      points: buildForecastPoints(6.2),
      explain:
        "Strong upward trend with consistent weekend lift. Current on-hand covers ~8 days at observed velocity. Reorder immediately.",
    },
    {
      sku_id: "sku_wool-blend-sweater-grey-l",
      horizon_days: 30,
      method: "holt_double_exponential",
      trend: "rising" as const,
      seasonality: "weekday_heavy" as const,
      weekly_index: [1.12, 1.08, 0.98, 0.96, 0.92, 0.78, 0.81],
      confidence: "high" as const,
      projected_30_day_demand: 142,
      projected_60_day_demand: 291,
      projected_90_day_demand: 445,
      stockout_probability_30d: 0.61,
      points: buildForecastPoints(4.7),
      explain:
        "Seasonal demand spike entering winter months. Weekday-heavy pattern suggests B2B or gifting channel.",
    },
    {
      sku_id: "sku_silk-scarf-burgundy",
      horizon_days: 30,
      method: "holt_double_exponential",
      trend: "rising" as const,
      seasonality: "weekend_heavy" as const,
      weekly_index: [0.71, 0.83, 0.89, 0.94, 1.22, 1.58, 1.47],
      confidence: "medium" as const,
      projected_30_day_demand: 98,
      projected_60_day_demand: 203,
      projected_90_day_demand: 308,
      stockout_probability_30d: 0.53,
      points: buildForecastPoints(3.3),
      explain:
        "Moderate confidence — fewer than 60 historical data points. Weekend demand is materially higher. Safety stock buffer recommended.",
    },
    {
      sku_id: "sku_slim-fit-chinos-khaki-32x30",
      horizon_days: 30,
      method: "holt_double_exponential",
      trend: "steady" as const,
      seasonality: "flat" as const,
      weekly_index: [0.98, 1.01, 1.02, 0.99, 1.00, 1.01, 0.99],
      confidence: "high" as const,
      projected_30_day_demand: 124,
      projected_60_day_demand: 248,
      projected_90_day_demand: 372,
      stockout_probability_30d: 0.38,
      points: buildForecastPoints(4.1),
      explain:
        "Very stable demand with no detectable seasonality. Lead time of 21d against 18d of remaining cover puts this in a reorder window.",
    },
    {
      sku_id: "sku_organic-cotton-hoodie-black-xl",
      horizon_days: 30,
      method: "holt_double_exponential",
      trend: "declining" as const,
      seasonality: "weekend_heavy" as const,
      weekly_index: [0.79, 0.85, 0.91, 0.96, 1.14, 1.38, 1.22],
      confidence: "high" as const,
      projected_30_day_demand: 67,
      projected_60_day_demand: 129,
      projected_90_day_demand: 186,
      stockout_probability_30d: 0.08,
      points: buildForecastPoints(2.2),
      explain:
        "Demand declining from peak. Ample on-hand stock — hold and let inventory run down before next reorder.",
    },
    {
      sku_id: "sku_canvas-tote-bag-natural",
      horizon_days: 30,
      method: "holt_double_exponential",
      trend: "steady" as const,
      seasonality: "flat" as const,
      weekly_index: [0.97, 1.00, 1.01, 1.02, 1.01, 0.99, 1.00],
      confidence: "high" as const,
      projected_30_day_demand: 58,
      projected_60_day_demand: 116,
      projected_90_day_demand: 174,
      stockout_probability_30d: 0.05,
      points: buildForecastPoints(1.9),
      explain: "Steady low-velocity item. Current stock covers 60+ days. No action needed.",
    },
    {
      sku_id: "sku_classic-polo-white-s",
      horizon_days: 30,
      method: "holt_double_exponential",
      trend: "volatile" as const,
      seasonality: "unknown" as const,
      weekly_index: [1.31, 0.74, 1.18, 0.82, 0.96, 1.23, 0.87],
      confidence: "low" as const,
      projected_30_day_demand: 45,
      projected_60_day_demand: 89,
      projected_90_day_demand: 132,
      stockout_probability_30d: 0.22,
      points: buildForecastPoints(1.5),
      explain:
        "Low confidence due to erratic demand pattern. Possible channel mixing or listing changes. Review sales history before acting on this forecast.",
    },
    {
      sku_id: "sku_denim-jacket-indigo-l",
      horizon_days: 30,
      method: "holt_double_exponential",
      trend: "declining" as const,
      seasonality: "flat" as const,
      weekly_index: [1.02, 1.00, 0.99, 0.98, 1.01, 0.99, 1.01],
      confidence: "medium" as const,
      projected_30_day_demand: 38,
      projected_60_day_demand: 71,
      projected_90_day_demand: 99,
      stockout_probability_30d: 0.04,
      points: buildForecastPoints(1.3),
      explain: "Post-season slowdown. 90+ days of cover. Consider markdown to free capital.",
    },
  ],
};

// ── Analytics (ABC × XYZ scorecards) ────────────────────────────────────────

export const DEMO_SCORECARDS = {
  a_count: 84,
  b_count: 201,
  c_count: 158,
  cutoff_a_pct: 80,
  cutoff_b_pct: 95,
  scorecards: [
    {
      sku_id: "sku_premium-linen-shirt-navy-m",
      name: "Premium Linen Shirt - Navy M",
      vendor: "Coastal Apparel Co.",
      category: "Tops",
      abc_class: "A" as const,
      xyz_class: "X" as const,
      contribution_pct: 8.3,
      variability_cv: 0.14,
      avg_daily_units: 6.2,
      avg_daily_revenue: 328,
      profit_per_unit: 24.5,
      sell_through_30d: 0.91,
      inventory_on_hand: 48,
      classification_note: "Top revenue driver with highly predictable demand. Protect service level.",
    },
    {
      sku_id: "sku_organic-cotton-hoodie-black-xl",
      name: "Organic Cotton Hoodie - Black XL",
      vendor: "NorthThread Supply",
      category: "Outerwear",
      abc_class: "A" as const,
      xyz_class: "Y" as const,
      contribution_pct: 6.5,
      variability_cv: 0.29,
      avg_daily_units: 4.8,
      avg_daily_revenue: 254,
      profit_per_unit: 31.0,
      sell_through_30d: 0.44,
      inventory_on_hand: 214,
      classification_note: "High revenue but demand variability is moderate. Current overstock needs attention.",
    },
    {
      sku_id: "sku_slim-fit-chinos-khaki-32x30",
      name: "Slim Fit Chinos - Khaki 32×30",
      vendor: "Pacific Goods Ltd.",
      category: "Bottoms",
      abc_class: "A" as const,
      xyz_class: "X" as const,
      contribution_pct: 5.2,
      variability_cv: 0.11,
      avg_daily_units: 4.1,
      avg_daily_revenue: 207,
      profit_per_unit: 19.8,
      sell_through_30d: 0.87,
      inventory_on_hand: 73,
      classification_note: "Stable A-item. Reorder point approaching.",
    },
    {
      sku_id: "sku_wool-blend-sweater-grey-l",
      name: "Wool Blend Sweater - Grey L",
      vendor: "NorthThread Supply",
      category: "Tops",
      abc_class: "A" as const,
      xyz_class: "Y" as const,
      contribution_pct: 4.6,
      variability_cv: 0.32,
      avg_daily_units: 3.8,
      avg_daily_revenue: 193,
      profit_per_unit: 28.4,
      sell_through_30d: 0.79,
      inventory_on_hand: 31,
      classification_note: "Seasonal demand variability. Monitor closely during winter ramp.",
    },
    {
      sku_id: "sku_classic-polo-white-s",
      name: "Classic Polo - White S",
      vendor: "Atlas Basics",
      category: "Tops",
      abc_class: "B" as const,
      xyz_class: "Z" as const,
      contribution_pct: 2.1,
      variability_cv: 0.61,
      avg_daily_units: 1.5,
      avg_daily_revenue: 68,
      profit_per_unit: 14.2,
      sell_through_30d: 0.38,
      inventory_on_hand: 142,
      classification_note: "High volatility B-item. Avoid large reorders until demand stabilises.",
    },
    {
      sku_id: "sku_canvas-tote-bag-natural",
      name: "Canvas Tote Bag - Natural",
      vendor: "Pacific Goods Ltd.",
      category: "Accessories",
      abc_class: "B" as const,
      xyz_class: "X" as const,
      contribution_pct: 1.8,
      variability_cv: 0.09,
      avg_daily_units: 1.9,
      avg_daily_revenue: 57,
      profit_per_unit: 11.0,
      sell_through_30d: 0.61,
      inventory_on_hand: 188,
      classification_note: "Very predictable demand. Slight overstock — hold.",
    },
    {
      sku_id: "sku_silk-scarf-burgundy",
      name: "Silk Scarf - Burgundy",
      vendor: "SunRise Textiles",
      category: "Accessories",
      abc_class: "B" as const,
      xyz_class: "Y" as const,
      contribution_pct: 1.4,
      variability_cv: 0.38,
      avg_daily_units: 3.3,
      avg_daily_revenue: 148,
      profit_per_unit: 22.1,
      sell_through_30d: 0.82,
      inventory_on_hand: 18,
      classification_note: "High sell-through rate and rising demand. Stockout risk in 5–7 days.",
    },
    {
      sku_id: "sku_denim-jacket-indigo-l",
      name: "Denim Jacket - Indigo L",
      vendor: "Coastal Apparel Co.",
      category: "Outerwear",
      abc_class: "B" as const,
      xyz_class: "Y" as const,
      contribution_pct: 1.1,
      variability_cv: 0.27,
      avg_daily_units: 1.3,
      avg_daily_revenue: 87,
      profit_per_unit: 38.5,
      sell_through_30d: 0.29,
      inventory_on_hand: 156,
      classification_note: "Post-season slowdown. Mark down to recover capital.",
    },
    {
      sku_id: "sku_leather-wallet-brown",
      name: "Leather Wallet - Brown",
      vendor: "Atlas Basics",
      category: "Accessories",
      abc_class: "C" as const,
      xyz_class: "Z" as const,
      contribution_pct: 0.4,
      variability_cv: 0.74,
      avg_daily_units: 0.3,
      avg_daily_revenue: 18,
      profit_per_unit: 21.0,
      sell_through_30d: 0.08,
      inventory_on_hand: 204,
      classification_note: "Long-tail item with erratic demand. Write-off or bundle candidate.",
    },
    {
      sku_id: "sku_running-shorts-blue-m",
      name: "Running Shorts - Blue M",
      vendor: "BlueLine Imports",
      category: "Activewear",
      abc_class: "C" as const,
      xyz_class: "Z" as const,
      contribution_pct: 0.3,
      variability_cv: 0.81,
      avg_daily_units: 0.2,
      avg_daily_revenue: 12,
      profit_per_unit: 9.5,
      sell_through_30d: 0.06,
      inventory_on_hand: 318,
      classification_note: "Dead stock. Seasonal item past its window — needs liquidation plan.",
    },
  ],
};

// ── Suppliers ────────────────────────────────────────────────────────────────

export const DEMO_SUPPLIERS = {
  vendors: [
    {
      vendor: "Coastal Apparel Co.",
      sku_count: 38,
      on_time_pct: 94,
      fill_rate_pct: 97,
      avg_lead_time_days: 14,
      lead_time_variance_days: 1.2,
      cost_stability_score: 91,
      overall_score: 93,
      tier: "preferred" as const,
      notes: [
        "Consistent on-time delivery over last 12 months",
        "Accepted emergency reorder within 48 h last quarter",
      ],
    },
    {
      vendor: "NorthThread Supply",
      sku_count: 24,
      on_time_pct: 88,
      fill_rate_pct: 93,
      avg_lead_time_days: 18,
      lead_time_variance_days: 3.4,
      cost_stability_score: 84,
      overall_score: 80,
      tier: "acceptable" as const,
      notes: [
        "Two late shipments in Q3 — flagged for review",
        "Fill rate dipped to 89% in October",
      ],
    },
    {
      vendor: "Pacific Goods Ltd.",
      sku_count: 19,
      on_time_pct: 91,
      fill_rate_pct: 95,
      avg_lead_time_days: 21,
      lead_time_variance_days: 2.1,
      cost_stability_score: 88,
      overall_score: 86,
      tier: "preferred" as const,
      notes: [
        "Reliable but longer lead time requires earlier PO placement",
        "Cost increases averaging 3% YoY",
      ],
    },
    {
      vendor: "Atlas Basics",
      sku_count: 31,
      on_time_pct: 72,
      fill_rate_pct: 81,
      avg_lead_time_days: 28,
      lead_time_variance_days: 7.8,
      cost_stability_score: 64,
      overall_score: 58,
      tier: "at_risk" as const,
      notes: [
        "Three partial shipments in the past 90 days",
        "Lead time variance has increased by 40% since Q2",
        "Recommend dual-sourcing critical SKUs",
      ],
    },
    {
      vendor: "SunRise Textiles",
      sku_count: 12,
      on_time_pct: 85,
      fill_rate_pct: 90,
      avg_lead_time_days: 24,
      lead_time_variance_days: 4.2,
      cost_stability_score: 78,
      overall_score: 75,
      tier: "acceptable" as const,
      notes: [
        "Good relationship — seasonal capacity constraints in Q4",
        "Negotiate buffer stock agreement before peak",
      ],
    },
    {
      vendor: "BlueLine Imports",
      sku_count: 9,
      on_time_pct: 67,
      fill_rate_pct: 74,
      avg_lead_time_days: 35,
      lead_time_variance_days: 11.3,
      cost_stability_score: 52,
      overall_score: 44,
      tier: "at_risk" as const,
      notes: [
        "Extremely high lead time variance — unsuitable for fast-moving SKUs",
        "Consider replacing with domestic alternative",
        "All pending POs on watch list",
      ],
    },
  ],
};

// ── Bundles ──────────────────────────────────────────────────────────────────

export const DEMO_BUNDLES = {
  bundles: [
    {
      bundle_sku_id: "sku_gift-set-linen-scarf",
      bundle_name: "Linen Shirt + Silk Scarf Gift Set",
      max_bundles_sellable: 18,
      limiting_component_sku_id: "sku_silk-scarf-burgundy",
      limiting_component_name: "Silk Scarf - Burgundy",
      component_status: [
        "Premium Linen Shirt - Navy M: 48 on hand ✓",
        "Silk Scarf - Burgundy: 18 on hand ⚠ limiting",
      ],
      total_component_value_at_risk: 2340,
      recommended_action:
        "Reorder Silk Scarf immediately — 5-day lead time means you can cover the holiday window if ordered today.",
    },
    {
      bundle_sku_id: "sku_essentials-kit-polo-tote",
      bundle_name: "Everyday Essentials Kit (Polo + Tote)",
      max_bundles_sellable: 142,
      limiting_component_sku_id: "sku_classic-polo-white-s",
      limiting_component_name: "Classic Polo - White S",
      component_status: [
        "Classic Polo - White S: 142 on hand ✓",
        "Canvas Tote Bag - Natural: 188 on hand ✓",
      ],
      total_component_value_at_risk: 0,
      recommended_action: "No action needed — both components well-stocked.",
    },
  ],
};

// ── Transfers ────────────────────────────────────────────────────────────────

export const DEMO_TRANSFERS = {
  transfers: [
    {
      sku_id: "sku_premium-linen-shirt-navy-m",
      name: "Premium Linen Shirt - Navy M",
      from_location: "Warehouse B (Los Angeles)",
      to_location: "Warehouse A (New York)",
      qty: 24,
      from_days_of_cover_before: 41,
      to_days_of_cover_before: 8,
      from_days_of_cover_after: 17,
      to_days_of_cover_after: 32,
      rationale:
        "New York location approaching stockout (8d cover). LA has surplus relative to its local demand. Intra-network transfer avoids a full reorder cycle.",
    },
    {
      sku_id: "sku_organic-cotton-hoodie-black-xl",
      name: "Organic Cotton Hoodie - Black XL",
      from_location: "Warehouse A (New York)",
      to_location: "Warehouse C (Chicago)",
      qty: 60,
      from_days_of_cover_before: 214,
      to_days_of_cover_before: 12,
      from_days_of_cover_after: 154,
      to_days_of_cover_after: 72,
      rationale:
        "Chicago nearing reorder point but New York is significantly overstocked. Transfer reduces dead-stock risk in New York.",
    },
  ],
};

// ── Liquidation ──────────────────────────────────────────────────────────────

export const DEMO_LIQUIDATION = {
  total_capital_recoverable: 14820,
  suggestions: [
    {
      sku_id: "sku_running-shorts-blue-m",
      name: "Running Shorts - Blue M",
      on_hand: 318,
      days_since_last_sale: 94,
      capital_tied_up: 3021,
      suggested_markdown_pct: 60,
      suggested_price: 11.98,
      projected_recovered_capital: 1905,
      tactic: "wholesale" as const,
      rationale:
        "Off-season item with near-zero sell-through. Wholesale liquidation recovers more capital faster than a retail markdown at this velocity.",
    },
    {
      sku_id: "sku_leather-wallet-brown",
      name: "Leather Wallet - Brown",
      on_hand: 204,
      days_since_last_sale: 67,
      capital_tied_up: 4284,
      suggested_markdown_pct: 40,
      suggested_price: 35.94,
      projected_recovered_capital: 3230,
      tactic: "markdown" as const,
      rationale:
        "Slow mover with high margin headroom. A 40% markdown should stimulate enough velocity to clear within 60 days without a fire sale.",
    },
    {
      sku_id: "sku_denim-jacket-indigo-l",
      name: "Denim Jacket - Indigo L",
      on_hand: 156,
      days_since_last_sale: 22,
      capital_tied_up: 6006,
      suggested_markdown_pct: 25,
      suggested_price: 59.25,
      projected_recovered_capital: 4680,
      tactic: "bundle" as const,
      rationale:
        "Post-season but still has some demand. Bundle with Classic Polo for a 'Spring Preview' kit — bundling protects margin better than a straight discount.",
    },
    {
      sku_id: "sku_classic-polo-white-s",
      name: "Classic Polo - White S",
      on_hand: 142,
      days_since_last_sale: 8,
      capital_tied_up: 2017,
      suggested_markdown_pct: 20,
      suggested_price: 47.96,
      projected_recovered_capital: 2005,
      tactic: "markdown" as const,
      rationale:
        "Erratic demand but relatively recent last sale. Light markdown combined with a flash sale should clear excess without major margin impact.",
    },
  ],
};

// ── Purchase Orders ──────────────────────────────────────────────────────────

export const DEMO_PURCHASE_ORDERS = {
  total_capital_required: 21480,
  drafts: [
    {
      po_id: "po_coastal-apr29",
      vendor: "Coastal Apparel Co.",
      created_at: new Date().toISOString(),
      status: "draft" as const,
      lines: [
        {
          sku_id: "sku_premium-linen-shirt-navy-m",
          name: "Premium Linen Shirt - Navy M",
          qty: 120,
          unit_cost: 28.5,
          extended_cost: 3420,
        },
        {
          sku_id: "sku_silk-scarf-burgundy",
          name: "Silk Scarf - Burgundy",
          qty: 80,
          unit_cost: 19.0,
          extended_cost: 1520,
        },
      ],
      total_cost: 4940,
      expected_arrival_date: daysFromNow(16),
      rationale: "Urgent reorder — both SKUs at critical stockout risk within 14 days.",
    },
    {
      po_id: "po_norththread-apr29",
      vendor: "NorthThread Supply",
      created_at: new Date().toISOString(),
      status: "draft" as const,
      lines: [
        {
          sku_id: "sku_wool-blend-sweater-grey-l",
          name: "Wool Blend Sweater - Grey L",
          qty: 200,
          unit_cost: 34.2,
          extended_cost: 6840,
        },
      ],
      total_cost: 6840,
      expected_arrival_date: daysFromNow(20),
      rationale: "Seasonal demand spike anticipated. Order now to cover the winter ramp.",
    },
    {
      po_id: "po_pacific-apr29",
      vendor: "Pacific Goods Ltd.",
      created_at: new Date().toISOString(),
      status: "draft" as const,
      lines: [
        {
          sku_id: "sku_slim-fit-chinos-khaki-32x30",
          name: "Slim Fit Chinos - Khaki 32×30",
          qty: 150,
          unit_cost: 22.0,
          extended_cost: 3300,
        },
      ],
      total_cost: 3300,
      expected_arrival_date: daysFromNow(23),
      rationale:
        "Stock covers ~18 days against a 21-day lead time — entering the reorder window today.",
    },
  ],
};

// ── Reorder suggestions (service-level feed) ─────────────────────────────────

export const DEMO_REORDER: {
  service_level: number;
  suggestions: Array<{
    sku_id: string;
    name: string;
    vendor: string;
    current_on_hand: number;
    reorder_point: number;
    safety_stock: number;
    order_up_to: number;
    recommended_order_qty: number;
    economic_order_qty: number;
    service_level_target: number;
    expected_stockout_prob: number;
    unit_cost: number;
    extended_cost: number;
    lead_time_days: number;
    rationale: string;
  }>;
  total_extended_cost: number;
  vendor_totals: Record<string, number>;
} = {
  service_level: 0.95,
  suggestions: [
    {
      sku_id: "sku_premium-linen-shirt-navy-m",
      name: "Premium Linen Shirt - Navy M",
      vendor: "Coastal Apparel Co.",
      current_on_hand: 48,
      reorder_point: 93,
      safety_stock: 25,
      order_up_to: 225,
      recommended_order_qty: 120,
      economic_order_qty: 140,
      service_level_target: 0.95,
      expected_stockout_prob: 0.74,
      unit_cost: 28.5,
      extended_cost: 3420,
      lead_time_days: 14,
      rationale: "On-hand below reorder point. High stockout probability. Order now.",
    },
    {
      sku_id: "sku_wool-blend-sweater-grey-l",
      name: "Wool Blend Sweater - Grey L",
      vendor: "NorthThread Supply",
      current_on_hand: 31,
      reorder_point: 76,
      safety_stock: 18,
      order_up_to: 208,
      recommended_order_qty: 200,
      economic_order_qty: 180,
      service_level_target: 0.95,
      expected_stockout_prob: 0.61,
      unit_cost: 34.2,
      extended_cost: 6840,
      lead_time_days: 18,
      rationale: "Seasonal demand rising. Place order before lead time consumes buffer.",
    },
    {
      sku_id: "sku_silk-scarf-burgundy",
      name: "Silk Scarf - Burgundy",
      vendor: "Coastal Apparel Co.",
      current_on_hand: 18,
      reorder_point: 40,
      safety_stock: 10,
      order_up_to: 100,
      recommended_order_qty: 80,
      economic_order_qty: 90,
      service_level_target: 0.95,
      expected_stockout_prob: 0.53,
      unit_cost: 19.0,
      extended_cost: 1520,
      lead_time_days: 14,
      rationale: "Below reorder point. Consolidate into Coastal PO to save freight.",
    },
    {
      sku_id: "sku_slim-fit-chinos-khaki-32x30",
      name: "Slim Fit Chinos - Khaki 32×30",
      vendor: "Pacific Goods Ltd.",
      current_on_hand: 73,
      reorder_point: 86,
      safety_stock: 20,
      order_up_to: 225,
      recommended_order_qty: 150,
      economic_order_qty: 160,
      service_level_target: 0.95,
      expected_stockout_prob: 0.38,
      unit_cost: 22.0,
      extended_cost: 3300,
      lead_time_days: 21,
      rationale: "Within reorder window given 21-day lead time. Place now.",
    },
  ],
  total_extended_cost: 15080,
  vendor_totals: {
    "Coastal Apparel Co.": 4940,
    "NorthThread Supply": 6840,
    "Pacific Goods Ltd.": 3300,
  },
};

// ── Alert rules & events ─────────────────────────────────────────────────────

export const DEMO_ALERT_RULES = {
  rules: [
    {
      id: "rule_stockout-critical",
      name: "Stockout risk — critical",
      trigger: "stockout_risk" as const,
      severity: "critical" as const,
      channels: ["email" as const, "slack" as const],
      threshold: 0.7,
      enabled: true,
      created_at: daysAgo(30),
      last_fired_at: daysAgo(1),
    },
    {
      id: "rule_stockout-warning",
      name: "Stockout risk — warning",
      trigger: "stockout_risk" as const,
      severity: "warning" as const,
      channels: ["email" as const],
      threshold: 0.4,
      enabled: true,
      created_at: daysAgo(30),
      last_fired_at: daysAgo(2),
    },
    {
      id: "rule_dead-stock",
      name: "Dead stock detected",
      trigger: "dead_stock" as const,
      severity: "warning" as const,
      channels: ["email" as const],
      threshold: 60,
      enabled: true,
      created_at: daysAgo(45),
      last_fired_at: daysAgo(7),
    },
    {
      id: "rule_forecast-miss",
      name: "Forecast accuracy miss",
      trigger: "forecast_miss" as const,
      severity: "info" as const,
      channels: ["email" as const],
      threshold: 0.15,
      enabled: false,
      created_at: daysAgo(14),
      last_fired_at: null,
    },
  ],
};

export const DEMO_ALERT_EVENTS = {
  events: [
    {
      id: "evt_001",
      rule_id: "rule_stockout-critical",
      rule_name: "Stockout risk — critical",
      severity: "critical" as const,
      trigger: "stockout_risk" as const,
      sku_id: "sku_premium-linen-shirt-navy-m",
      sku_name: "Premium Linen Shirt - Navy M",
      message: "Stockout probability reached 74% — reorder immediately.",
      fired_at: daysAgo(1),
      channels_sent: ["email" as const, "slack" as const],
      delivered: true,
    },
    {
      id: "evt_002",
      rule_id: "rule_stockout-critical",
      rule_name: "Stockout risk — critical",
      severity: "critical" as const,
      trigger: "stockout_risk" as const,
      sku_id: "sku_wool-blend-sweater-grey-l",
      sku_name: "Wool Blend Sweater - Grey L",
      message: "Stockout probability reached 61% during seasonal demand spike.",
      fired_at: daysAgo(2),
      channels_sent: ["email" as const, "slack" as const],
      delivered: true,
    },
    {
      id: "evt_003",
      rule_id: "rule_stockout-warning",
      rule_name: "Stockout risk — warning",
      severity: "warning" as const,
      trigger: "stockout_risk" as const,
      sku_id: "sku_silk-scarf-burgundy",
      sku_name: "Silk Scarf - Burgundy",
      message: "Stockout probability at 53% — within the next replenishment window.",
      fired_at: daysAgo(3),
      channels_sent: ["email" as const],
      delivered: true,
    },
    {
      id: "evt_004",
      rule_id: "rule_dead-stock",
      rule_name: "Dead stock detected",
      severity: "warning" as const,
      trigger: "dead_stock" as const,
      sku_id: "sku_running-shorts-blue-m",
      sku_name: "Running Shorts - Blue M",
      message: "94 days since last sale — liquidation plan recommended.",
      fired_at: daysAgo(7),
      channels_sent: ["email" as const],
      delivered: true,
    },
  ],
};

export const DEMO_ALERT_CHANNELS = {
  channels: [
    { channel: "email" as const, enabled: true, target: "demo@skubase.io", verified: true },
    { channel: "slack" as const, enabled: true, target: "#inventory-alerts", verified: true },
    { channel: "sms" as const, enabled: false, target: "", verified: false },
    { channel: "webhook" as const, enabled: false, target: "", verified: false },
  ],
};

// ── Action feed (api.ts) ──────────────────────────────────────────────────────

export const DEMO_ACTION_FEED = {
  data_source: "mock" as const,
  actions: [
    // Urgent items
    {
      sku_id: "sku_premium-linen-shirt-navy-m",
      name: "Premium Linen Shirt - Navy M",
      status: "urgent" as const,
      recommended_action: "Place reorder with Coastal Apparel Co. — 120 units at $28.50.",
      explanation: "On-hand covers only 8 days. Lead time is 14 days. Stockout risk is 74%.",
      days_of_inventory: 8,
      lead_time_days_used: 14,
      safety_buffer_days: 5,
      lead_time_source: "vendor" as const,
      target_coverage_days: 45,
      priority_score: 98,
      data_quality_confidence: "high" as const,
      data_quality_warnings: [],
      urgency_level: "critical" as const,
      days_until_stockout: 8,
      estimated_profit_impact: 2940,
    },
    {
      sku_id: "sku_silk-scarf-burgundy",
      name: "Silk Scarf - Burgundy",
      status: "urgent" as const,
      recommended_action: "Expedite reorder — add to next Coastal Apparel PO.",
      explanation: "18 units on hand, selling 3.3/day. Stockout in ~5 days.",
      days_of_inventory: 5,
      lead_time_days_used: 14,
      safety_buffer_days: 5,
      lead_time_source: "vendor" as const,
      target_coverage_days: 45,
      priority_score: 95,
      data_quality_confidence: "medium" as const,
      data_quality_warnings: ["Fewer than 60 historical data points"],
      urgency_level: "critical" as const,
      days_until_stockout: 5,
      estimated_profit_impact: 1770,
    },
    {
      sku_id: "sku_wool-blend-sweater-grey-l",
      name: "Wool Blend Sweater - Grey L",
      status: "urgent" as const,
      recommended_action: "Order 200 units from NorthThread Supply before lead time expires.",
      explanation: "31 units cover ~8 days. 18-day lead time means order needed today.",
      days_of_inventory: 8,
      lead_time_days_used: 18,
      safety_buffer_days: 7,
      lead_time_source: "vendor" as const,
      target_coverage_days: 60,
      priority_score: 91,
      data_quality_confidence: "high" as const,
      data_quality_warnings: [],
      urgency_level: "high" as const,
      days_until_stockout: 8,
      estimated_profit_impact: 2130,
    },
    {
      sku_id: "sku_slim-fit-chinos-khaki-32x30",
      name: "Slim Fit Chinos - Khaki 32×30",
      status: "urgent" as const,
      recommended_action: "Place order with Pacific Goods Ltd. — 150 units.",
      explanation: "73 on hand = 18 days cover. 21-day lead time — in the reorder window.",
      days_of_inventory: 18,
      lead_time_days_used: 21,
      safety_buffer_days: 5,
      lead_time_source: "vendor" as const,
      target_coverage_days: 60,
      priority_score: 84,
      data_quality_confidence: "high" as const,
      data_quality_warnings: [],
      urgency_level: "high" as const,
      days_until_stockout: 18,
      estimated_profit_impact: 1490,
    },
    // Optimize items
    {
      sku_id: "sku_organic-cotton-hoodie-black-xl",
      name: "Organic Cotton Hoodie - Black XL",
      status: "optimize" as const,
      recommended_action: "Transfer 60 units to Chicago warehouse to reduce NYC overstock.",
      explanation: "214 units on hand = 44 days cover. Target is 30 days. $5,890 excess capital.",
      days_of_inventory: 44,
      lead_time_days_used: 18,
      safety_buffer_days: 7,
      lead_time_source: "vendor" as const,
      target_coverage_days: 30,
      priority_score: 62,
      data_quality_confidence: "high" as const,
      data_quality_warnings: [],
      excess_units: 68,
      cash_tied_up: 5890,
    },
    {
      sku_id: "sku_canvas-tote-bag-natural",
      name: "Canvas Tote Bag - Natural",
      status: "optimize" as const,
      recommended_action: "Hold — no reorder needed. Let stock run down naturally.",
      explanation: "188 units = 99 days cover. Well above target. Skip next reorder cycle.",
      days_of_inventory: 99,
      lead_time_days_used: 12,
      safety_buffer_days: 5,
      lead_time_source: "category" as const,
      target_coverage_days: 45,
      priority_score: 41,
      data_quality_confidence: "high" as const,
      data_quality_warnings: [],
      excess_units: 103,
      cash_tied_up: 2420,
    },
    {
      sku_id: "sku_classic-polo-white-s",
      name: "Classic Polo - White S",
      status: "optimize" as const,
      recommended_action: "Run 20% markdown to reduce excess inventory before next season.",
      explanation: "142 units, erratic demand, 94-day cover against a 45-day target.",
      days_of_inventory: 94,
      lead_time_days_used: 14,
      safety_buffer_days: 5,
      lead_time_source: "vendor" as const,
      target_coverage_days: 45,
      priority_score: 38,
      data_quality_confidence: "low" as const,
      data_quality_warnings: ["High demand variability (CV > 0.6)", "Erratic sales pattern detected"],
      excess_units: 74,
      cash_tied_up: 2840,
    },
    // Dead items
    {
      sku_id: "sku_running-shorts-blue-m",
      name: "Running Shorts - Blue M",
      status: "dead" as const,
      recommended_action: "Wholesale liquidation — 318 units at ~$6/unit to recover capital.",
      explanation: "94 days since last sale. Off-season. $3,021 capital locked up.",
      days_of_inventory: 0,
      lead_time_days_used: 14,
      safety_buffer_days: 5,
      lead_time_source: "global_default" as const,
      target_coverage_days: 45,
      priority_score: 31,
      data_quality_confidence: "high" as const,
      data_quality_warnings: [],
      excess_units: 318,
      cash_tied_up: 3021,
    },
    {
      sku_id: "sku_leather-wallet-brown",
      name: "Leather Wallet - Brown",
      status: "dead" as const,
      recommended_action: "40% markdown or bundle into gift set to stimulate movement.",
      explanation: "67 days since last sale. 204 units. $4,284 tied up.",
      days_of_inventory: 0,
      lead_time_days_used: 14,
      safety_buffer_days: 5,
      lead_time_source: "global_default" as const,
      target_coverage_days: 45,
      priority_score: 28,
      data_quality_confidence: "medium" as const,
      data_quality_warnings: ["Demand history sparse — fewer than 20 data points"],
      excess_units: 204,
      cash_tied_up: 4284,
    },
    {
      sku_id: "sku_denim-jacket-indigo-l",
      name: "Denim Jacket - Indigo L",
      status: "dead" as const,
      recommended_action: "Bundle with Classic Polo for spring promo or take a 25% markdown.",
      explanation: "Post-season slowdown. 156 units = $6,006 at cost with declining velocity.",
      days_of_inventory: 0,
      lead_time_days_used: 14,
      safety_buffer_days: 5,
      lead_time_source: "global_default" as const,
      target_coverage_days: 45,
      priority_score: 24,
      data_quality_confidence: "medium" as const,
      data_quality_warnings: [],
      excess_units: 156,
      cash_tied_up: 6006,
    },
  ],
};
