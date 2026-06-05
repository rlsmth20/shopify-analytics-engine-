"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { DataQualityNote } from "@/components/data-quality-note";
import { useAuth } from "@/components/auth-guard";
import {
  createAlertRule,
  deleteAlertRule,
  evaluateAlertsNow,
  fetchAlertEvents,
  fetchAlertRules,
  fetchChannels,
  sendTestAlert,
  toggleAlertRule,
  updateChannel,
  type AlertEvent,
  type AlertRule,
  type AlertSeverity,
  type AlertTrigger,
  type NotificationChannel,
  type NotificationChannelConfig,
} from "@/lib/api-v2";
import { planToTier, tierAllows, type PlanTierKey } from "@/lib/plans";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const TRIGGER_OPTIONS: { value: AlertTrigger; label: string; help: string }[] = [
  { value: "stockout_risk", label: "Stockout risk", help: "Fires when a SKU has fewer days of cover than the threshold" },
  { value: "dead_stock", label: "Dead stock capital", help: "Fires when a dead SKU ties up more capital than the threshold (USD)" },
  { value: "overstock", label: "Overstock days of cover", help: "Fires when days of cover exceed the threshold" },
  { value: "forecast_miss", label: "High stockout probability", help: "Fires when forecast stockout probability exceeds the threshold (percent)" },
  { value: "supplier_slip", label: "Supplier on-time slip", help: "Fires when a vendor's on-time rate falls below the threshold (percent)" },
];

const SEVERITY_OPTIONS: AlertSeverity[] = ["info", "warning", "critical"];
const CHANNEL_OPTIONS: NotificationChannel[] = ["email", "sms", "slack", "webhook"];
const CHANNEL_MIN_TIER: Record<NotificationChannel, PlanTierKey> = {
  email: "starter",
  slack: "starter",
  sms: "growth",
  webhook: "growth",
};

const TARGETING_OPTIONS = [
  { label: "Storewide", status: "Available", detail: "Rules evaluate connected inventory signals across the store." },
  { label: "Specific products/SKUs", status: "Planned", detail: "Product-level targeting is not saved on alert rules yet." },
  { label: "Product categories", status: "Planned", detail: "Category filters are planned after rule targeting is added." },
  { label: "Collections", status: "Planned", detail: "Collection targeting requires Shopify collection mappings." },
  { label: "Tags", status: "Planned", detail: "Tag targeting requires synced Shopify product tags." },
  { label: "Supplier/vendor", status: "Partial", detail: "Supplier slip alerts use supplier scorecards when supplier data exists." },
  { label: "Locations", status: "Requires data", detail: "Location-specific alerts require location-level inventory and rule targeting support." },
];

