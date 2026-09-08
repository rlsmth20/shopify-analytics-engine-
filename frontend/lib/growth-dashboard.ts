/** Presentation helpers for the owner-only HTTP snapshot. No backend imports. */
export type GrowthCount = number | null | undefined;
export const growthNumber = (value: GrowthCount) => typeof value === "number" && Number.isFinite(value)
  ? new Intl.NumberFormat("en-US").format(value) : "Unknown";
export const growthMoney = (value: GrowthCount) => typeof value === "number" && Number.isFinite(value)
  ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: value > 0 && value < 1 ? 4 : 2 }).format(value) : "Unknown";
export const growthPercent = (value: GrowthCount) => typeof value === "number" && Number.isFinite(value)
  ? `${Math.round(value * 100)}%` : "Unknown";
export const growthLabel = (value?: string | null) => value ? value.replaceAll("_", " ") : "Not recorded";
export const growthTime = (value?: number | null) => value && Number.isFinite(value)
  ? new Date(value * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "Not yet recorded";
export const chartWidth = (value: GrowthCount, maximum: number) => typeof value === "number" && Number.isFinite(value) && maximum > 0
  ? Math.max(0, Math.min(100, value / maximum * 100)) : 0;
export function outcomeLabel(observed: number, linked: number, contacted: number) {
  if (contacted === 0 || (observed === 0 && linked < contacted)) return "Unknown";
  return `${growthNumber(observed)}${linked < contacted ? "+" : ""}`;
}
export const FUNNEL_STAGES = [
  ["VISITOR", "Visitors"], ["SIGNUP", "Accounts created"], ["SHOPIFY_CONNECTION", "Shopify connected"],
  ["INVENTORY_ANALYSIS_VIEWED", "Useful analysis viewed"], ["TRIAL_STARTED", "Trials started"],
  ["SUBSCRIPTION_PURCHASED", "Verified purchases"],
] as const;
export type GrowthCohort = {
  id: string; experiment_id: string; channel: string; icp: string | null; offer: string | null;
  message_version: number | string | null; sent: number; pending: number; mature: number;
  email_delivered: number | null; email_bounced: number | null; delivery_unknown: number;
  substantive_replies: number; positive_interest: number; linked_contacts: number;
  first_sent_at: number | null; latest_sent_at: number | null; outcomes: Record<string, number>;
  outcome_linkage_complete: boolean; substantive_reply_rate: number | null; positive_interest_rate: number | null;
};
export type GrowthActivityDay = { day: string; first_contacts: number; substantive_replies: number };
export type GrowthInboxTransport = {
  status?: "disabled" | "configuration_required" | "not_checked" | "poll_failed" | "poll_stale" | "verification_unrecorded" | "verification_stale" | "verified";
  mailbox?: string;
  label?: string;
  explanation?: string;
  last_poll_at?: number | null;
  last_poll_status?: "success" | "failed" | null;
  last_successful_poll_at?: number | null;
  last_approved_receipt_at?: number | null;
  last_approved_receipt_observed_at?: number | null;
  last_bridge_verified_at?: number | null;
  latest_poll_replies_ingested?: number | null;
  verification_due_after_seconds?: number | null;
  poll_stale_after_seconds?: number | null;
};

const inboxTimestamp = (value?: number | null) => typeof value === "number" && Number.isFinite(value) && value > 0 ? value : null;

/** Polling, copied receipts and delivery verification are independent evidence. */
export function growthInboxView(inbox?: GrowthInboxTransport | null) {
  const labels = {
    disabled: "Inbox monitoring disabled",
    configuration_required: "Inbox setup needed",
    not_checked: "Inbox not yet checked",
    poll_failed: "Latest inbox check failed",
    poll_stale: "Inbox check overdue",
    verification_unrecorded: "Reply delivery not yet verified",
    verification_stale: "Reply delivery verification is old",
    verified: "Reply delivery recently verified",
  };
  const recognized = inbox?.status && Object.hasOwn(labels, inbox.status) ? inbox.status : null;
  const verifiedAt = inboxTimestamp(inbox?.last_bridge_verified_at);
  const status = recognized === "verified" && !verifiedAt ? null : recognized;
  const lastPollAt = inboxTimestamp(inbox?.last_poll_at);
  const lastSuccessfulPollAt = inboxTimestamp(inbox?.last_successful_poll_at);
  const latestReplies = typeof inbox?.latest_poll_replies_ingested === "number"
    && Number.isSafeInteger(inbox.latest_poll_replies_ingested) && inbox.latest_poll_replies_ingested >= 0
    && lastPollAt && inbox.last_poll_status === "success" && status !== "poll_failed" ? inbox.latest_poll_replies_ingested : null;
  return {
    label: status ? inbox?.label || labels[status] : "Inbox status unknown",
    explanation: status ? inbox?.explanation || "Mailbox checks and delivery verification are recorded separately."
      : "This snapshot does not contain confirmed inbox monitoring status.",
    warning: status !== null && status !== "verified",
    lastPollAt,
    lastSuccessfulPollAt,
    lastPollResult: inbox?.last_poll_status === "success" ? "Successful" : inbox?.last_poll_status === "failed" ? "Failed" : "Unknown",
    lastReceiptAt: inboxTimestamp(inbox?.last_approved_receipt_at),
    receiptObservedAt: inboxTimestamp(inbox?.last_approved_receipt_observed_at),
    verifiedAt,
    latestReplies,
    verificationWindowDays: typeof inbox?.verification_due_after_seconds === "number"
      && Number.isFinite(inbox.verification_due_after_seconds) && inbox.verification_due_after_seconds > 0
      ? inbox.verification_due_after_seconds / 86400 : null,
  };
}

export type GrowthSnapshot = {
  generated_at?: number;
  execution?: {
    daily_new_contact_cap: number; sent_today: number; remaining_capacity: number;
    qualified_ready: number; discovery_pending: number; acquisition_tasks_running: number;
    oldest_pending_acquisition_age: number | null; last_acquisition_action: { at: number; stage: string } | null;
    last_successful_send: number | null; current_blocker: string | null; operational_fault: string | null;
    next_action: string; next_wake_retry: number | null;
  };
  measurement?: { day_timezone: string; mission_started_at: number | null; mission_funnel: Record<string, number>; funnel_scope: string };
  mission: { qualified_users: number; target: number; qualified_definition: string };
  today: Record<string, number>; funnel: Record<string, number>;
  outreach?: { cohorts: GrowthCohort[]; activity: GrowthActivityDay[]; sent: number; pending: number;
    contact_count: number; cohort_contact_limit: number; cohorts_truncated: boolean; limitations: string };
  pipeline: { prospects: number; qualified_prospects: number; active_conversations: number; high_intent_prospects: number;
    contacts: { id: string; organization: string; status: string; source: string; contact_basis: string; suppressed?: boolean }[] };
  experiments: { counts: Record<string, number>; items: { id: string; status: string;
    specification: { hypothesis: string; primary_metric: string; channel?: string }; started_at?: number;
    result: { confidence?: string; sample_size?: number; interpretation?: string; next_action?: string; observation_pending?: boolean } }[] };
  learning: { beliefs: { key: string; claim: string; sample_size: number; confidence: number; confidence_meaning?: string;
    contradictory_evidence: number[]; credible_interval_95: number[]; updated_at?: number }[]; recent_changes: string[]; contradictions: unknown[] };
  strategy: { icp: string; positioning: string; next_action: string; biggest_uncertainty: string; priorities: string[];
    bottleneck: { stage: string; observation: string; recommended_action: string }; acquisition_hold: Record<string, unknown> };
  economics: { mrr: number | null; customers: number | null; model_api_spend: number; unresolved_cost_reservations: number;
    unknown_cost_records?: number; acquisition_spend: number; advertising_spend: number; cac: number | null; limitations: string };
  agent: { activity: string; next_action: string; last_wake: number; model: string | null; health: string; paused: boolean;
    daily_budget_usd: number; next_due?: number | null; queue_ready?: number;
    first_contact_capacity?: { limit: number; window_hours: number; used: number; remaining: number; unresolved: number;
      next_slot_at: number | null; is_target: boolean; scope: string; continue_non_outbound: boolean };
    executive?: { last_review?: number; mode?: string };
    inbox_transport?: GrowthInboxTransport | null;
    capabilities?: { requested_service_email: boolean; community_posting: boolean; payment_receipts: boolean; executive_review: string };
    errors: { id: string; kind: string; error: string; at: number }[] };
  review_queue?: { id: number; kind: string; at: number; data: { reason?: string; body?: string; destination?: string;
    observation?: string; recommended_action?: string } }[];
  recent_actions: { id: number; kind: string; at: number; source: string }[];
};
