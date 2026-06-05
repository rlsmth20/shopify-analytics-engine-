export type BillingCycle = "monthly" | "annual";
export type PlanTierKey = "starter" | "growth" | "scale";
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