export default function AlertsPage() {
  const { user } = useAuth();
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [channels, setChannels] = useState<NotificationChannelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [tab, setTab] = useState<"rules" | "channels" | "history">("rules");
  const [plan, setPlan] = useState<string | null>(null);

  const paidTier = planToTier(plan) ?? "starter";
  const unlockAll = user.id === 0 || user.in_trial || user.is_admin;
  const isChannelAllowed = (channel: NotificationChannel) =>
    unlockAll || tierAllows(paidTier, CHANNEL_MIN_TIER[channel]);

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (user.id === 0) return;

    void fetch(`${API_BASE}/billing/me`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { plan?: string } | null) => setPlan(data?.plan ?? null))
      .catch(() => setPlan(null));
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
        setNotice("Evaluation complete: no rules matched the current inventory state.");
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
          } found; ${deliveredCount} delivered through enabled channels.`
        );
      }
      await refresh();
      setTab("history");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setEvaluating(false);
    }
  }

  return (
    <div className="alerts-page">
      <div className="content-grid content-grid-2-1 alert-context-grid">
        <DataQualityNote title="Alert rules are storewide today">
          <p>
            Skubase evaluates enabled rules against connected inventory, forecast,
            and supplier signals for the whole store. Advanced product, tag,
            collection, and location targeting is planned; unsupported targeting
            is shown below as a requirement, not an active filter.
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

        <DataQualityNote title="Location-specific alerts require location-level inventory">
          <p>
            Your current alert rules use storewide inventory risk. When
            location-level Shopify inventory is available, Skubase can show
            location-aware planning surfaces; alert rule targeting is not active
            yet.
          </p>
          <div className="button-row">
            <Link href="/transfers?demo=1" className="button button-secondary button-sm">
              View transfer requirements
            </Link>
            <button type="button" className="button button-primary button-sm" disabled>
              Continue with storewide alerts
            </button>
          </div>
        </DataQualityNote>
      </div>

      <div className="tab-bar">
        {(["rules", "channels", "history"] as const).map((t) => (
          <button
            key={t}
            type="button"
            className={`tab-button${tab === t ? " tab-button-active" : ""}`}
            onClick={() => setTab(t)}
          >
            {t === "rules" ? "Rules" : t === "channels" ? "Channels" : "Recent events"}
          </button>
        ))}
        <button
          type="button"
          className="button-ghost tab-bar-trailing"
          disabled={evaluating}
          onClick={() => void runEvaluation(true)}
        >
          {evaluating ? "Evaluating..." : "Preview evaluation"}
        </button>
        <span className="auto-alert-pill">Auto-send on</span>
      </div>

      {loading ? <p className="page-loading">Loading...</p> : null}
      {error ? <p className="page-error-copy">{error}</p> : null}
      {notice ? <p className="muted small">{notice}</p> : null}

      {tab === "rules" ? (
        <RulesPanel
          rules={rules}
          onChange={refresh}
          isChannelAllowed={isChannelAllowed}
        />
      ) : null}
      {tab === "channels" ? (
        <ChannelsPanel
          channels={channels}
          onChange={refresh}
          isChannelAllowed={isChannelAllowed}
        />
      ) : null}
      {tab === "history" ? <EventsPanel events={events} /> : null}
    </div>
  );
}

function RulesPanel({
  rules,
  onChange,
  isChannelAllowed,
}: {
  rules: AlertRule[];
  onChange: () => void;
  isChannelAllowed: (channel: NotificationChannel) => boolean;
}) {
  const [newRule, setNewRule] = useState({
    name: "",
    trigger: "stockout_risk" as AlertTrigger,
    severity: "critical" as AlertSeverity,
    channels: ["email"] as NotificationChannel[],
    threshold: 3,
    enabled: true,
  });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newRule.name.trim()) return;
    await createAlertRule(newRule);
    setNewRule({ ...newRule, name: "" });
    onChange();
  }

  return (
    <div className="alerts-rules">
      <form className="alert-rule-form" onSubmit={handleCreate}>
        <h3 className="panel-section-title">Add a rule</h3>
        <p className="panel-section-subtitle">
          Enabled rules are checked automatically. Use preview to inspect matches without sending notifications.
        </p>
        <div className="alert-targeting-panel">
          <div>
            <p className="form-label">Choose what this rule applies to</p>
            <p className="form-hint">
              Today, alert rules are storewide and use the trigger threshold below.
              Advanced product targeting is planned.
            </p>
          </div>
          <div className="alert-targeting-options">
            {TARGETING_OPTIONS.map((option) => (
              <div
                key={option.label}
                className={`alert-targeting-option${option.status === "Available" ? " alert-targeting-option-active" : ""}`}
                aria-disabled={option.status !== "Available"}
              >
                <span>{option.label}</span>
                <strong>{option.status}</strong>
                <small>{option.detail}</small>
              </div>
            ))}
          </div>
          <p className="form-hint">
            Condition groups such as "match all conditions" or "match any
            condition" are not active yet. Skubase can still monitor stockout,
            dead-stock, overstock, forecast, and supplier signals from connected
            product and order data.
          </p>
        </div>
        <div className="form-grid">
          <label className="form-field">
            <span className="form-label">Rule name</span>
            <input
              type="text"
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
                setNewRule({ ...newRule, trigger: e.target.value as AlertTrigger })
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
            <span className="form-label">Threshold</span>
            <input
              type="number"
              step="any"
              value={newRule.threshold}
              onChange={(e) =>
                setNewRule({ ...newRule, threshold: Number(e.target.value) })
              }
            />
            <span className="form-hint">
              This is the manual threshold for the selected trigger. Product-level
              alert-below, target stock, restock-to, and safety stock thresholds
              are planned; smart recommendations use sales velocity, lead time,
              and target coverage today.
            </span>
          </label>
          <div className="form-field">
            <span className="form-label">Channels</span>
            <div className="channel-chips">
              {CHANNEL_OPTIONS.map((c) => {
                const active = newRule.channels.includes(c);
                const allowed = isChannelAllowed(c);
                return (
                  <button
                    key={c}
                    type="button"
                    className={`channel-chip${active ? " channel-chip-active" : ""}`}
                    disabled={!allowed}
                    title={allowed ? undefined : `${c} alerts are included on Growth and Scale.`}
                    onClick={() =>
                      setNewRule({
                        ...newRule,
                        channels: active
                          ? newRule.channels.filter((x) => x !== c)
                          : [...newRule.channels, c],
                      })
                    }
                  >
                    {allowed ? c : `${c} (Growth)`}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
        <button type="submit" className="button-primary">
          Create rule
        </button>
      </form>

      <div className="rules-list">
        <h3 className="panel-section-title">Active rules</h3>
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
                {" - threshold "}
                {rule.threshold}
              </p>
              <div className="rule-card-channels">
                {rule.channels.map((c) => (
                  <span key={c} className="channel-pill">
                    {c}
                  </span>
                ))}
              </div>
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
                  aria-label={rule.enabled ? "Disable rule" : "Enable rule"}
                  onClick={async () => {
                    await toggleAlertRule(rule.id, !rule.enabled);
                    onChange();
                  }}
                />
                <span className="toggle-label">{rule.enabled ? "Enabled" : "Disabled"}</span>
              </span>
              <button
                type="button"
                className="button-danger-link"
                onClick={async () => {
                  await deleteAlertRule(rule.id);
                  onChange();
                }}
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
}: {
  channels: NotificationChannelConfig[];
  onChange: () => void;
  isChannelAllowed: (channel: NotificationChannel) => boolean;
}) {
  return (
    <div className="channels-panel">
      <p className="panel-section-subtitle">
        Configure where automatic alerts are delivered. Only enabled channels with real targets receive notifications.
      </p>
      <div className="channels-grid">
        {channels.map((c) => (
          <ChannelCard
            key={c.channel}
            channel={c}
            locked={!isChannelAllowed(c.channel)}
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
}: {
  channel: NotificationChannelConfig;
  locked: boolean;
  onChange: () => void;
}) {
  const [target, setTarget] = useState(channel.target);
  const [enabled, setEnabled] = useState(channel.enabled);
  const [testResult, setTestResult] = useState<string | null>(null);

  const placeholder =
    channel.channel === "email"
      ? "alerts@yourshop.com"
      : channel.channel === "sms"
      ? "+15551234567"
      : channel.channel === "slack"
      ? "https://hooks.slack.com/services/..."
      : "https://your-webhook-endpoint.example.com/hook";

  async function handleSave() {
    await updateChannel({
      channel: channel.channel,
      enabled,
      target,
    });
    onChange();
  }

  async function handleTest() {
    if (!target) {
      setTestResult("Enter a target first.");
      return;
    }
    const result = await sendTestAlert({ channel: channel.channel, target });
    setTestResult(
      result.delivered
        ? "Test notification sent."
        : `Failed: ${result.error || "unknown error"}`
    );
  }

  return (
    <div className="channel-card">
      <div className="channel-card-head">
        <h4 className="channel-card-title">{channel.channel.toUpperCase()}</h4>
        <label className="switch-inline">
          <input
            type="checkbox"
            checked={enabled}
            disabled={locked}
            onChange={(e) => setEnabled(e.target.checked)}
          />
          {enabled ? "On" : "Off"}
        </label>
      </div>
      <label className="form-field">
        <span className="form-label">Target</span>
        <input
          type="text"
          placeholder={placeholder}
          value={target}
          disabled={locked}
          onChange={(e) => setTarget(e.target.value)}
        />
      </label>
      <div className="channel-card-actions">
        <button type="button" className="button-primary" onClick={handleSave} disabled={locked}>
          {locked ? "Growth plan" : "Save"}
        </button>
        <button type="button" className="button-ghost" onClick={handleTest} disabled={locked}>
          Send test
        </button>
      </div>
      {testResult ? <p className="muted small">{testResult}</p> : null}
    </div>
  );
}

function EventsPanel({ events }: { events: AlertEvent[] }) {
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
                  <span>Delivered via: {event.channels_sent.join(", ")}</span>
                ) : event.delivered ? (
                  <span>Preview only</span>
                ) : (
                  <span>No enabled channel delivered this alert</span>
                )}
              </div>
            </div>
          </div>
        ))}
    </div>
  );
}
