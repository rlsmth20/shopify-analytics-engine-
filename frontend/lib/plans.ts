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
    pitch: "For solo operators and Stocky migrants picking their first replacement.",
    limit: "Up to 500 active SKUs - 1 location - 3 seats",
    featured: false,
    features: [
      { label: "Ranked action feed (urgent / optimize / dead)", included: true },
      { label: "AI-powered demand forecasting (Holt + seasonality)", included: true },
      { label: "ABC x XYZ classification", included: true },
      { label: "Supplier lead-time settings", included: true },
      { label: "Purchase order drafts with CSV export", included: true },
      { label: "Email + Slack alerts", included: true },
      { label: "Shopify-native ingestion", included: true },
      { label: "Self-serve setup", included: true },
      { label: "Supplier scorecards + tiering", included: false },
      { label: "Bundles, transfers, and liquidation plans", included: false },
      { label: "SMS + webhook alerts", included: false },
      { label: "Team roles, audit logs, SSO", included: false },
    ],
    monthly: { plan: "starter_monthly", price: "$29" },
    annual: { plan: "starter_annual", price: "$24.65", yearTotal: "$296" },
  },
  {
    key: "growth",
    name: "Growth",
    pitch: "Most merchants land here. Full intelligence stack, multi-location, no seat gates.",
    limit: "Up to 5,000 active SKUs - 3 locations - unlimited seats",
    featured: true,
    features: [
      { label: "Everything in Starter", included: true },
      { label: "Supplier scorecards + tiering when PO/receipt history is connected", included: true },
      { label: "Safety-stock / ROP / EOQ with service-level segmentation", included: true },
      { label: "Bundle / kit bottleneck analysis when component mappings are configured", included: true },
      { label: "Multi-location transfer recommendations when location inventory is connected", included: true },
      { label: "Dead-stock liquidation plans", included: true },
      { label: "PO approval workflows", included: true },
      { label: "SMS + webhook alerts", included: true },
      { label: "Scheduled PDF reports", included: true },
      { label: "Team roles, audit logs, SSO", included: false },
    ],
    monthly: { plan: "growth_monthly", price: "$99" },
    annual: { plan: "growth_annual", price: "$84.15", yearTotal: "$1,010" },
  },
  {
    key: "scale",
    name: "Scale",
    pitch: "For multi-store operators and teams that want audit + approval flows.",
    limit: "Up to 25,000 active SKUs - 10 locations - unlimited seats",
    featured: false,
    features: [
      { label: "Everything in Growth", included: true },
      { label: "Advanced PO approval + send flow", included: true },
      { label: "Audit log and decision snapshots", included: true },
      { label: "Workspace roles", included: true },
      { label: "Priority support (same-business-day response)", included: true },
      { label: "Onboarding concierge", included: true },
      { label: "SSO (Google, Microsoft)", included: true },
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
