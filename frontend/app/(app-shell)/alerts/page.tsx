"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { DataQualityNote } from "@/components/data-quality-note";
import { useAuth } from "@/components/auth-guard";
import { fetchEntitlements, type Entitlements } from "@/lib/entitlements";
import {
  createAlertRule,
  deleteAlertRule,
  evaluateAlertsNow,
  fetchAlertEvents,
  fetchAlertRules,
  fetchChannels,
  sendTestAlert,
  retryUncertainAlert,
  toggleAlertRule,
  updateChannel,
  type AlertEvent,
  type AlertRule,
  type AlertSeverity,
  type AlertTrigger,
  type NotificationChannel,
  type NotificationChannelConfig,
} from "@/lib/api-v2";
import type { PlanTierKey } from "@/lib/plans";
import { alertError, channelState, eventDeliveryLabel, ruleHasReadyChannel, targetError, thresholdError, unsupportedTargeting } from "@/lib/alert-setup";
import styles from "./page.module.css";

const TRIGGER_OPTIONS: { value: AlertTrigger; label: string; help: string }[] = [
  { value: "stockout_risk", label: "Reorder deadline risk", help: "Alert when the last safe reorder window is inside your chosen buffer." },
  { value: "dead_stock", label: "Dead stock capital", help: "Alert when stale inventory has at least this much cash tied up." },
  { value: "overstock", label: "Excess inventory cover", help: "Alert when a SKU has extra cover beyond lead time and target coverage." },
  { value: "forecast_miss", label: "High stockout probability", help: "Alert when forecasted stockout risk reaches this percent." },
  { value: "supplier_slip", label: "Supplier on-time slip", help: "Alert when a supplier's on-time delivery rate drops below this percent." },
];

const TRIGGER_DEFAULT_VALUE: Record<AlertTrigger, number> = {
  stockout_risk: 3,
  dead_stock: 500,
  overstock: 30,
  forecast_miss: 70,
  supplier_slip: 80,
  bundle_break: 5,
  price_drop: 20,
};

const TRIGGER_VALUE_COPY: Record<
  AlertTrigger,
  { label: string; suffix: string; helper: string; example: string }
> = {
  stockout_risk: {
    label: "Alert when reorder buffer is below",
    suffix: "days",
    helper: "Example: enter 3 to alert when a SKU is 3 days or less from the point where a reorder may not arrive before stockout. Skubase calculates this as days left minus lead time.",
    example: "3",
  },
  dead_stock: {
    label: "Alert when cash tied up is above",
    suffix: "USD",
    helper: "Example: enter 500 to alert when stale inventory ties up at least $500.",
    example: "500",
  },
  overstock: {
    label: "Alert when extra cover is above",
    suffix: "days",
    helper: "Example: enter 30 to alert when a SKU has more than 30 extra days after lead time and target coverage. Skubase calculates this as days of cover minus lead time minus target coverage.",
    example: "30",
  },
  forecast_miss: {
    label: "Alert when stockout risk is above",
    suffix: "%",
    helper: "Example: enter 70 to alert when forecasted stockout risk reaches 70%.",
    example: "70",
  },
  supplier_slip: {
    label: "Alert when supplier on-time rate is below",
    suffix: "%",
    helper: "Example: enter 80 to alert when supplier on-time delivery falls below 80%.",
    example: "80",
  },
  bundle_break: {
    label: "Alert when buildable bundle units is below",
    suffix: "units",
    helper: "Example: enter 5 to alert when component stock can build fewer than 5 bundles.",
    example: "5",
  },
  price_drop: {
    label: "Alert when markdown is above",
    suffix: "%",
    helper: "Example: enter 20 to alert when a product markdown is above 20%.",
    example: "20",
  },
};

function formatRuleTriggerValue(trigger: AlertTrigger, value: number): string {
  const copy = TRIGGER_VALUE_COPY[trigger];
  if (trigger === "stockout_risk") {
    return `Reorder buffer is ${value} ${value === 1 ? "day" : "days"} or less`;
  }
  if (trigger === "dead_stock") {
    return `Cash tied up is at least $${value.toLocaleString()}`;
  }
  if (trigger === "overstock") {
    return `Extra cover is above ${value} days`;
  }
  if (trigger === "forecast_miss") {
    return `Stockout risk is at least ${value}%`;
  }
  if (trigger === "supplier_slip") {
    return `Supplier on-time rate is below ${value}%`;
  }
  return `${copy.label} ${value} ${copy.suffix}`;
}

const SEVERITY_OPTIONS: AlertSeverity[] = ["info", "warning", "critical"];
const CHANNEL_OPTIONS: NotificationChannel[] = ["email", "sms", "slack", "webhook"];
const CHANNEL_MIN_TIER: Record<NotificationChannel, PlanTierKey> = {
  email: "starter",
  slack: "starter",
  sms: "growth",
  webhook: "growth",
};

