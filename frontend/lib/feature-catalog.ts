/**
 * Single source of truth for what skubase does and which plan includes it.
 *
 * Used by the /features marketing page (cards + explanations) and the
 * pricing page comparison matrix, so the two can never drift apart.
 * Availability values mirror backend CAPABILITY_MIN_PLAN — if a feature
 * moves tiers there, update it here in the same change.
 */

export type FeatureAvailability = boolean | "basic" | "full" | "planned";

export type CatalogFeature = {
  name: string;
  /** What it does and why it matters — plain merchant language. */
  description: string;
  /** Honest requirement note, shown smaller (e.g. needs PO receipt history). */
  detail?: string;
  /** In-app page the demo opens. */
  demoHref?: string;
  starter: FeatureAvailability;
  growth: FeatureAvailability;
  scale: FeatureAvailability;
};

export type CatalogGroup = {
  key: string;
  title: string;
  tagline: string;
  features: CatalogFeature[];
};

export const FEATURE_CATALOG: CatalogGroup[] = [
  {
    key: "daily",
    title: "Know what to do first",
    tagline:
      "skubase opens with a ranked list of decisions, not a wall of dashboards. Work it from the top.",
    features: [
      {
        name: "Dashboard",
        description:
          "One screen with the signals that matter: inventory value over time, urgent actions, stockout exposure, and cash tied up in slow stock.",
        demoHref: "/dashboard?demo=1",
        starter: true,
        growth: true,
        scale: true,
      },
      {
        name: "Action Queue",
        description:
          "Every SKU ranked urgent / optimize / dead with a recommended action and the dollar impact of doing it — or ignoring it. The full queue, on every plan.",
        demoHref: "/actions?demo=1",
        starter: true,
        growth: true,
        scale: true,
      },
      {
        name: "Inventory Health",
        description:
          "Stockout risk, slow movers, overstock, and SKU-level health scores so you can see where the catalog is strong and where it leaks cash.",
        demoHref: "/analytics?demo=1",
        starter: true,
        growth: true,
        scale: true,
      },
      {
        name: "Alerts & Rules",
        description:
          "Configurable rules for stockout risk, reorder deadlines, overstock, dead stock, forecast risk, and supplier slip — evaluated automatically, delivered by email or Slack.",
        detail: "SMS is planned.",
        demoHref: "/alerts?demo=1",
        starter: true,
        growth: true,
        scale: true,
      },
      {
        name: "Webhook alert channel",
        description:
          "Send alert payloads to any endpoint — Zapier, Make, or your own systems — alongside email and Slack.",
        demoHref: "/alerts?demo=1",
        starter: false,
        growth: true,
        scale: true,
      },
      {
        name: "Monday Buy List email",
        description:
          "A weekly email digest of what to reorder this week, with quantities and cash required — before you open the app.",
        demoHref: "/dashboard?demo=1",
        starter: true,
        growth: true,
        scale: true,
      },
    ],
  },
  {
    key: "replenishment",
    title: "Never run out",
    tagline:
      "Forecasts you can interrogate: every recommended quantity shows the demand, lead time, and risk math behind it.",
    features: [
      {
        name: "Demand forecasting",
        description:
          "90-day forecasts from sales velocity with weekly seasonality, plus a stockout probability per SKU instead of a vague \"low stock\" flag.",
        demoHref: "/forecast?demo=1",
        starter: false,
        growth: true,
        scale: true,
      },
      {
        name: "Projected Stock Health",
        description:
          "Days of cover vs. lead time vs. target coverage for each SKU, projected forward so you see problems before they are problems.",
        demoHref: "/forecast?demo=1",
        starter: false,
        growth: true,
        scale: true,
      },
      {
        name: "Reorder / Purchase Orders",
        description:
          "Reorder recommendations become PO drafts with quantities, landed cost, and supplier grouping — then receipts close the loop and feed supplier scorecards.",
        demoHref: "/purchase-orders?demo=1",
        starter: false,
        growth: true,
        scale: true,
      },
      {
        name: "Open-to-buy cash plan",
        description:
          "The cash required for the recommended buys, grouped by supplier and urgency, so the buy plan fits the bank balance.",
        demoHref: "/purchase-orders?demo=1",
        starter: false,
        growth: true,
        scale: true,
      },
      {
        name: "Inventory Rules",
        description:
          "Your lead times, safety buffer, and target coverage — by vendor, category, or SKU — so recommendations match how your supply chain actually behaves.",
        demoHref: "/lead-time-settings?demo=1",
        starter: false,
        growth: true,
        scale: true,
      },
    ],
  },
  {
    key: "cash",
    title: "Recover cash from dead stock",
    tagline:
      "Slow stock is not a report, it is trapped cash. skubase attaches a recovery plan and a dollar figure to every stale SKU.",
    features: [
      {
        name: "Dead Stock liquidation plans",
        description:
          "Every dead SKU gets a practical tactic — markdown, bundle, wholesale, or write-off — with capital tied up and projected recovery attached.",
        demoHref: "/liquidation?demo=1",
        starter: true,
        growth: true,
        scale: true,
      },
      {
        name: "Bundle Opportunities",
        description:
          "Order history reveals what customers already buy together, so you can launch bundles and kits with demand evidence instead of guesses.",
        demoHref: "/bundles?demo=1",
        starter: false,
        growth: true,
        scale: true,
      },
      {
        name: "Dead-stock bundle pairings",
        description:
          "Pairs a dead SKU with a fast mover it historically sells alongside, and computes the blended margin so the bundle clears stock without giving it away.",
        demoHref: "/liquidation?demo=1",
        starter: false,
        growth: true,
        scale: true,
      },
    ],
  },
  {
    key: "reporting",
    title: "Reports that leave the app",
    tagline:
      "Branded Excel workbooks with summaries, charts, and totals — built for the Monday meeting, not just the browser tab.",
    features: [
      {
        name: "Reports & Exports",
        description:
          "Reorder, stockout, dead-stock, and inventory action reports with filtering — exported as styled Excel workbooks with KPI summaries, charts, and totals rows.",
        detail: "Starter includes core report previews; Growth unlocks filtering and every export.",
        demoHref: "/reports?demo=1",
        starter: "basic",
        growth: "full",
        scale: "full",
      },
      {
        name: "Scheduled email reports",
        description:
          "Pick a report, a cadence, and a recipient — skubase emails it weekly (Monday morning) or monthly (the 1st) with a deep link back into the workflow.",
        demoHref: "/reports?demo=1",
        starter: false,
        growth: false,
        scale: true,
      },
      {
        name: "Sync health",
        description:
          "A visible indicator of when the store last synced and exactly what went wrong if it didn't — no silent staleness.",
        demoHref: "/store-sync?demo=1",
        starter: true,
        growth: true,
        scale: true,
      },
    ],
  },
  {
    key: "scale",
    title: "Operate at scale",
    tagline:
      "Multi-location, supplier accountability, and team controls for operations that outgrew one warehouse and one buyer.",
    features: [
      {
        name: "Supplier insights",
        description:
          "Lead-time behavior by supplier, surfaced wherever it changes a reorder decision.",
        demoHref: "/suppliers?demo=1",
        starter: false,
        growth: true,
        scale: true,
      },
      {
        name: "Supplier scorecards",
        description:
          "On-time delivery, fill rate, lead-time stability, and cost stability per supplier — measured from PO receipt history, exported as a scorecard workbook.",
        detail: "Needs purchase-order receipt history to measure against.",
        demoHref: "/suppliers?demo=1",
        starter: false,
        growth: false,
        scale: true,
      },
      {
        name: "Multi-location transfers",
        description:
          "Rebalancing recommendations that move stock from where it sits to where it sells, with units-to-move totals and a styled export.",
        detail: "Needs location-level Shopify inventory.",
        demoHref: "/transfers?demo=1",
        starter: false,
        growth: false,
        scale: true,
      },
      {
        name: "Team controls",
        description: "Admin roles and audit history for teams where more than one person touches the buy plan.",
        starter: false,
        growth: false,
        scale: true,
      },
      {
        name: "Priority support",
        description: "Same-business-day responses, plus onboarding concierge for larger catalogs.",
        starter: false,
        growth: false,
        scale: true,
      },
      {
        name: "SMS alerts",
        description: "Text-message delivery for critical alerts.",
        detail: "Planned — will land on Growth and Scale when it ships.",
        starter: false,
        growth: "planned",
        scale: "planned",
      },
    ],
  },
  {
    key: "connect",
    title: "Connect your data in minutes",
    tagline:
      "Shopify-first with a read-only sync — and CSV paths that work even before you connect a store.",
    features: [
      {
        name: "Shopify sync",
        description:
          "Read-only sync of products, inventory, and order history. skubase never writes to your store — it cannot change quantities, prices, or orders.",
        demoHref: "/store-sync?demo=1",
        starter: true,
        growth: true,
        scale: true,
      },
      {
        name: "Stocky CSV import",
        description:
          "Bring your Stocky catalog across in one upload — the migration checklist walks the whole move.",
        demoHref: "/stocky-migration?demo=1",
        starter: true,
        growth: true,
        scale: true,
      },
      {
        name: "ShipStation CSV import",
        description:
          "Shipment history from ShipStation covers Amazon, eBay, and Walmart velocity, so forecasts see your whole demand picture.",
        starter: true,
        growth: true,
        scale: true,
      },
    ],
  },
];

export type TierColumn = "starter" | "growth" | "scale";

export const TIER_COLUMNS: { key: TierColumn; label: string }[] = [
  { key: "starter", label: "Starter" },
  { key: "growth", label: "Growth" },
  { key: "scale", label: "Scale" },
];

/** Lowest plan that includes the feature, for the badge on feature cards. */
export function availabilityBadge(feature: CatalogFeature): string {
  if (feature.growth === "planned" || feature.scale === "planned") return "Planned";
  if (feature.starter) return "All plans";
  if (feature.growth) return "Growth and up";
  if (feature.scale) return "Scale";
  return "Planned";
}
