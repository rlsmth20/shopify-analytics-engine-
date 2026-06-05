export type BillingCycle = "monthly" | "annual";
export type PlanTierKey = "starter" | "growth" | "scale";
export type CapabilityKey =
  | "today"
  | "actionQueue"
  | "basicAlerts"
  | "basicReports"
  | "inventoryHealth"
  | "deadStock"
  | "forecast"
  | "purchaseOrders"
  | "advancedReports"
  | "bundleOpportunities"
  | "projectedStockHealth"
  | "inventoryRules"
  | "supplierScorecards"
  | "transfers";
export type PlanKey =
  | "starter_monthly"
  | "growth_monthly"
  | "scale_monthly"
  | "starter_annual"
  | "growth_annual"
  | "scale_annual";

export type TierFeature = {
  label: string;
  included: boolean;
};

export type PricingTier = {
  key: PlanTierKey;
  name: string;
  pitch: string;
  limit: string;
  featured: boolean;
  features: TierFeature[];
  monthly: {
    plan: Extract<PlanKey, `${string}_monthly`>;
    price: string;
  };
  annual: {
    plan: Extract<PlanKey, `${string}_annual`>;
    price: string;
    yearTotal: string;
  };
};

export const TIER_ORDER: Record<PlanTierKey, number> = {
  starter: 0,
  growth: 1,
  scale: 2,
};

export type PlanCapability = {
  requiredPlan: PlanTierKey;
  title: string;
  description: string;
  cta: string;
};

export const PLAN_CAPABILITIES: Record<CapabilityKey, PlanCapability> = {
  today: {
    requiredPlan: "starter",
    title: "Today",
    description: "Review the most important inventory signals for your Shopify store.",
    cta: "Choose Starter",
  },
  actionQueue: {
    requiredPlan: "starter",
    title: "Action Queue",
    description: "Work through ranked stockout, reorder, and dead-stock recommendations.",
    cta: "Choose Starter",
  },
  basicAlerts: {
    requiredPlan: "starter",
    title: "Alerts & Rules",
    description: "Monitor stockout risk, dead stock, overstock, forecast risk, and reorder needs.",
    cta: "Choose Starter",
  },
  basicReports: {
    requiredPlan: "starter",
    title: "Reports & Exports",
    description: "Review and export core inventory reports from connected Shopify data.",
    cta: "Choose Starter",
  },
  inventoryHealth: {
    requiredPlan: "starter",
    title: "Inventory Health",
    description: "Understand stockout risk, slow movers, cash tied up, and SKU health.",
    cta: "Choose Starter",
  },
  deadStock: {
    requiredPlan: "starter",
    title: "Dead Stock",
    description: "Find slow-moving inventory and prioritize recovery opportunities.",
    cta: "Choose Starter",
  },
  forecast: {
    requiredPlan: "growth",
    title: "Forecast & replenishment",
    description: "Forecast future demand, calculate reorder needs, and see when inventory needs attention.",
    cta: "Upgrade to Growth",
  },
  purchaseOrders: {
    requiredPlan: "growth",
    title: "Reorder / POs",
    description: "Turn reorder recommendations into saved PO drafts and receipt history.",
    cta: "Upgrade to Growth",
  },
  advancedReports: {
    requiredPlan: "growth",
    title: "Advanced Reports & Exports",
    description: "Filter, review, and export deeper reorder, stockout, and dead-stock reports.",
    cta: "Upgrade to Growth",
  },
  bundleOpportunities: {
    requiredPlan: "growth",
    title: "Bundle Opportunities",
    description: "Use order history to find products customers already buy together.",
    cta: "Upgrade to Growth",
  },
  projectedStockHealth: {
    requiredPlan: "growth",
    title: "Projected Stock Health",
    description: "Compare stock cover, lead time, and target coverage for each SKU.",
    cta: "Upgrade to Growth",
  },
  inventoryRules: {
    requiredPlan: "growth",
    title: "Inventory Rules",
    description: "Customize lead times, safety buffer, target coverage, and reorder assumptions.",
    cta: "Upgrade to Growth",
  },
  supplierScorecards: {
    requiredPlan: "scale",
    title: "Supplier Scorecards",
    description: "Measure supplier performance when PO receipt history is available.",
    cta: "Upgrade to Scale",
  },
  transfers: {
    requiredPlan: "scale",
    title: "Transfer Planning",
    description: "Balance inventory across locations when location-level Shopify inventory is available.",
    cta: "Upgrade to Scale",
  },
};

