"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { trackEvent } from "@/lib/analytics";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const ISSUE_OPTIONS = [
  "Stockouts",
  "Overstock / dead stock",
  "Reorder planning",
  "Supplier lead times",
  "Bundles / kits",
  "Not sure",
] as const;

const SKU_COUNT_OPTIONS = ["50-250", "251-1,000", "1,001-5,000", "5,001+", "Not sure"];

type FormState = {
  first_name: string;
  email: string;
  company_name: string;
  store_url: string;
  approximate_sku_count: string;
  biggest_inventory_issue: string;
};

const INITIAL_STATE: FormState = {
  first_name: "",
  email: "",
  company_name: "",
  store_url: "",
  approximate_sku_count: "",
  biggest_inventory_issue: "",
};

export function InventoryRiskSnapshotForm({
  className = "",
}: {
  className?: string;
}) {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(INITIAL_STATE);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [started, setStarted] = useState(false);

  const utmParams = useMemo(() => {
    if (typeof window === "undefined") return {};
    const params = new URLSearchParams(window.location.search);
    return {
      utm_source: params.get("utm_source") || undefined,
      utm_medium: params.get("utm_medium") || undefined,
      utm_campaign: params.get("utm_campaign") || undefined,
      utm_content: params.get("utm_content") || undefined,
      utm_term: params.get("utm_term") || undefined,
    };
  }, []);

  useEffect(() => {
    trackEvent("inventory_snapshot_page_view");
  }, []);

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    if (!started) {
      setStarted(true);
      trackEvent("inventory_snapshot_form_start");
    }
    setForm((current) => ({ ...current, [key]: value }));
  }

  function validate(): string | null {
    if (!form.first_name.trim()) return "Enter your first name.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
      return "Enter a valid work email.";
    }
    if (!form.company_name.trim()) return "Enter your company name.";
    if (!isPlausibleStoreUrl(form.store_url)) return "Enter a valid Shopify store URL.";
    if (!form.approximate_sku_count) return "Choose an approximate SKU count.";
    if (!form.biggest_inventory_issue) return "Choose your biggest inventory issue.";
    return null;
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch(`${API_BASE}/inventory-risk-snapshot/leads`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          source: "inventory_risk_snapshot",
          ...utmParams,
        }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(body?.detail || `Request failed (${response.status}).`);
      }
      trackEvent("inventory_snapshot_form_submit", {
        biggest_inventory_issue: form.biggest_inventory_issue,
        approximate_sku_count: form.approximate_sku_count,
      });
      router.push("/inventory-risk-snapshot/thanks");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form id="snapshot-form" className={`snapshot-form ${className}`} onSubmit={handleSubmit}>
      <div>
        <p className="snapshot-form-eyebrow">Free diagnostic</p>
        <h2 className="snapshot-form-title">Get your inventory risk snapshot</h2>
        <p className="snapshot-form-copy">
          Send the basics. We will review the store and return a short action snapshot.
        </p>
      </div>

      <div className="snapshot-form-grid">
        <label className="snapshot-field">
          <span>First name</span>
          <input
            className="input-control"
            value={form.first_name}
            onChange={(event) => updateField("first_name", event.target.value)}
            autoComplete="given-name"
            required
          />
        </label>
        <label className="snapshot-field">
          <span>Work email</span>
          <input
            type="email"
            className="input-control"
            value={form.email}
            onChange={(event) => updateField("email", event.target.value)}
            autoComplete="email"
            required
          />
        </label>
        <label className="snapshot-field">
          <span>Company name</span>
          <input
            className="input-control"
            value={form.company_name}
            onChange={(event) => updateField("company_name", event.target.value)}
            autoComplete="organization"
            required
          />
        </label>
        <label className="snapshot-field">
          <span>Shopify store URL</span>
          <input
            className="input-control"
            value={form.store_url}
            onChange={(event) => updateField("store_url", event.target.value)}
            placeholder="yourstore.myshopify.com"
            required
          />
        </label>
        <label className="snapshot-field">
          <span>Approximate SKU count</span>
          <select
            className="input-control"
            value={form.approximate_sku_count}
            onChange={(event) => updateField("approximate_sku_count", event.target.value)}
            required
          >
            <option value="">Select range</option>
            {SKU_COUNT_OPTIONS.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <fieldset className="snapshot-field snapshot-issue-field">
          <legend>Biggest inventory issue</legend>
          <div className="snapshot-issue-options">
            {ISSUE_OPTIONS.map((option) => (
              <label key={option} className="snapshot-radio">
                <input
                  type="radio"
                  name="biggest_inventory_issue"
                  value={option}
                  checked={form.biggest_inventory_issue === option}
                  onChange={(event) => updateField("biggest_inventory_issue", event.target.value)}
                  required
                />
                <span>{option}</span>
              </label>
            ))}
          </div>
        </fieldset>
      </div>

      {error ? <p className="snapshot-form-error" role="alert">{error}</p> : null}
      <button type="submit" className="button button-primary button-lg" disabled={submitting}>
        {submitting ? "Submitting..." : "Get my free snapshot"}
      </button>
      <p className="snapshot-form-footnote">No credit card. No sales deck required.</p>
    </form>
  );
}

function isPlausibleStoreUrl(value: string): boolean {
  const trimmed = value.trim().toLowerCase();
  if (!trimmed || trimmed.includes(" ") || !trimmed.includes(".")) return false;
  if (["example.com", "test.com", "localhost"].includes(trimmed)) return false;
  try {
    const parsed = new URL(trimmed.includes("://") ? trimmed : `https://${trimmed}`);
    return Boolean(parsed.hostname && parsed.hostname.includes("."));
  } catch {
    return false;
  }
}
