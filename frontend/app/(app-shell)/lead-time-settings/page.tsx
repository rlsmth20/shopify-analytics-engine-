"use client";

import { useEffect, useState, type FormEvent } from "react";

import { EmptyState } from "@/components/empty-state";
import { SectionCard } from "@/components/section-card";
import {
  fetchCategoryLeadTimes,
  fetchShopSettings,
  fetchVendorLeadTimes,
  saveCategoryLeadTimes,
  saveShopSettings,
  saveVendorLeadTimes,
  type CategoryLeadTimeEntry,
  type ShopSettingsResponse,
  type VendorLeadTimeEntry
} from "@/lib/api";
import {
  formatCategoryLeadTimes,
  formatVendorLeadTimes,
  parseCategoryLeadTimes,
  parseVendorLeadTimes
} from "@/lib/app-helpers";
import { useStoredShopDomain } from "@/lib/use-stored-shop-domain";

export default function LeadTimeSettingsPage() {
  const { shopifyDomain, setShopifyDomain, hasHydrated } = useStoredShopDomain();
  const [defaultLeadTimeDays, setDefaultLeadTimeDays] = useState("14");
  const [safetyBufferDays, setSafetyBufferDays] = useState("7");
  const [allowMockFallback, setAllowMockFallback] = useState(true);
  const [vendorLeadTimesText, setVendorLeadTimesText] = useState("");
  const [categoryLeadTimesText, setCategoryLeadTimesText] = useState("");
  const [settingsPersisted, setSettingsPersisted] = useState(false);
  const [isLoadingSettings, setIsLoadingSettings] = useState(false);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [settingsNotice, setSettingsNotice] = useState<string | null>(null);

  async function loadSettings(domain: string, options?: { requireDomain?: boolean }) {
    const targetDomain = domain.trim() || "current-shop";
    if (!targetDomain) {
      if (options?.requireDomain) {
        setSettingsError("Enter a Shopify domain first.");
      }
      return;
    }

    setIsLoadingSettings(true);
    setSettingsError(null);
    setSettingsNotice(null);

    try {
      const [settings, vendorLeadTimes, categoryLeadTimes] = await Promise.all([
        fetchShopSettings(targetDomain),
        fetchVendorLeadTimes(targetDomain),
        fetchCategoryLeadTimes(targetDomain)
      ]);
      applyShopSettings(settings);
      setShopifyDomain(settings.shopify_domain);
      setVendorLeadTimesText(formatVendorLeadTimes(vendorLeadTimes.items));
      setCategoryLeadTimesText(formatCategoryLeadTimes(categoryLeadTimes.items));
      setSettingsNotice(
        settings.is_persisted
          ? "Loaded persisted shop settings and lead-time overrides."
          : "Loaded default settings and any saved lead-time overrides for this shop."
      );
    } catch (error) {
      setSettingsError(
        error instanceof Error
          ? error.message
          : "The shop settings could not be loaded."
      );
    } finally {
      setIsLoadingSettings(false);
    }
  }

  async function handleLoadSettings() {
    await loadSettings(shopifyDomain, { requireDomain: true });
  }

  async function handleSaveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const targetDomain = shopifyDomain.trim() || "current-shop";

    const nextDefaultLeadTimeDays = Number.parseInt(defaultLeadTimeDays, 10);
    const nextSafetyBufferDays = Number.parseInt(safetyBufferDays, 10);
    let vendorLeadTimes: VendorLeadTimeEntry[] = [];
    let categoryLeadTimes: CategoryLeadTimeEntry[] = [];

    if (
      Number.isNaN(nextDefaultLeadTimeDays) ||
      Number.isNaN(nextSafetyBufferDays)
    ) {
      setSettingsError("Lead time and safety buffer must be valid numbers.");
      return;
    }

    try {
      vendorLeadTimes = parseVendorLeadTimes(vendorLeadTimesText);
      categoryLeadTimes = parseCategoryLeadTimes(categoryLeadTimesText);
    } catch (error) {
      setSettingsError(
        error instanceof Error
          ? error.message
          : "Lead-time overrides could not be parsed."
      );
      return;
    }

    setIsSavingSettings(true);
    setSettingsError(null);
    setSettingsNotice(null);

    try {
      const [settings, savedVendorLeadTimes, savedCategoryLeadTimes] =
        await Promise.all([
          saveShopSettings({
            shopify_domain: targetDomain,
            global_default_lead_time_days: nextDefaultLeadTimeDays,
            global_safety_buffer_days: nextSafetyBufferDays,
            allow_mock_fallback: allowMockFallback
          }),
          saveVendorLeadTimes({
            shopify_domain: targetDomain,
            items: vendorLeadTimes
          }),
          saveCategoryLeadTimes({
            shopify_domain: targetDomain,
            items: categoryLeadTimes
          })
        ]);
      applyShopSettings(settings);
      setShopifyDomain(settings.shopify_domain);
      setVendorLeadTimesText(formatVendorLeadTimes(savedVendorLeadTimes.items));
      setCategoryLeadTimesText(
        formatCategoryLeadTimes(savedCategoryLeadTimes.items)
      );
      setSettingsNotice("Shop settings and lead-time overrides saved.");
    } catch (error) {
      setSettingsError(
        error instanceof Error
          ? error.message
          : "The shop settings could not be saved."
      );
    } finally {
      setIsSavingSettings(false);
    }
  }

  function applyShopSettings(settings: ShopSettingsResponse) {
    setDefaultLeadTimeDays(String(settings.global_default_lead_time_days));
    setSafetyBufferDays(String(settings.global_safety_buffer_days));
    setAllowMockFallback(settings.allow_mock_fallback);
    setSettingsPersisted(settings.is_persisted);
  }

  useEffect(() => {
    if (!hasHydrated) {
      return;
    }

    void loadSettings(shopifyDomain.trim() || "current-shop");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasHydrated]);

  return (
    <div className="page-stack">
      <SectionCard>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Shop Scope</p>
            <h2 className="section-title">Shop configuration target</h2>
          </div>
          <p className="section-copy">
            Settings are scoped to one Shopify domain and feed the live action engine.
          </p>
        </div>

        <div className="settings-scope-row">
          <label className="field-label field-label-grow">
            <span>Shopify domain</span>
            <input
              className="input-control"
              type="text"
              placeholder="store-name.myshopify.com"
              value={shopifyDomain}
              onChange={(event) => setShopifyDomain(event.target.value)}
            />
          </label>

          <button
            type="button"
            className="button button-secondary"
            disabled={isLoadingSettings}
            onClick={() => void handleLoadSettings()}
          >
            {isLoadingSettings ? "Loading..." : "Load settings"}
          </button>
        </div>
      </SectionCard>

      <form className="page-stack" onSubmit={handleSaveSettings}>
        <div className="content-grid content-grid-2-1">
          <SectionCard>
            <div className="section-heading">
              <div>
                <p className="section-eyebrow">Global Settings</p>
                <h2 className="section-title section-title-small">Defaults and fallback</h2>
              </div>
              <span className="status-badge status-neutral">
                {settingsPersisted ? "Persisted" : "Default"}
              </span>
            </div>

            <div className="form-grid">
              <label className="field-label">
                <span>Default lead time days</span>
                <input
                  className="input-control"
                  type="number"
                  min={1}
                  value={defaultLeadTimeDays}
                  onChange={(event) => setDefaultLeadTimeDays(event.target.value)}
                />
              </label>

              <label className="field-label">
                <span>Safety buffer days</span>
                <input
                  className="input-control"
                  type="number"
                  min={0}
                  value={safetyBufferDays}
                  onChange={(event) => setSafetyBufferDays(event.target.value)}
                />
              </label>
            </div>

            <label className="toggle-row">
              <div>
                <span className="toggle-title">Allow mock fallback</span>
                <p className="toggle-copy">
                  If disabled, `/actions` returns an error when the DB does not
                  have usable live data.
                </p>
              </div>
              <input
                type="checkbox"
                checked={allowMockFallback}
                onChange={(event) => setAllowMockFallback(event.target.checked)}
              />
            </label>
          </SectionCard>

          <SectionCard>
            <div className="section-heading">
              <div>
                <p className="section-eyebrow">Resolution Order</p>
                <h2 className="section-title section-title-small">How lead times resolve</h2>
              </div>
            </div>
            <div className="step-list">
              <div className="step-item">
                <strong>1. SKU override</strong>
                <p>Uses the SKU-specific lead time when it exists.</p>
              </div>
              <div className="step-item">
                <strong>2. Vendor override</strong>
                <p>Uses the shop-scoped vendor lead time table.</p>
              </div>
              <div className="step-item">
                <strong>3. Category override</strong>
                <p>Uses the shop-scoped category lead time table.</p>
              </div>
              <div className="step-item">
                <strong>4. Global default</strong>
                <p>Falls back to the shop default, then file config if needed.</p>
              </div>
            </div>
          </SectionCard>
        </div>

        <div className="content-grid content-grid-2-2">
          <SectionCard>
            <div className="section-heading">
              <div>
                <p className="section-eyebrow">Vendor Overrides</p>
                <h2 className="section-title section-title-small">Vendor lead times</h2>
              </div>
            </div>
            <label className="field-label">
              <span>One vendor per line</span>
              <textarea
                className="input-control textarea-control"
                value={vendorLeadTimesText}
                onChange={(event) => setVendorLeadTimesText(event.target.value)}
                placeholder={"Northstar Apparel | 16\nSummit Sportswear | 19"}
              />
            </label>
            <p className="section-copy">Format: vendor name | lead time days</p>
          </SectionCard>

          <SectionCard>
            <div className="section-heading">
              <div>
                <p className="section-eyebrow">Category Overrides</p>
                <h2 className="section-title section-title-small">Category lead times</h2>
              </div>
            </div>
            <label className="field-label">
              <span>One category per line</span>
              <textarea
                className="input-control textarea-control"
                value={categoryLeadTimesText}
                onChange={(event) => setCategoryLeadTimesText(event.target.value)}
                placeholder={"outerwear | 18\ntops | 12"}
              />
            </label>
            <p className="section-copy">Format: category | lead time days</p>
          </SectionCard>
        </div>

        <div className="button-row">
          <button type="submit" className="button button-primary" disabled={isSavingSettings}>
            {isSavingSettings ? "Saving settings..." : "Save settings"}
          </button>
        </div>
      </form>

      {settingsError ? (
        <EmptyState
          title="Settings unavailable"
          description={settingsError}
          tone="error"
        />
      ) : null}

      {settingsNotice ? (
        <EmptyState title="Settings ready" description={settingsNotice} />
      ) : null}
    </div>
  );
}
