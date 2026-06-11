"use client";

import { useEffect, useState } from "react";

import { API_BASE_URL } from "@/lib/api-base";
import { useAuth } from "@/components/auth-guard";
import { authenticatedFetch } from "@/lib/shopify-embedded";

type ReportSchedule = {
  report_type: string;
  recipient_email: string;
  enabled: boolean;
};

const REPORT_TYPE = "weekly_buy_list";

export function BuyListEmailCard() {
  const { user } = useAuth();
  const isSyntheticEmail =
    user.email.startsWith("shopify-admin+") || user.email.endsWith(".invalid");
  const [email, setEmail] = useState(isSyntheticEmail ? "" : user.email);
  const [enabled, setEnabled] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (user.id === 0) return;
    let cancelled = false;
    void authenticatedFetch(`${API_BASE_URL}/reports/schedules`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: { schedules?: ReportSchedule[] } | null) => {
        if (cancelled) return;
        const existing = data?.schedules?.find((s) => s.report_type === REPORT_TYPE);
        if (existing) {
          setEnabled(existing.enabled);
          if (existing.recipient_email) setEmail(existing.recipient_email);
        }
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user.id]);

  async function save(nextEnabled: boolean) {
    if (nextEnabled && (!email.trim() || !email.includes("@"))) {
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
          recipient_email: email.trim(),
          enabled: nextEnabled,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setNotice(body?.detail || `Could not save (${res.status}).`);
        return;
      }
      setEnabled(nextEnabled);
      setNotice(
        nextEnabled
          ? "On. Your buy list arrives every Monday morning (UTC)."
          : "Off. You will not receive the weekly buy list."
      );
    } catch {
      setNotice("Network error - try again in a moment.");
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

  if (!loaded) return null;

  return (
    <div className="chart-card">
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">Weekly digest</p>
          <h2 className="section-title section-title-small">Monday buy list email</h2>
        </div>
        <span className={`status-badge ${enabled ? "status-succeeded" : "status-failed"}`}>
          {enabled ? "On" : "Off"}
        </span>
      </div>
      <p className="section-copy">
        Every Monday: your top reorders ranked by stockout risk, with the cash
        required by vendor. The same math as this page, in your inbox.
      </p>
      <div className="button-row" style={{ marginTop: "12px", flexWrap: "wrap", gap: "8px" }}>
        <input
          type="email"
          className="input-control"
          style={{ minWidth: "240px" }}
          placeholder="you@yourstore.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          disabled={saving}
        />
        <button
          type="button"
          className={`button ${enabled ? "button-ghost" : "button-primary"}`}
          onClick={() => void save(!enabled)}
          disabled={saving}
        >
          {saving ? "Saving..." : enabled ? "Turn off" : "Turn on"}
        </button>
      </div>
      {notice ? (
        <p className="section-copy" style={{ marginTop: "8px" }}>{notice}</p>
      ) : null}
    </div>
  );
}
