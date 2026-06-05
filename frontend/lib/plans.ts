export type BillingCycle = "monthly" | "annual";
export type PlanTierKey = "starter" | "growth" | "scale";
export type PlanId = "none" | "trial" | PlanTierKey;
export type CapabilityKey =
  | "billing"
  | "account"
  | "store_sync"
  | "contact_feedback"
  | "stocky_migration"
  | "limited_today"
  | "today_basic"
  | "action_queue_basic"
  | "action_queue_full"
  | "alerts_basic"
  | "alerts_advanced"
  | "forecast"
  | "projected_stock_health"
  | "inventory_health_basic"
  | "inventory_health_full"
  | "reports_basic"
  | "reports_export"
  | "reorder_pos"
  | "bundle_opportunities"
  | "dead_stock_basic"
  | "dead_stock_full"
  | "suppliers_basic"
  | "supplier_scorecards"
  | "transfers"
  | "inventory_rules_basic"
  | "inventory_rules_advanced"
  | "scheduled_reports"
  | "team_controls"
  | "priority_support";
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

export const PLAN_ORDER: Record<PlanId, number> = {
  none: -1,
  trial: 99,
  starter: 0,
  growth: 1,
  scale: 2,
};

export type PlanCapability = {
  requiredPlan: PlanId;
  title: string;
  description: string;
  cta: string;
};