function parseList(value: string): string[] {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function listToText(values: string[]): string {
  return values.join(", ");
}

export default function AlertsPage() {
  const { user } = useAuth();
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [channels, setChannels] = useState<NotificationChannelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [tab, setTab] = useState<"rules" | "channels" | "history">("channels");
  const [entitlements, setEntitlements] = useState<Entitlements | null>(null);
  const [entitlementError, setEntitlementError] = useState<string | null>(null);
  const [schedulerEnabled, setSchedulerEnabled] = useState<boolean | null>(null);
  const [evaluationInterval, setEvaluationInterval] = useState<number | null>(null);

  const unlockAll = user.id === 0;
  const isChannelAllowed = (channel: NotificationChannel) =>
    unlockAll || user.is_admin || Boolean(entitlements?.capabilities.includes(CHANNEL_MIN_TIER[channel] === "growth" ? "alerts_advanced" : "alerts_basic"));

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (user.id === 0) return;

    void fetchEntitlements()
      .then((data) => setEntitlements(data))
      .catch(() => { setEntitlements(null); setEntitlementError("We couldn't check your plan. Reload this page before changing channel settings."); });
  }, [user.id]);

  async function refresh() {
    setLoading(true);
    try {
      const [r, c, e] = await Promise.all([
        fetchAlertRules(),
        fetchChannels(),
        fetchAlertEvents(),
      ]);
      setRules(r.rules);
      setChannels(c.channels);
      setSchedulerEnabled(typeof c.scheduler_enabled === "boolean" ? c.scheduler_enabled : null);
      setEvaluationInterval(c.evaluation_interval_seconds ?? null);
      setEvents(e.events);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function runEvaluation(dryRun: boolean) {
    setEvaluating(true);
    setError(null);
    setNotice(null);
    try {
      const result = await evaluateAlertsNow(dryRun);
      setEvents(result.events);
      setTab("history");
      if (result.events.length === 0) {
        setNotice(dryRun
          ? "Preview complete: no enabled rules matched the currently available signals. No notifications were sent."
          : "No notifications were queued. There may be no current matches or eligible channels, or matching alerts may be waiting for their next permitted send.");
      } else if (dryRun) {
        setNotice(
          `Preview complete: ${result.events.length} matching alert${
            result.events.length === 1 ? "" : "s"
          } found. No notifications were sent.`
        );
      } else {
        const deliveredCount = result.events.filter((event) => event.delivered).length;
        setNotice(
          `Send complete: ${result.events.length} matching alert${
            result.events.length === 1 ? "" : "s"
          } found; ${deliveredCount} accepted by at least one receiving service.`
        );
      }
      if (!dryRun) await refresh();
      setTab("history");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setEvaluating(false);
    }
  }

  const enabledRules = rules.filter((rule) => rule.enabled);
  const readyChannels = channels.filter((channel) => channelState(channel, isChannelAllowed(channel.channel)).ready);
  const rulesNeedingSetup = enabledRules.filter((rule) => !ruleHasReadyChannel(rule, channels, isChannelAllowed));

  return (
    <div className={`alerts-page ${styles.page}`}>
      <section className={styles.setupSummary} aria-labelledby="alerts-setup-title">
        <div><p className="section-eyebrow">Alert setup</p><h2 id="alerts-setup-title">Get stock alerts where you work</h2>
          <p>Save a destination, send a test, then choose the inventory problems you want to hear about.</p></div>
        <div className={styles.setupStatus} aria-live="polite"><strong>{loading ? "Checking setup…" : unlockAll ? "Sample workspace" : `${readyChannels.length} tested channel${readyChannels.length === 1 ? "" : "s"} enabled`}</strong>
          <span>{loading ? "Loading saved settings." : `${rulesNeedingSetup.length} of ${enabledRules.length} enabled rules need channel setup or a test.`}</span>
          <span>{schedulerEnabled === null ? "Automatic-check status unavailable" : schedulerEnabled ? `Automatic checks enabled${evaluationInterval ? ` · about every ${Math.max(1, Math.round(evaluationInterval / 60))} minutes` : ""}` : "Automatic checks are currently paused"}</span>
        </div>
      </section>
      {!loading && rulesNeedingSetup.length > 0 ? <p className={styles.setupWarning}>Enabled rules need a saved, enabled destination to send. Test the receiving inbox, Slack channel, or workflow before relying on notifications.</p> : null}
      <details className={styles.help}><summary>How inventory signals and targeting work</summary>
      <div className="content-grid content-grid-2-1 alert-context-grid">
        <DataQualityNote title="Choose broad or targeted alerts">
          <p>
            Skubase evaluates enabled rules against connected inventory,
            forecast, and supplier signals. Use targeting to narrow a rule by
            SKU, product title, category, or supplier.
          </p>
          <div className="button-row">
            <Link href="/lead-time-settings" className="button button-secondary button-sm">
              Adjust reorder assumptions
            </Link>
            <Link href="/store-sync" className="button button-secondary button-sm">
              Check store sync
            </Link>
          </div>
        </DataQualityNote>

        <DataQualityNote title="Start with a tested destination">
          <p>
            Saving a destination does not confirm a message arrived. Send a test,
            check the receiving inbox or channel, then enable the rules you need.
            Tags, collections, and location targeting are not available in this alert flow yet.
          </p>
          <div className="button-row">
            <Link href="/transfers" className="button button-secondary button-sm">
              View transfer requirements
            </Link>
            <button type="button" className="button button-primary button-sm" onClick={() => setTab("channels")}>
              Set up channels
            </button>
          </div>
        </DataQualityNote>
      </div>
      </details>

      <nav className="tab-bar" aria-label="Alert sections">
        {(["channels", "rules", "history"] as const).map((t) => (
          <button
            key={t}
            type="button"
            className={`tab-button${tab === t ? " tab-button-active" : ""}`}
            aria-current={tab === t ? "page" : undefined}
            onClick={() => setTab(t)}
          >
            {t === "rules" ? "Choose rules" : t === "channels" ? "Set up channels" : "Recent activity"}
          </button>
        ))}
        <button
          type="button"
          className="button-ghost tab-bar-trailing"
          disabled={evaluating || loading || enabledRules.length === 0}
          onClick={() => void runEvaluation(true)}
        >
          {evaluating ? "Evaluating..." : "Preview evaluation"}
        </button>
      </nav>

      {loading ? <p className="page-loading">Loading...</p> : null}
      {error ? <p className="page-error-copy" role="alert">{error}</p> : null}
      {entitlementError ? <p className="page-error-copy" role="alert">{entitlementError}</p> : null}
      {notice ? <p className={styles.message} role="status">{notice}</p> : null}

      {tab === "rules" ? (
        <RulesPanel
          rules={rules}
          onChange={refresh}
          isChannelAllowed={isChannelAllowed}
          channels={channels}
          demo={unlockAll}
          onSetup={() => setTab("channels")}
        />
      ) : null}
      {tab === "channels" ? (
        <ChannelsPanel
          channels={channels}
          onChange={refresh}
          isChannelAllowed={isChannelAllowed}
          demo={unlockAll}
        />
      ) : null}
      {tab === "history" ? <EventsPanel events={events} onChange={refresh} demo={unlockAll} /> : null}
    </div>
  );
}

function RulesPanel({
  rules,
  onChange,
  isChannelAllowed,
  channels,
  demo,
  onSetup,
}: {
  rules: AlertRule[];
  onChange: () => void;
  isChannelAllowed: (channel: NotificationChannel) => boolean;
  channels: NotificationChannelConfig[];
  demo: boolean;
  onSetup: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [newRule, setNewRule] = useState({
    name: "",
    trigger: "stockout_risk" as AlertTrigger,
    severity: "critical" as AlertSeverity,
    channels: ["email"] as NotificationChannel[],
    threshold: String(TRIGGER_DEFAULT_VALUE.stockout_risk),
    scope: "storewide" as "storewide" | "custom",
    match_mode: "all" as "all" | "any",
    target_skus: "",
    product_title_contains: "",
    categories: "",
    suppliers: "",
    tags: "",
    collections: "",
    locations: "",
    enabled: false,
  });
  const thresholdCopy = TRIGGER_VALUE_COPY[newRule.trigger];
  const readySelected = newRule.channels.some((name) => channels.some((channel) => channel.channel === name && channelState(channel, isChannelAllowed(name)).ready));

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null); setNotice(null);
    if (!newRule.name.trim()) { setError("Give this rule a name."); return; }
    const invalidThreshold = thresholdError(newRule.trigger, newRule.threshold);
    if (invalidThreshold) { setError(invalidThreshold); return; }
    if (!newRule.channels.length || newRule.channels.some((channel) => channel === "sms" || !isChannelAllowed(channel))) {
      setError("Choose at least one available channel included in your plan."); return;
    }
    if (newRule.enabled && !readySelected) { setError("Set up and test a selected channel first, or save this rule paused."); return; }
    if (newRule.scope === "custom" && ![newRule.target_skus, newRule.product_title_contains, newRule.categories, newRule.suppliers].some((value) => value.trim())) {
      setError("Add a targeting condition, or choose Storewide."); return;
    }
    setBusy("create");
    try {
      await createAlertRule({
      name: newRule.name.trim(),
      trigger: newRule.trigger,
      severity: newRule.severity,
      channels: newRule.channels,
      threshold: Number(newRule.threshold),
      enabled: newRule.enabled,
      scope: newRule.scope,
      match_mode: newRule.match_mode,
      target_skus: parseList(newRule.target_skus),
      product_title_contains: newRule.product_title_contains,
      categories: parseList(newRule.categories),
      suppliers: parseList(newRule.suppliers),
      tags: parseList(newRule.tags),
      collections: parseList(newRule.collections),
      locations: parseList(newRule.locations),
    });
      setNewRule({ ...newRule, name: "" });
      setNotice(newRule.enabled ? "Rule saved and enabled. Preview evaluation to inspect its matches." : "Rule saved paused. Enable it after testing its destination.");
      onChange();
    } catch (cause) { setError(alertError(cause, "We couldn't save this rule. Your entries are still here.")); }
    finally { setBusy(null); }
  }

  async function mutateRule(rule: AlertRule, action: "toggle" | "delete") {
    setError(null); setNotice(null);
    if (action === "toggle" && !rule.enabled && !ruleHasReadyChannel(rule, channels, isChannelAllowed)) {
      setError(`Set up and test a channel selected by “${rule.name}” before enabling it.`); return;
    }
    if (action === "toggle" && !rule.enabled && (!TRIGGER_OPTIONS.some((item) => item.value === rule.trigger) || unsupportedTargeting(rule).length)) {
      setError("Recreate this rule with a supported trigger and targeting conditions before enabling it."); return;
    }
    setBusy(rule.id);
    try {
      if (action === "delete") await deleteAlertRule(rule.id);
      else await toggleAlertRule(rule.id, !rule.enabled);
      setNotice(action === "delete" ? `Deleted “${rule.name}”.` : `${rule.enabled ? "Paused" : "Enabled"} “${rule.name}”.`);
      onChange();
    } catch (cause) { setError(alertError(cause, "We couldn't update this rule. Please try again.")); }
    finally { setBusy(null); }
  }

  return (
    <div className="alerts-rules">
      <form className="alert-rule-form" onSubmit={handleCreate}>
        <h3 className="panel-section-title">Add a rule</h3>
        <p className="panel-section-subtitle">
          Start with one important problem. Save the rule paused while you finish setting up delivery. Preview shows matches without sending.
        </p>
        <div className="alert-targeting-panel">
          <div>
            <p className="form-label">Choose what this rule applies to</p>
            <p className="form-hint">
              Use storewide rules for broad monitoring, or custom targeting for
              specific SKU, supplier, category, or product title conditions.
            </p>
          </div>
          <div className="alert-target-mode">
            <button
              type="button"
              className={`alert-targeting-option${newRule.scope === "storewide" ? " alert-targeting-option-active" : ""}`}
              aria-pressed={newRule.scope === "storewide"}
              onClick={() => setNewRule({ ...newRule, scope: "storewide" })}
            >
              <span>Storewide</span>
              <strong>{newRule.scope === "storewide" ? "Selected" : "Choose"}</strong>
              <small>Evaluate connected inventory signals across the store.</small>
            </button>
            <button
              type="button"
              className={`alert-targeting-option${newRule.scope === "custom" ? " alert-targeting-option-active" : ""}`}
              aria-pressed={newRule.scope === "custom"}
              onClick={() => setNewRule({ ...newRule, scope: "custom" })}
            >
              <span>Custom targeting</span>
              <strong>{newRule.scope === "custom" ? "Selected" : "Choose"}</strong>
              <small>Apply this rule only to matching product conditions.</small>
            </button>
          </div>
          {newRule.scope === "custom" ? (
            <div className="alert-targeting-fields">
              <label className="form-field">
                <span className="form-label">Condition matching</span>
                <select
                  value={newRule.match_mode}
                  onChange={(event) =>
                    setNewRule({ ...newRule, match_mode: event.target.value as "all" | "any" })
                  }
                >
                  <option value="all">Match all conditions</option>
                  <option value="any">Match any condition</option>
                </select>
              </label>
              <label className="form-field">
                <span className="form-label">Specific products/SKUs</span>
                <input
                  value={newRule.target_skus}
                  disabled={newRule.trigger === "supplier_slip"}
                  onChange={(event) => setNewRule({ ...newRule, target_skus: event.target.value })}
                  placeholder="sku-premium-linen, SKU-123"
                />
              </label>
              <label className="form-field">
                <span className="form-label">{newRule.trigger === "supplier_slip" ? "Supplier name contains" : "Product title contains"}</span>
                <input
                  value={newRule.product_title_contains}
                  onChange={(event) => setNewRule({ ...newRule, product_title_contains: event.target.value })}
                  placeholder="hoodie"
                />
              </label>
              <label className="form-field">
                <span className="form-label">Product categories</span>
                <input
                  value={newRule.categories}
                  disabled={newRule.trigger === "supplier_slip"}
                  onChange={(event) => setNewRule({ ...newRule, categories: event.target.value })}
                  placeholder="Apparel, Accessories"
                />
              </label>
              <label className="form-field">
                <span className="form-label">Suppliers</span>
                <input
                  value={newRule.suppliers}
                  onChange={(event) => setNewRule({ ...newRule, suppliers: event.target.value })}
                  placeholder="Coastal Apparel Co."
                />
              </label>
            </div>
          ) : null}
          <p className="form-hint">
            Conditions match against available synced data. Tags, collections, and location targeting are not available yet.
          </p>
        </div>
        <div className="form-grid">
          <label className="form-field">
            <span className="form-label">Rule name</span>
            <input
              type="text"
              required
              placeholder="e.g., AX SKUs nearing stockout"
              value={newRule.name}
              onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
            />
          </label>
          <label className="form-field">
            <span className="form-label">Trigger</span>
            <select
              value={newRule.trigger}
              onChange={(e) =>
                setNewRule({
                  ...newRule,
                  trigger: e.target.value as AlertTrigger,
                  threshold: String(TRIGGER_DEFAULT_VALUE[e.target.value as AlertTrigger]),
                  target_skus: e.target.value === "supplier_slip" ? "" : newRule.target_skus,
                  categories: e.target.value === "supplier_slip" ? "" : newRule.categories,
                })
              }
            >
              {TRIGGER_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <span className="form-hint">
              {TRIGGER_OPTIONS.find((o) => o.value === newRule.trigger)?.help}
            </span>
          </label>
          <label className="form-field">
            <span className="form-label">Severity</span>
            <select
              value={newRule.severity}
              onChange={(e) =>
                setNewRule({ ...newRule, severity: e.target.value as AlertSeverity })
              }
            >
              {SEVERITY_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span className="form-label">{thresholdCopy.label}</span>
            <input
              type="number"
              required
              min="0"
              max={["forecast_miss", "supplier_slip", "price_drop"].includes(newRule.trigger) ? "100" : undefined}
              step="any"
              placeholder={thresholdCopy.example}
              value={newRule.threshold}
              onChange={(e) =>
                setNewRule({ ...newRule, threshold: e.target.value })
              }
            />
            <span className="form-hint">
              {thresholdCopy.helper}
            </span>
          </label>
          <div className="form-field">
            <span className="form-label">Channels</span>
            <div className="channel-chips">
              {CHANNEL_OPTIONS.map((c) => {
                const active = newRule.channels.includes(c);
                const planned = c === "sms"; // SMS delivery is not live yet
                const config = channels.find((channel) => channel.channel === c);
                const allowed = !planned && isChannelAllowed(c) && config?.available !== false;
                return (
                  <button
                    key={c}
                    type="button"
                    className={`channel-chip${active ? " channel-chip-active" : ""}`}
                    aria-pressed={active}
                    disabled={(!allowed && !active) || !!busy || demo}
                    title={
                      planned
                        ? "SMS alerts are planned - use email or Slack for now."
                        : allowed
                        ? undefined
                        : `${c} alerts are included on Growth and Scale.`
                    }
                    onClick={() =>
                      setNewRule({
                        ...newRule,
                        channels: active
                          ? newRule.channels.filter((x) => x !== c)
                          : [...newRule.channels, c],
                      })
                    }
                  >
                    {planned ? "SMS (not available yet)" : allowed ? `${c} · ${config ? channelState(config, true).label : "Add destination"}` : `${c} (${isChannelAllowed(c) ? "unavailable" : CHANNEL_MIN_TIER[c] === "growth" ? "Growth" : "Starter"})`}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
        <div className={styles.ruleSetup}><button type="button" className="button button-secondary button-sm" onClick={onSetup}>Configure or test channels</button>
          <label className={styles.check}><input type="checkbox" checked={newRule.enabled} disabled={(!readySelected && !newRule.enabled) || demo || !!busy} onChange={(event) => setNewRule({ ...newRule, enabled: event.target.checked })} />Enable after saving</label>
          {!readySelected ? <p className="form-hint">No selected channel is tested and enabled yet. Save this rule paused while you finish setup.</p> : null}
        </div>
        <button type="submit" className="button-primary" disabled={!!busy || demo}>
          {busy === "create" ? "Saving rule…" : newRule.enabled ? "Save and enable rule" : "Save paused rule"}
        </button>
        {demo ? <p className="form-hint">Sign in to your own store to save live rules.</p> : null}
      </form>

      {error ? <p className={styles.error} role="alert">{error}</p> : null}
      {notice ? <p className={styles.message} role="status">{notice}</p> : null}

      <div className="rules-list">
        <h3 className="panel-section-title">Saved rules</h3>
        {rules.length === 0 ? (
          <p className="muted">No rules configured yet.</p>
        ) : null}
        {rules.map((rule) => (
          <div key={rule.id} className={`rule-card rule-sev-${rule.severity}`}>
            <div className="rule-card-main">
              <div className="rule-card-head">
                <span className={`severity-pill severity-${rule.severity}`}>
                  {rule.severity}
                </span>
                <h4 className="rule-card-title">{rule.name}</h4>
              </div>
              <p className="rule-card-body">
                <strong>
                  {TRIGGER_OPTIONS.find((t) => t.value === rule.trigger)?.label ??
                    rule.trigger}
                </strong>
                {" - "}
                {formatRuleTriggerValue(rule.trigger, rule.threshold)}
              </p>
              <div className="rule-card-channels">
                {rule.channels.map((c) => (
                  <span key={c} className="channel-pill">
                    {c}
                  </span>
                ))}
              </div>
              {rule.enabled && !ruleHasReadyChannel(rule, channels, isChannelAllowed) ? <p className={styles.setupWarning}>Enabled, but no selected channel is currently tested and ready. Check channel setup.</p> : null}
              {unsupportedTargeting(rule).length ? <p className={styles.setupWarning}>This saved rule uses unsupported targeting: {unsupportedTargeting(rule).join(", ")}. Recreate it using supported conditions to avoid missing alerts.</p> : null}
              {!TRIGGER_OPTIONS.some((item) => item.value === rule.trigger) ? <p className={styles.setupWarning}>This saved trigger is not evaluated in the current alert flow. Recreate it with a supported alert type above.</p> : null}
              {rule.scope === "custom" ? (
                <div className="rule-target-summary">
                  <span>{rule.match_mode === "any" ? "Any condition" : "All conditions"}</span>
                  {rule.target_skus.length ? <span>SKUs: {listToText(rule.target_skus)}</span> : null}
                  {rule.product_title_contains ? <span>Title contains: {rule.product_title_contains}</span> : null}
                  {rule.categories.length ? <span>Categories: {listToText(rule.categories)}</span> : null}
                  {rule.suppliers.length ? <span>Suppliers: {listToText(rule.suppliers)}</span> : null}
                  {rule.tags.length ? <span>Tags: {listToText(rule.tags)}</span> : null}
                  {rule.collections.length ? <span>Collections: {listToText(rule.collections)}</span> : null}
                  {rule.locations.length ? <span>Locations: {listToText(rule.locations)}</span> : null}
                </div>
              ) : (
                <p className="muted small">Applies storewide</p>
              )}
              {rule.last_fired_at ? (
                <p className="muted small">
                  Last fired {new Date(rule.last_fired_at).toLocaleString()}
                </p>
              ) : (
                <p className="muted small">Never fired</p>
              )}
            </div>
            <div className="rule-card-actions">
              <span className="toggle-row">
                <button
                  type="button"
                  className={`toggle-switch${rule.enabled ? " toggle-switch-on" : ""}`}
                  role="switch"
                  aria-checked={rule.enabled}
                  aria-label={`Enable ${rule.name}`}
                  disabled={!!busy || demo}
                  onClick={() => void mutateRule(rule, "toggle")}
                />
                <span className="toggle-label">{rule.enabled ? "Enabled" : "Disabled"}</span>
              </span>
              <button
                type="button"
                className="button-danger-link"
                disabled={!!busy || demo}
                onClick={() => void mutateRule(rule, "delete")}
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ChannelsPanel({
  channels,
  onChange,
  isChannelAllowed,
  demo,
}: {
  channels: NotificationChannelConfig[];
  onChange: () => void;
  isChannelAllowed: (channel: NotificationChannel) => boolean;
  demo: boolean;
}) {
  return (
    <div className="channels-panel">
      <p className="panel-section-subtitle">
        Save your destination, send a test, and check the inbox or receiving channel. A successful request confirms acceptance by the service, not that an email was read.
      </p>
      <div className="channels-grid">
        {channels.map((c) => (
          <ChannelCard
            key={c.channel}
            channel={c}
            locked={!isChannelAllowed(c.channel)}
            demo={demo}
            onChange={onChange}
          />
        ))}
      </div>
    </div>
  );
}

function ChannelCard({
  channel,
  locked,
  onChange,
  demo,
}: {
  channel: NotificationChannelConfig;
  locked: boolean;
  onChange: () => void;
  demo: boolean;
}) {
  const [target, setTarget] = useState(channel.target);
  const [enabled, setEnabled] = useState(channel.enabled);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"save" | "test" | null>(null);
  const [showTarget, setShowTarget] = useState(false);
  useEffect(() => { setTarget(channel.target); setEnabled(channel.enabled); }, [channel.target, channel.enabled]);
  const dirty = target.trim() !== channel.target || enabled !== channel.enabled;
  const readiness = channelState(channel, !locked);
  const secret = channel.channel === "slack" || channel.channel === "webhook";
  const disabled = locked || demo || !!busy;

  // SMS delivery is not live yet (Twilio + A2P registration pending), so the
  // channel shows as planned instead of taking config that would go nowhere.
  if (channel.channel === "sms") {
    return (
      <div className="channel-card">
        <div className="channel-card-head">
          <h4 className="channel-card-title">SMS</h4>
          <span className="status-badge status-neutral">Planned</span>
        </div>
        <p className="muted small">
          SMS alerts are not available yet. Use email, Slack, or a webhook for current alerts. SMS is planned for Growth and Scale once delivery is available.
        </p>
      </div>
    );
  }

  const placeholder =
    channel.channel === "email"
      ? "alerts@yourshop.com"
      : channel.channel === "slack"
      ? "https://hooks.slack.com/services/..."
      : "https://your-webhook-endpoint.example.com/hook";

  async function handleSave() {
    const changedTarget = target.trim() !== channel.target;
    const problem = enabled || (changedTarget && target.trim()) ? targetError(channel.channel, target) : null;
    if (problem) { setError(problem); return; }
    setBusy("save"); setError(null); setTestResult(null);
    try {
      await updateChannel({
      channel: channel.channel,
      enabled,
      target: target.trim(),
    });
      setTestResult(!changedTarget && channel.verified
        ? enabled ? "Channel enabled. Matching rules can now send here." : "Channel paused. Automatic alerts will not be sent here."
        : "Destination saved. Send a test and check the destination before enabling automatic alerts.");
      onChange();
    } catch (cause) { setError(alertError(cause, "Could not save this destination. Your edits are still here.")); }
    finally { setBusy(null); }
  }

  async function handleTest() {
    const problem = targetError(channel.channel, target);
    if (problem || dirty) { setError(problem ?? "Save changes before sending a test."); return; }
    setBusy("test"); setError(null); setTestResult(null);
    try {
      const result = await sendTestAlert({ channel: channel.channel, target: channel.target });
      const accepted = result.status ? result.status === "accepted" : result.delivered;
      if (!accepted) { setError(result.error || "The test was not confirmed. Check the settings before trying again."); onChange(); return; }
      setTestResult(`Test request accepted. Check ${channel.channel === "email" ? "your inbox and spam folder" : channel.channel === "slack" ? "your Slack channel" : "your receiving workflow"} for the Skubase test notification.${result.persisted_verified === false ? " This test did not verify the saved destination." : ""}`);
      onChange();
    } catch (cause) { setError(alertError(cause, "Could not send the test. Check the destination and try again.")); }
    finally { setBusy(null); }
  }

  return (
    <div className={`channel-card ${styles.channelCard}`}>
      <div className="channel-card-head">
        <h4 className="channel-card-title">{channel.channel.toUpperCase()}</h4>
        <span className={!dirty && readiness.ready ? styles.readyBadge : styles.badge}>{demo ? "Sample workspace" : dirty ? "Unsaved changes" : readiness.label}</span>
      </div>
      <p className="muted small" id={`channel-${channel.channel}-help`}>{channel.channel === "email"
        ? "Use one inbox your team checks. Skubase sends alert emails through its business email service."
        : channel.channel === "slack" ? "Create an incoming webhook for the Slack channel where your team wants alerts, then paste its URL here."
        : "Use a public HTTPS endpoint from your automation tool or internal system."}</p>
      {channel.channel === "slack" ? <a className={styles.guideLink} href="https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks" target="_blank" rel="noopener noreferrer">Open Slack's webhook setup guide ↗</a> : null}
      {channel.channel === "webhook" ? <details className={styles.help}><summary>What the endpoint receives</summary><p>Skubase posts JSON containing <code>subject</code>, <code>body</code>, <code>emitted_at</code>, and <code>source</code>. The endpoint should return a successful HTTP response.</p></details> : null}
      {channel.available === false ? <p className={styles.setupWarning}>{channel.availability_reason || "This delivery service is currently unavailable. You can prepare its destination while service setup is completed."}</p> : null}
      {locked ? <p className={styles.setupWarning}>{channel.channel === "webhook" ? "Growth or Scale" : "Starter or above"} includes this channel. <Link href="/billing">View plans</Link></p> : null}
        <label className="switch-inline">
          <input
            type="checkbox"
            checked={enabled}
            disabled={disabled || (!enabled && (channel.available !== true || !channel.verified || target.trim() !== channel.target))}
            onChange={(e) => setEnabled(e.target.checked)}
          />
          Enable {channel.channel} for automatic alerts
        </label>
      <label className="form-field">
        <span className="form-label">{channel.channel === "email" ? "Recipient email" : `${channel.channel === "slack" ? "Slack incoming" : "Receiving"} webhook URL`}</span>
        <input
          type={channel.channel === "email" ? "email" : secret && !showTarget ? "password" : "url"}
          autoComplete="off"
          spellCheck={false}
          aria-describedby={`channel-${channel.channel}-help`}
          aria-invalid={!!error}
          placeholder={placeholder}
          value={target}
          disabled={disabled}
          onChange={(e) => { setTarget(e.target.value); setEnabled(false); setError(null); setTestResult(null); }}
        />
      </label>
      {secret ? <label className={styles.check}><input type="checkbox" checked={showTarget} onChange={(event) => setShowTarget(event.target.checked)} />Show webhook URL</label> : null}
      {dirty ? <p className="muted small">Unsaved changes. Save before sending a test.</p> : null}
      {target.trim() !== channel.target ? <p className="muted small">A new destination is saved paused. Test it before enabling automatic alerts.</p> : !channel.verified && !enabled ? <p className="muted small">Send a successful test before enabling this channel.</p> : null}
      {channel.verified && !dirty ? <p className="muted small">{channel.verification_label || "A test to the saved destination was accepted by the receiving service."}</p> : null}
      <div className="channel-card-actions">
        <button type="button" className="button-primary" onClick={() => void handleSave()} disabled={disabled || !dirty}>
          {busy === "save" ? "Saving…" : target.trim() === channel.target && enabled !== channel.enabled ? enabled ? "Enable channel" : "Pause channel" : "Save destination"}
        </button>
        <button type="button" className="button-ghost" onClick={() => void handleTest()} disabled={disabled || dirty || channel.available !== true || !!targetError(channel.channel, target)}>
          {busy === "test" ? "Sending test…" : "Send test"}
        </button>
      </div>
      {demo ? <p className="muted small">Sample settings only. No test messages are sent from this workspace.</p> : null}
      {error ? <p className={styles.error} role="alert">{error}</p> : null}
      {testResult ? <p className={styles.message} role="status">{testResult}</p> : null}
    </div>
  );
}

function EventsPanel({ events, onChange, demo }: { events: AlertEvent[]; onChange: () => void; demo: boolean }) {
  if (events.length === 0) {
    return (
      <DataQualityNote title="Alert event history appears after rules match store data">
        <p>
          Alert rules are configured and checked automatically. Recent events will
          appear here after evaluations run against connected inventory, forecast,
          and supplier data. Use preview to inspect current matches without sending.
        </p>
      </DataQualityNote>
    );
  }
  return (
    <div className="events-list">
      {events
        .slice()
        .reverse()
        .map((event) => (
          <div key={event.id} className={`event-row event-sev-${event.severity}`}>
            <div className="event-row-main">
              <div className="event-row-head">
                <span className={`severity-pill severity-${event.severity}`}>
                  {event.severity}
                </span>
                <h4 className="event-row-title">{event.rule_name}</h4>
                <span className="muted small">
                  {new Date(event.fired_at).toLocaleString()}
                </span>
              </div>
              <p className="event-row-body">{event.message}</p>
              <div className="event-row-meta">
                {event.sku_name ? <span>SKU: {event.sku_name}</span> : null}
                {event.channels_sent.length > 0 ? (
                  <span>Accepted by: {event.channels_sent.join(", ")}</span>
                ) : null}
                <span>{eventDeliveryLabel(event)}</span>
                {event.resolved ? <span>Condition resolved</span> : null}
              </div>
              {event.delivery_errors && Object.entries(event.delivery_errors).length ? <ul className={styles.deliveryErrors}>{Object.entries(event.delivery_errors).map(([channel, message]) => <li key={channel}><strong>{channel}:</strong> {message}</li>)}</ul> : null}
              <UncertainRetry event={event} onChange={onChange} demo={demo} />
            </div>
          </div>
        ))}
    </div>
  );
}

function UncertainRetry({ event, onChange, demo }: { event: AlertEvent; onChange: () => void; demo: boolean }) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState<NotificationChannel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  if (event.resolved || !event.uncertain_channels?.length) return null;

  async function retry(channel: NotificationChannel) {
    if (!acknowledged || demo || busy) return;
    setBusy(channel); setError(null); setNotice(null);
    try {
      await retryUncertainAlert(event.id, channel);
      setAcknowledged(false);
      setNotice(`A fresh ${channel} check is queued. A notification is sent only if the rule still matches. Other accepted channels are not repeated.`);
      onChange();
    } catch (cause) { setError(alertError(cause, "The retry could not be queued. Refresh activity and check channel settings.")); }
    finally { setBusy(null); }
  }

  return <div className={styles.retryPanel}>
    <p><strong>Check the destination before retrying.</strong> The service may have received this alert even though Skubase could not confirm the result. Retrying may send a duplicate.</p>
    <label className={styles.check}><input type="checkbox" checked={acknowledged} disabled={!!busy || demo}
      onChange={(change) => setAcknowledged(change.target.checked)} />I checked the destination and understand a retry may send a duplicate.</label>
    <div className="button-row">{event.uncertain_channels.map((channel) => <button key={channel} type="button" className="button button-secondary button-sm"
      disabled={!acknowledged || !!busy || demo} onClick={() => void retry(channel)}>{busy === channel ? "Queueing…" : `Retry ${channel}`}</button>)}</div>
    {error ? <p className={styles.error} role="alert">{error}</p> : null}{notice ? <p className={styles.message} role="status">{notice}</p> : null}
  </div>;
}
