"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { API_BASE_URL } from "@/lib/api-base";
import { useAuth } from "@/components/auth-guard";
import { authenticatedFetch } from "@/lib/shopify-embedded";
import { GatedFeature } from "@/components/gated-feature";
import { readEmailSchedules, emailScheduleError, validScheduleEmail, type EmailSchedule } from "@/lib/email-schedule";
import { ScheduledEmailStatus } from "@/components/scheduled-email-status";

const REPORT_TYPE = "weekly_buy_list";

export function BuyListEmailCard() {
  return <GatedFeature capability="scheduled_reports" title="Weekly buy-list email" description="Schedule your reorder priorities by email on Scale. You can still review the purchase-order plan on this page."><BuyListEmailSetup /></GatedFeature>;
}

function BuyListEmailSetup() {
  const { user } = useAuth();
  const isSyntheticEmail =
    user.email.startsWith("shopify-admin+") || user.email.endsWith(".invalid");
  const [email, setEmail] = useState(isSyntheticEmail ? "" : user.email);
  const [enabled, setEnabled] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [savedEmail, setSavedEmail] = useState("");
  const [savedSchedule, setSavedSchedule] = useState<EmailSchedule | null>(null);

  useEffect(() => {
    if (user.id === 0) return;
    const controller = new AbortController();
    setLoaded(false);
    setLoadError(null);
    void authenticatedFetch(`${API_BASE_URL}/reports/schedules`, { credentials: "include", signal: controller.signal })
      .then(async res => {
        const body = await res.json().catch(() => null);
        if (!res.ok) throw new Error(emailScheduleError(body, "Could not load your email schedule."));
        return readEmailSchedules(body);
      })
      .then(schedules => {
        if (controller.signal.aborted) return;
        const existing = schedules.find((s) => s.report_type === REPORT_TYPE);
        setSavedSchedule(existing ?? null);
        setEnabled(existing?.enabled ?? false);
        if (existing) {
          setSavedEmail(existing.recipient_email);
          if (existing.recipient_email) setEmail(existing.recipient_email);
        }
        setLoaded(true);
      })
      .catch(error => { if (!controller.signal.aborted) { setLoadError(error instanceof Error ? error.message : "Could not load your email schedule."); setLoaded(true); } });
    return () => {
      controller.abort();
    };
  }, [user.id, retry]);

  async function save(nextEnabled: boolean) {
    const recipient = nextEnabled ? email.trim() : savedEmail;
    if (!validScheduleEmail(recipient)) {
      setNotice("Enter the email address that should receive the buy list.");
      return;
    }
    setSaving(true);
    setNotice(null);
    try {
      const res = await authenticatedFetch(`${API_BASE_URL}/reports/schedules`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          report_type: REPORT_TYPE,
          cadence: "weekly",
          channel: "email",
          recipient_email: recipient,
          enabled: nextEnabled,
        }),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        setNotice(emailScheduleError(body, `Could not save (${res.status}).`));
        return;
      }
      const saved = readEmailSchedules({ schedules: [body] })[0];
      if (saved.report_type !== REPORT_TYPE || saved.enabled !== nextEnabled || saved.recipient_email !== recipient) {
        setNotice("The server did not confirm this schedule change. Reload the settings before trying again.");
        return;
      }
      setEnabled(nextEnabled);
      setSavedEmail(recipient);
      setSavedSchedule(saved);
      setNotice(
        nextEnabled
          ? "Schedule saved for Monday (UTC). A buy list is sent when there are reorder items and email delivery is available."
          : "Weekly buy-list schedule paused."
      );
    } catch (error) {
      setNotice(error instanceof Error && error.message ? error.message : "The schedule change could not be confirmed. Reload these settings before trying again.");
    } finally {
      setSaving(false);
    }
  }

  if (user.id === 0) {
    return (
      <div className="chart-card">
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Weekly digest</p>
            <h2 className="section-title section-title-small">Monday buy list email</h2>
          </div>
          <span className="status-badge status-failed">Demo</span>
        </div>
        <p className="section-copy">
          Every Monday: your top reorders ranked by stockout risk, with the cash
          required by vendor. Sign in with your store to turn this on.
        </p>
      </div>
    );
  }

  if (!loaded) return <div className="chart-card"><p className="section-copy" role="status">Loading weekly email settings…</p></div>;
  if (loadError) return <div className="chart-card"><h2 className="section-title section-title-small">Weekly buy-list email</h2><p className="section-copy" role="alert">{loadError}</p><button type="button" className="button button-ghost" onClick={() => setRetry(value => value + 1)}>Try again</button></div>;

  return (
    <div className="chart-card">
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">Weekly digest</p>
          <h2 className="section-title section-title-small">Monday buy list email</h2>
        </div>
        <span className={`status-badge ${enabled ? "status-succeeded" : "status-failed"}`}>
          {enabled ? "Scheduled" : "Not scheduled"}
        </span>
      </div>
      <p className="section-copy">
        On Monday (UTC), email your top reorders and purchasing costs by supplier.
        Weeks with no reorder items are skipped. This schedule is separate from threshold-based inventory alerts.
      </p>
      <p className="section-copy"><Link href="/alerts">Set up stock alerts</Link> or <Link href="/reports">schedule other report emails</Link>.</p>
      {savedSchedule ? <ScheduledEmailStatus delivery={savedSchedule} /> : null}
      <div className="button-row" style={{ marginTop: "12px", flexWrap: "wrap", gap: "8px" }}>
        <label htmlFor="buy-list-recipient">Recipient email</label>
        <input id="buy-list-recipient"
          type="email"
          className="input-control"
          style={{ minWidth: 0, width: "min(100%, 300px)" }}
          placeholder="you@yourstore.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          disabled={saving}
        />
        <button
          type="button"
          className={`button ${enabled ? "button-ghost" : "button-primary"}`}
          onClick={() => void save(true)}
          disabled={saving}
        >
          {saving ? "Saving..." : enabled ? "Save recipient" : "Schedule weekly email"}
        </button>
        {enabled ? <button type="button" className="button button-ghost" disabled={saving} onClick={() => void save(false)}>Pause schedule</button> : null}
      </div>
      {notice ? (
        <p className="section-copy" role="status" style={{ marginTop: "8px" }}>{notice}</p>
      ) : null}
    </div>
  );
}