export const PRICING_TIERS: PricingTier[] = [
  {
    key: "starter",
    name: "Starter",
    pitch: "For smaller Shopify brands replacing spreadsheets and basic inventory alerts.",
    limit: "Up to 500 active SKUs - 1 location - 3 seats",
    featured: false,
    features: [
      { label: "Basic inventory alerts and Action Queue", included: true },
      { label: "Storewide stockout and dead-stock monitoring", included: true },
      { label: "Automatic email + Slack alerts when enabled rules match", included: true },
      { label: "Basic custom thresholds for stockout, overstock, and dead-stock triggers", included: true },
      { label: "Reorder recommendations from smart defaults", included: true },
      { label: "Reports & Exports", included: true },
      { label: "Shopify sync", included: true },
      { label: "14-day free trial", included: true },
      { label: "SMS + webhook alert channels", included: false },
      { label: "Supplier scorecards when PO receipt history is connected", included: false },
      { label: "Bundle Opportunities and transfer planning", included: false },
      { label: "Admin roles and audit history", included: false },
    ],
    monthly: { plan: "starter_monthly", price: "$29" },
    annual: { plan: "starter_annual", price: "$24.65", yearTotal: "$296" },
  },
  {
    key: "growth",
    name: "Growth",
    pitch: "For growing Shopify brands that need configurable alerts, reorder planning, and inventory reporting.",
    limit: "Up to 5,000 active SKUs - 3 locations - unlimited seats",
    featured: true,
    features: [
      { label: "Everything in Starter", included: true },
      { label: "Configurable storewide alert rules for stockout, overstock, dead stock, forecast risk, and supplier slip", included: true },
      { label: "SMS + webhook alert channels", included: true },
      { label: "Configurable lead times and target coverage", included: true },
      { label: "Reorder / PO planning with styled export", included: true },
      { label: "Projected Stock Health", included: true },
      { label: "Bundle Opportunities from order history", included: true },
      { label: "Advanced Reports & Exports", included: true },
      { label: "Supplier and lead-time insights when data exists", included: true },
      { label: "Scheduled report preferences", included: true },
      { label: "Admin roles and audit history", included: false },
    ],
    monthly: { plan: "growth_monthly", price: "$99" },
    annual: { plan: "growth_annual", price: "$84.15", yearTotal: "$1,010" },
  },
  {
    key: "scale",
    name: "Scale",
    pitch: "For larger catalogs, multi-location operators, and teams that need deeper planning.",
    limit: "Up to 25,000 active SKUs - 10 locations - unlimited seats",
    featured: false,
    features: [
      { label: "Everything in Growth", included: true },
      { label: "Multi-location transfer planning when location-level inventory is available", included: true },
      { label: "Higher-volume catalog support", included: true },
      { label: "Supplier scorecards when PO receipt history exists", included: true },
      { label: "Advanced planning views", included: true },
      { label: "Advanced alert routing through enabled channels; targeting expands as data support grows", included: true },
      { label: "Priority support (same-business-day response)", included: true },
      { label: "Onboarding concierge", included: true },
      { label: "14-day free trial", included: true },
    ],
    monthly: { plan: "scale_monthly", price: "$199" },
    annual: { plan: "scale_annual", price: "$169.15", yearTotal: "$2,030" },
  },
];

export const PLAN_LABELS: Record<string, string> = {
  starter_monthly: "Starter ($29/mo)",
  growth_monthly: "Growth ($99/mo)",
  scale_monthly: "Scale ($199/mo)",
  starter_annual: "Starter (annual)",
  growth_annual: "Growth (annual)",
  scale_annual: "Scale (annual)",
  none: "No active plan",
};

export function planToTier(plan: string | null | undefined): PlanTierKey | null {
  if (!plan || plan === "none") return null;
  if (plan.startsWith("starter_")) return "starter";
  if (plan.startsWith("growth_")) return "growth";
  if (plan.startsWith("scale_")) return "scale";
  return null;
}

export function tierAllows(
  tier: PlanTierKey | null,
  minimum: PlanTierKey,
): boolean {
  if (!tier) return false;
  return TIER_ORDER[tier] >= TIER_ORDER[minimum];
}

export function requiresPlan(capability: CapabilityKey): PlanTierKey {
  return PLAN_CAPABILITIES[capability].requiredPlan;
}

export function hasCapability(
  tier: PlanTierKey | null,
  capability: CapabilityKey,
): boolean {
  return tierAllows(tier, requiresPlan(capability));
}

export function planDisplayName(tier: PlanTierKey): string {
  if (tier === "starter") return "Starter";
  if (tier === "growth") return "Growth";
  return "Scale";
}