export const PLAN_CAPABILITIES: Record<CapabilityKey, PlanCapability> = {
  billing: {
    requiredPlan: "none",
    title: "Billing",
    description: "View plan status and manage app billing.",
    cta: "View billing",
  },
  account: {
    requiredPlan: "none",
    title: "Account",
    description: "Manage account and workspace details.",
    cta: "View account",
  },
  store_sync: {
    requiredPlan: "none",
    title: "Store Sync",
    description: "Connect Shopify and review sync status.",
    cta: "Open Store Sync",
  },
  contact_feedback: {
    requiredPlan: "none",
    title: "Contact & Feedback",
    description: "Contact support or share product feedback.",
    cta: "Contact support",
  },
  stocky_migration: {
    requiredPlan: "none",
    title: "Stocky Migration",
    description: "Use the migration checklist to move from Stocky.",
    cta: "Open checklist",
  },
  limited_today: {
    requiredPlan: "none",
    title: "Today",
    description: "See a limited starting view before choosing a plan.",
    cta: "View Today",
  },
  today_basic: {
    requiredPlan: "starter",
    title: "Today",
    description: "Review the most important inventory signals for your Shopify store.",
    cta: "Choose Starter",
  },
  action_queue_basic: {
    requiredPlan: "starter",
    title: "Basic Action Queue",
    description: "Work through basic stockout, reorder, and dead-stock recommendations.",
    cta: "Choose Starter",
  },
  action_queue_full: {
    requiredPlan: "growth",
    title: "Full Action Queue",
    description: "Work through the full ranked queue with richer action context.",
    cta: "Upgrade to Growth",
  },
  alerts_basic: {
    requiredPlan: "starter",
    title: "Basic Alerts & Rules",
    description: "Monitor stockout risk, dead stock, overstock, forecast risk, and reorder needs.",
    cta: "Choose Starter",
  },
  alerts_advanced: {
    requiredPlan: "growth",
    title: "Advanced Alerts & Rules",
    description: "Use configurable rules and alert channels for more targeted inventory monitoring.",
    cta: "Upgrade to Growth",
  },
  inventory_health_basic: {
    requiredPlan: "starter",
    title: "Inventory Health",
    description: "Understand stockout risk, slow movers, cash tied up, and SKU health.",
    cta: "Choose Starter",
  },
  inventory_health_full: {
    requiredPlan: "growth",
    title: "Full Inventory Health",
    description: "Review deeper SKU health and planning context.",
    cta: "Upgrade to Growth",
  },
  reports_basic: {
    requiredPlan: "starter",
    title: "Reports",
    description: "Review core inventory report previews from connected Shopify data.",
    cta: "Choose Starter",
  },
  reports_export: {
    requiredPlan: "growth",
    title: "Reports & Exports",
    description: "Filter, review, and export deeper reorder, stockout, and dead-stock reports.",
    cta: "Upgrade to Growth",
  },
  dead_stock_basic: {
    requiredPlan: "starter",
    title: "Dead Stock",
    description: "Find slow-moving inventory and prioritize recovery opportunities.",
    cta: "Choose Starter",
  },
  dead_stock_full: {
    requiredPlan: "growth",
    title: "Dead Stock Recovery",
    description: "Use full recovery planning and exports for slow-moving inventory.",
    cta: "Upgrade to Growth",
  },
  forecast: {
    requiredPlan: "growth",
    title: "Forecast & replenishment",
    description: "Forecast future demand, calculate reorder needs, and see when inventory needs attention.",
    cta: "Upgrade to Growth",
  },
  reorder_pos: {
    requiredPlan: "growth",
    title: "Reorder / POs",
    description: "Turn reorder recommendations into saved PO drafts and receipt history.",
    cta: "Upgrade to Growth",
  },
  bundle_opportunities: {
    requiredPlan: "growth",
    title: "Bundle Opportunities",
    description: "Use order history to find products customers already buy together.",
    cta: "Upgrade to Growth",
  },
  projected_stock_health: {
    requiredPlan: "growth",
    title: "Projected Stock Health",
    description: "Compare stock cover, lead time, and target coverage for each SKU.",
    cta: "Upgrade to Growth",
  },
  suppliers_basic: {
    requiredPlan: "growth",
    title: "Supplier Insights",
    description: "Review supplier and lead-time insights when data is available.",
    cta: "Upgrade to Growth",
  },
  inventory_rules_basic: {
    requiredPlan: "starter",
    title: "Inventory Rules",
    description: "Edit default lead time and target coverage assumptions.",
    cta: "Choose Starter",
  },
  inventory_rules_advanced: {
    requiredPlan: "growth",
    title: "Inventory Rules",
    description: "Customize lead times, safety buffer, target coverage, and reorder assumptions.",
    cta: "Upgrade to Growth",
  },
  supplier_scorecards: {
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
  scheduled_reports: {
    requiredPlan: "scale",
    title: "Scheduled Reports",
    description: "Save report schedule preferences as delivery automation expands.",
    cta: "Upgrade to Scale",
  },
  team_controls: {
    requiredPlan: "scale",
    title: "Team Controls",
    description: "Use advanced workspace controls as team administration expands.",
    cta: "Upgrade to Scale",
  },
  priority_support: {
    requiredPlan: "scale",
    title: "Priority Support",
    description: "Get same-business-day support for higher-volume operations.",
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
    monthly: { plan: "starter_monthly", price: "$49" },
    annual: { plan: "starter_annual", price: "$41.65", yearTotal: "$500" },
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
  starter_monthly: "Starter ($49/mo)",
  growth_monthly: "Growth ($99/mo)",
  scale_monthly: "Scale ($199/mo)",
  starter_annual: "Starter (annual)",
  growth_annual: "Growth (annual)",
  scale_annual: "Scale (annual)",
  none: "No active plan",
};

export function planToTier(plan: string | null | undefined): PlanTierKey | null {
  const normalized = normalizePlanName(plan);
  if (normalized === "starter" || normalized === "growth" || normalized === "scale") {
    return normalized;
  }
  return null;
}

export function normalizePlanName(plan: string | null | undefined): PlanId {
  if (!plan || plan === "none") return "none";
  const normalized = String(plan)
    .trim()
    .toLowerCase()
    .replace("skubase", "")
    .replace(/[\s-]+/g, "_");
  if (normalized === "trial" || normalized === "trialing") return "trial";
  if (normalized.includes("starter")) return "starter";
  if (normalized.includes("growth")) return "growth";
  if (normalized.includes("scale")) return "scale";
  return "none";
}

export function tierAllows(
  tier: PlanTierKey | null,
  minimum: PlanTierKey,
): boolean {
  if (!tier) return false;
  return TIER_ORDER[tier] >= TIER_ORDER[minimum];
}

export function requiresPlan(capability: CapabilityKey): PlanId {
  return PLAN_CAPABILITIES[capability].requiredPlan;
}

export function hasCapability(
  tier: PlanId | null,
  capability: CapabilityKey,
): boolean {
  if (!tier) return false;
  return PLAN_ORDER[tier] >= PLAN_ORDER[requiresPlan(capability)];
}

export function planDisplayName(tier: PlanId): string {
  if (tier === "none") return "No active plan";
  if (tier === "trial") return "Trial";
  if (tier === "starter") return "Starter";
  if (tier === "growth") return "Growth";
  return "Scale";
}

export function getUpgradeLabel(requiredPlan: PlanId): string {
  if (requiredPlan === "none" || requiredPlan === "trial") return "View billing";
  return `Upgrade to ${planDisplayName(requiredPlan)}`;
}
