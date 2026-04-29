"use client";

import { useEffect, useState } from "react";

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

const TRIGGER_OPTIONS: { value: AlertTrigger; label: string; help: string }[] = [
  { value: "stockout_risk", label: "Stockout risk", help: "Fires when a SKU has fewer days of cover than the threshold" },
  { value: "dead_stock", label: "Dead stock capital", help: "Fires when a dead SKU ties up more capital than the threshold (USD)" },
  { value: "overstock", label: "Overstock days of cover", help: "Fires when days of cover exceed the threshold" },
  { value: "forecast_miss", label: "High stockout probability", help: "Fires when forecast stockout probability exceeds the threshold (percent)" },
  { value: "supplier_slip", label: "Supplier on-time slip", help: "Fires when a vendor's on-time rate falls below the threshold (percent)" },
];

const SEVERITY_OPTIONS: AlertSeverity[] = ["info", "warning", "critical"];
const CHANNEL_OPTIONS: NotificationChannel[] = ["email", "sms", "slack", "webhook"];

export default function AlertsPage() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [channels, setChannels] = useState<NotificationChannelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"rules" | "channels" | "history">("rules");

  useEffect(() => {
    refresh();
  }, []);

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

  return (
    <div className="alerts-page">
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
          onClick={async () => {
            await evaluateAlertsNow(true);
            await refresh();
          }}
        >
          Run evaluation now
        </button>
      </div>

      {loading ? <p className="page-loading">Loading…</p> : null}
      {error ? <p className="page-error-copy">{error}</p> : null}

      {tab === "rules" ? <RulesPanel rules={rules} onChange={refresh} /> : null}
      {tab === "channels" ? (
        <ChannelsPanel channels={channels} onChange={refresh} />
      ) : null}
      {tab === "history" ? <EventsPanel events={events} /> : null}
    </div>
  );
}

function RulesPanel({ rules, onChange }: { rules: AlertRule[]; onChange: () => void }) {
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
          Build a custom rule — mix triggers, channels, and thresholds to fit how your team operates.
        </p>
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
          </label>
          <div className="form-field">
            <span className="form-label">Channels</span>
            <div className="channel-chips">
              {CHANNEL_OPTIONS.map((c) => {
                const active = newRule.channels.includes(c);
                return (
                  <button
                    key={c}
                    type="button"
                    className={`channel-chip${active ? " channel-chip-active" : ""}`}
                    onClick={() =>
                      setNewRule({
                        ...newRule,
                        channels: active
                          ? newRule.channels.filter((x) => x !== c)
                          : [...newRule.channels, c],
                      })
                    }
                  >
                    {c}
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
                {" · threshold "}
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
}: {
  channels: NotificationChannelConfig[];
  onChange: () => void;
}) {
  return (
    <div className="channels-panel">
      <p className="panel-section-subtitle">
        Configure how alerts reach you. Email, SMS, Slack, and generic webhooks are all supported out of the box.
      </p>
      <div className="channels-grid">
        {channels.map((c) => (
          <ChannelCard key={c.channel} channel={c} onChange={onChange} />
        ))}
      </div>
    </div>
  );
}

function ChannelCard({
  channel,
  onChange,
}: {
  channel: NotificationChannelConfig;
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
          onChange={(e) => setTarget(e.target.value)}
        />
      </label>
      <div className="channel-card-actions">
        <button type="button" className="button-primary" onClick={handleSave}>
          Save
        </button>
        <button type="button" className="button-ghost" onClick={handleTest}>
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
      <div className="empty-state">
        <p className="empty-state-title">No alerts have fired yet</p>
        <p className="empty-state-copy">
          Run an evaluation above — any rule that matches your current state will produce a dry-run event here.
        </p>
      </div>
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
                ) : (
                  <span>Dry run</span>
                )}
              </div>
            </div>
          </div>
        ))}
    </div>
  );
}
