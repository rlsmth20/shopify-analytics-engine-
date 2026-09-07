"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import { EmptyState } from "@/components/empty-state";
import { GatedFeature } from "@/components/gated-feature";
import { SectionCard } from "@/components/section-card";
import {
  fetchCategoryLeadTimes,
  fetchShopSettings,
  fetchSkuLeadTimes,
  fetchSkus,
  fetchVendorLeadTimes,
  saveCategoryLeadTimes,
  saveShopSettings,
  saveSkuLeadTimes,
  saveVendorLeadTimes,
  type CategoryLeadTimeEntry,
  type ShopSettingsResponse,
  type SkuDetail,
  type SkuLeadTimeEntry,
  type VendorLeadTimeEntry
} from "@/lib/api";
import { useStoredShopDomain } from "@/lib/use-stored-shop-domain";
import { useAuth } from "@/components/auth-guard";
import styles from "./page.module.css";

type OverrideRow = {
  id: string;
  name: string;
  lead_time_days: string;
};

type SkuOverrideRow = OverrideRow & {
  productName: string;
  supplier: string;
  category: string;
};

type LeadTimeSource = "sku" | "supplier" | "category" | "global";
const SKU_SEARCH_MIN_LENGTH = 2;
const SKU_OVERRIDE_PAGE_SIZE = 25;
const WRITE_SECTIONS = ["defaults", "suppliers", "categories", "skus"] as const;
const LOAD_SECTIONS = [...WRITE_SECTIONS, "catalog"] as const;
type WriteSection = typeof WRITE_SECTIONS[number];
type LoadSection = typeof LOAD_SECTIONS[number];
type LoadStatus = { status: "loading" | "ready" | "error"; error?: string };
const SECTION_LABELS: Record<LoadSection, string> = { defaults: "Global defaults", suppliers: "Supplier rules", categories: "Category rules", skus: "SKU rules", catalog: "Product lookup" };

export default function LeadTimeSettingsPage() {
  return (
    <GatedFeature
      capability="inventory_rules_advanced"
      title="Customize inventory rules"
      description="Upgrade to Growth to customize lead times, safety buffer, target coverage, and reorder assumptions."
    >
      <LeadTimeSettingsContent />
    </GatedFeature>
  );
}

function LeadTimeSettingsContent() {
  const { user } = useAuth();
  const demo = user.id === 0;
  const { shopifyDomain, setShopifyDomain, hasHydrated } = useStoredShopDomain();
  const [defaultLeadTimeDays, setDefaultLeadTimeDays] = useState("14");
  const [safetyBufferDays, setSafetyBufferDays] = useState("7");
  // Preserve the compatibility field exactly as loaded; it is not a live-data control.
  const [allowMockFallback, setAllowMockFallback] = useState(true);
  const [supplierRows, setSupplierRows] = useState<OverrideRow[]>([]);
  const [categoryRows, setCategoryRows] = useState<OverrideRow[]>([]);
  const [skuRows, setSkuRows] = useState<SkuOverrideRow[]>([]);
  const [syncedSkus, setSyncedSkus] = useState<SkuDetail[]>([]);
  const [skuSearch, setSkuSearch] = useState("");
  const [skuOverridePage, setSkuOverridePage] = useState(1);
  const [settingsPersisted, setSettingsPersisted] = useState(false);
  const [isLoadingSettings, setIsLoadingSettings] = useState(false);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [settingsNotice, setSettingsNotice] = useState<string | null>(null);
  const [loadStates, setLoadStates] = useState<Record<LoadSection, LoadStatus>>(() => Object.fromEntries(LOAD_SECTIONS.map(key => [key, { status: "loading" }])) as Record<LoadSection, LoadStatus>);
  const savedSignatures = useRef<Partial<Record<WriteSection, string>>>({});
  const loadController = useRef<AbortController | null>(null);
  const saveController = useRef<AbortController | null>(null);
  const catalogRef = useRef<SkuDetail[]>([]);
  const settingsConfirmed = WRITE_SECTIONS.every(key => loadStates[key].status === "ready");
  const failedLoads = LOAD_SECTIONS.filter(key => loadStates[key].status === "error");

  const supplierNames = useMemo(
    () => uniqueValues(syncedSkus.map((sku) => sku.vendor)),
    [syncedSkus]
  );
  const categoryNames = useMemo(
    () => uniqueValues(syncedSkus.map((sku) => sku.category)),
    [syncedSkus]
  );

  const supplierMap = useMemo(
    () => rowsToMap(supplierRows),
    [supplierRows]
  );
  const categoryMap = useMemo(
    () => rowsToMap(categoryRows),
    [categoryRows]
  );
  const skuMap = useMemo(() => rowsToMap(skuRows), [skuRows]);

  const filteredSkuSuggestions = useMemo(() => {
    const query = skuSearch.trim().toLowerCase();
    if (query.length < SKU_SEARCH_MIN_LENGTH) {
      return [];
    }
    return syncedSkus
      .filter((sku) =>
        [sku.sku_id, sku.name, sku.vendor, sku.category]
          .join(" ")
          .toLowerCase()
          .includes(query)
      )
      .slice(0, 10);
  }, [skuSearch, syncedSkus]);

  const pagedSkuRows = useMemo(() => {
    const start = (skuOverridePage - 1) * SKU_OVERRIDE_PAGE_SIZE;
    return skuRows.slice(start, start + SKU_OVERRIDE_PAGE_SIZE);
  }, [skuOverridePage, skuRows]);

  const skuOverridePageCount = Math.max(
    1,
    Math.ceil(skuRows.length / SKU_OVERRIDE_PAGE_SIZE)
  );

  const draftValid = useMemo(() => {
    try {
      if (!defaultLeadTimeDays.trim() || !safetyBufferDays.trim()
        || !Number.isSafeInteger(Number(defaultLeadTimeDays)) || Number(defaultLeadTimeDays) < 1
        || !Number.isSafeInteger(Number(safetyBufferDays)) || Number(safetyBufferDays) < 0) return false;
      parseOverrideRows(supplierRows, "Supplier");
      parseOverrideRows(categoryRows, "Category");
      parseOverrideRows(skuRows, "SKU");
      return true;
    } catch { return false; }
  }, [defaultLeadTimeDays, safetyBufferDays, supplierRows, categoryRows, skuRows]);

  const effectivePreview = useMemo(
    () =>
      (draftValid ? syncedSkus.slice(0, 8) : []).map((sku) =>
        resolveEffectiveLeadTime({
          sku,
          defaultLeadTimeDays,
          skuMap,
          supplierMap,
          categoryMap
        })
      ),
    [categoryMap, defaultLeadTimeDays, skuMap, supplierMap, syncedSkus, draftValid]
  );

  async function loadSettings(domain: string, sections: readonly LoadSection[] = LOAD_SECTIONS) {
    if (demo) return;
    const targetDomain = domain.trim() || "current-shop";
    loadController.current?.abort();
    const controller = new AbortController();
    loadController.current = controller;
    setIsLoadingSettings(true);
    setSettingsError(null);
    setSettingsNotice(null);
    setLoadStates(previous => ({ ...previous, ...Object.fromEntries(sections.map(key => [key, { status: "loading" }])) }));
    const loaders: Record<LoadSection, () => Promise<void>> = {
      defaults: async () => {
        const settings = confirmSettings(await fetchShopSettings(targetDomain, controller.signal));
        if (controller.signal.aborted) return;
        applyShopSettings(settings);
        setShopifyDomain(settings.shopify_domain);
        savedSignatures.current.defaults = settingsSignature(settings);
      },
      suppliers: async () => {
        const items = confirmOverrides(await fetchVendorLeadTimes(targetDomain, controller.signal), "vendor");
        if (controller.signal.aborted) return;
        setSupplierRows(withEmptyFallback(items.map(item => buildOverrideRow(item.name, item.lead_time_days))));
        savedSignatures.current.suppliers = overrideSignature(items);
      },
      categories: async () => {
        const items = confirmOverrides(await fetchCategoryLeadTimes(targetDomain, controller.signal), "category");
        if (controller.signal.aborted) return;
        setCategoryRows(withEmptyFallback(items.map(item => buildOverrideRow(item.name, item.lead_time_days))));
        savedSignatures.current.categories = overrideSignature(items);
      },
      skus: async () => {
        const items = confirmOverrides(await fetchSkuLeadTimes(targetDomain, controller.signal), "sku_id");
        if (controller.signal.aborted) return;
        setSkuRows(items.map(item => buildSkuRow(item.name, item.lead_time_days, catalogRef.current.find(sku => sku.sku_id === item.name))));
        savedSignatures.current.skus = overrideSignature(items);
        setSkuOverridePage(1);
      },
      catalog: async () => {
        const skus = await fetchSkus(controller.signal);
        if (!Array.isArray(skus) || !skus.every(sku => sku && [sku.sku_id, sku.name, sku.vendor, sku.category].every(value => typeof value === "string"))) throw new Error("Product lookup response is incomplete.");
        if (controller.signal.aborted) return;
        catalogRef.current = skus;
        setSyncedSkus(skus);
        setSkuRows(rows => rows.map(row => {
          const sku = skus.find(item => item.sku_id === row.name);
          return sku ? { ...row, productName: sku.name, supplier: sku.vendor, category: sku.category } : row;
        }));
      },
    };
    await Promise.allSettled(sections.map(async key => {
      try {
        await loaders[key]();
        if (!controller.signal.aborted) setLoadStates(previous => ({ ...previous, [key]: { status: "ready" } }));
      } catch (error) {
        if (!controller.signal.aborted) setLoadStates(previous => ({ ...previous, [key]: { status: "error", error: error instanceof Error ? error.message : "Could not load saved settings." } }));
      }
    }));
    if (!controller.signal.aborted) setIsLoadingSettings(false);
  }

  async function handleLoadSettings() {
    if (isSavingSettings) return;
    await loadSettings(shopifyDomain, failedLoads.length ? failedLoads : LOAD_SECTIONS);
  }

  async function handleSaveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (demo || !settingsConfirmed || isLoadingSettings || isSavingSettings) {
      if (!demo) setSettingsError("Load all saved rule sections before saving. Existing rules have not been replaced.");
      return;
    }
    const targetDomain = shopifyDomain.trim() || "current-shop";

    const nextDefaultLeadTimeDays = Number(defaultLeadTimeDays);
    const nextSafetyBufferDays = Number(safetyBufferDays);

    if (
      !defaultLeadTimeDays.trim() || !safetyBufferDays.trim() ||
      !Number.isSafeInteger(nextDefaultLeadTimeDays) ||
      nextDefaultLeadTimeDays < 1 ||
      !Number.isSafeInteger(nextSafetyBufferDays) ||
      nextSafetyBufferDays < 0
    ) {
      setSettingsError("Use whole numbers: lead time must be at least 1 day and safety buffer cannot be negative.");
      return;
    }

    let supplierLeadTimes: VendorLeadTimeEntry[] = [];
    let categoryLeadTimes: CategoryLeadTimeEntry[] = [];
    let skuLeadTimes: SkuLeadTimeEntry[] = [];

    try {
      supplierLeadTimes = parseOverrideRows(supplierRows, "supplier").map((item) => ({
        vendor: item.name,
        lead_time_days: item.lead_time_days
      }));
      categoryLeadTimes = parseOverrideRows(categoryRows, "category").map((item) => ({
        category: item.name,
        lead_time_days: item.lead_time_days
      }));
      skuLeadTimes = parseOverrideRows(skuRows, "SKU").map((item) => ({
        sku_id: item.name,
        lead_time_days: item.lead_time_days
      }));
    } catch (error) {
      setSettingsError(
        error instanceof Error
          ? error.message
          : "Lead-time overrides could not be validated."
      );
      return;
    }

    const defaults = { shopify_domain: targetDomain, global_default_lead_time_days: nextDefaultLeadTimeDays,
      global_safety_buffer_days: nextSafetyBufferDays, allow_mock_fallback: allowMockFallback };
    const signatures: Record<WriteSection, string> = {
      defaults: settingsSignature(defaults),
      suppliers: overrideSignature(supplierLeadTimes.map(item => ({ name: item.vendor, lead_time_days: item.lead_time_days }))),
      categories: overrideSignature(categoryLeadTimes.map(item => ({ name: item.category, lead_time_days: item.lead_time_days }))),
      skus: overrideSignature(skuLeadTimes.map(item => ({ name: item.sku_id, lead_time_days: item.lead_time_days! }))),
    };
    const changed = WRITE_SECTIONS.filter(key => signatures[key] !== savedSignatures.current[key] || (key === "defaults" && !settingsPersisted));
    if (!changed.length) { setSettingsError(null); setSettingsNotice("No unsaved rule changes."); return; }
    const controller = new AbortController();
    saveController.current = controller;
    setIsSavingSettings(true); setSettingsError(null); setSettingsNotice(null);
    const writers: Record<WriteSection, () => Promise<void>> = {
      defaults: async () => {
        const saved = confirmSettings(await saveShopSettings(defaults, controller.signal));
        if (!saved.is_persisted || settingsSignature(saved) !== signatures.defaults) throw new Error("The stored defaults were not confirmed with the requested values.");
        if (!controller.signal.aborted) applyShopSettings(saved);
      },
      suppliers: async () => {
        const saved = confirmOverrides(await saveVendorLeadTimes({ shopify_domain: targetDomain, items: supplierLeadTimes }, controller.signal), "vendor");
        if (overrideSignature(saved) !== signatures.suppliers) throw new Error("The saved supplier rules did not match the requested values.");
        if (!controller.signal.aborted) setSupplierRows(withEmptyFallback(saved.map(item => buildOverrideRow(item.name, item.lead_time_days))));
      },
      categories: async () => {
        const saved = confirmOverrides(await saveCategoryLeadTimes({ shopify_domain: targetDomain, items: categoryLeadTimes }, controller.signal), "category");
        if (overrideSignature(saved) !== signatures.categories) throw new Error("The saved category rules did not match the requested values.");
        if (!controller.signal.aborted) setCategoryRows(withEmptyFallback(saved.map(item => buildOverrideRow(item.name, item.lead_time_days))));
      },
      skus: async () => {
        const saved = confirmOverrides(await saveSkuLeadTimes({ shopify_domain: targetDomain, items: skuLeadTimes }, controller.signal), "sku_id");
        if (overrideSignature(saved) !== signatures.skus) throw new Error("The saved SKU rules did not match the requested values.");
        if (!controller.signal.aborted) setSkuRows(saved.map(item => buildSkuRow(item.name, item.lead_time_days, catalogRef.current.find(sku => sku.sku_id === item.name))));
      },
    };
    const results = await Promise.allSettled(changed.map(async key => {
      await writers[key]();
      if (!controller.signal.aborted) savedSignatures.current[key] = signatures[key];
    }));
    if (controller.signal.aborted) return;
    const succeeded = changed.filter((_, index) => results[index].status === "fulfilled");
    const failed = changed.flatMap((key, index) => {
      const result = results[index];
      return result.status === "rejected" ? [`${SECTION_LABELS[key]}: ${result.reason instanceof Error ? result.reason.message : "Save was not confirmed."}`] : [];
    });
    setIsSavingSettings(false);
    if (succeeded.length) setSettingsNotice(`Saved: ${succeeded.map(key => SECTION_LABELS[key]).join(", ")}.`);
    if (failed.length) setSettingsError(`Not confirmed: ${failed.join(" ")} Your edits are retained. Some requests may have reached the server. Save again to retry only sections with unsaved changes, or reload saved rules to check the stored values.`);
  }

  function applyShopSettings(settings: ShopSettingsResponse) {
    setDefaultLeadTimeDays(String(settings.global_default_lead_time_days));
    setSafetyBufferDays(String(settings.global_safety_buffer_days));
    setAllowMockFallback(settings.allow_mock_fallback);
    setSettingsPersisted(settings.is_persisted);
  }

  function addSupplierRow(name = "") {
    setSupplierRows((rows) => [...trimBlankRows(rows), buildOverrideRow(name, "")]);
  }

  function addCategoryRow(name = "") {
    setCategoryRows((rows) => [...trimBlankRows(rows), buildOverrideRow(name, "")]);
  }

  function addSkuRow(sku: SkuDetail) {
    setSkuRows((rows) => {
      if (rows.some((row) => row.name === sku.sku_id)) {
        return rows;
      }
      return [...rows, buildSkuRow(sku.sku_id, sku.sku_lead_time_days ?? "", sku)];
    });
    setSkuSearch("");
    setSkuOverridePage(1);
  }

  useEffect(() => {
    if (!hasHydrated || demo) {
      return;
    }

    setIsSavingSettings(false);
    savedSignatures.current = {};
    catalogRef.current = [];
    void loadSettings(shopifyDomain.trim() || "current-shop");
    return () => { loadController.current?.abort(); saveController.current?.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasHydrated, user.id]);

  if (demo) return <SectionCard><h2 className="section-title">Lead-time settings in the sample workspace</h2><p className="section-copy">Sample recommendations use example lead times. No store settings are loaded or changed here. Sign in to configure your own supplier, category, and SKU rules.</p><Link className="button button-primary" href="/login">Sign in to set up lead times</Link></SectionCard>;

  return (
    <div className={`page-stack ${styles.page}`}>
      <SectionCard>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Inventory Rules</p>
            <h2 className="section-title">Lead-time control center</h2>
          </div>
          <p className="section-copy">
            Set default, supplier, category, and SKU-specific lead times that feed the Action Queue, Forecast, and Reorder / POs.
          </p>
        </div>

        <div className="settings-scope-row">
          <div className="field-label field-label-grow">
            <span>Connected workspace</span>
            <p className="section-copy">{shopifyDomain || "Your authenticated workspace"}</p>
            <Link href="/store-sync">Manage Shopify connection</Link>
          </div>

          <button
            type="button"
            className="button button-secondary"
            disabled={isLoadingSettings || isSavingSettings}
            onClick={() => void handleLoadSettings()}
          >
            {isLoadingSettings ? "Loading..." : failedLoads.length ? "Retry failed reads" : "Reload saved rules"}
          </button>
        </div>
      </SectionCard>

      <SectionCard>
        <p className="section-copy" role="status">{settingsConfirmed ? "Saved rule sections are loaded. Only sections with changes will be saved." : "Waiting for saved rule sections. Saving is disabled to protect your existing overrides."}</p>
        <ul className="section-copy">{LOAD_SECTIONS.map(key => <li key={key}><strong>{SECTION_LABELS[key]}:</strong> {loadStates[key].status === "ready" ? "Loaded" : loadStates[key].status === "loading" ? "Loading…" : `Unavailable — ${loadStates[key].error}`}</li>)}</ul>
        {failedLoads.length > 0 ? <p className="section-copy">Retry failed reads to keep the sections already loaded. A missing product lookup does not erase saved SKU overrides.</p> : <p className="section-copy">Reloading saved rules replaces unsaved edits with the stored values.</p>}
      </SectionCard>

      <form className="page-stack" onSubmit={handleSaveSettings}>
        <fieldset className="page-stack" disabled={!settingsConfirmed || isLoadingSettings || isSavingSettings} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
        <SectionCard>
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">How Skubase decides</p>
              <h2 className="section-title section-title-small">Most specific rule wins</h2>
            </div>
            <Link href="/alerts" className="button button-secondary button-sm">
              Create alert rule
            </Link>
          </div>
          <div className="lead-time-priority-grid">
            <PriorityStep number="1" title="SKU override" copy="Use this for hero SKUs, fragile items, import products, or anything with a known exception." />
            <PriorityStep number="2" title="Supplier lead time" copy="Set the normal delivery window for each supplier so all their SKUs inherit it." />
            <PriorityStep number="3" title="Category lead time" copy="Use category defaults for product types that behave similarly, like accessories or apparel." />
            <PriorityStep number="4" title="Global default" copy="Everything else falls back to the shop-wide default and safety buffer." />
          </div>
        </SectionCard>

        <div className="content-grid content-grid-2-1">
          <SectionCard>
            <div className="section-heading">
              <div>
                <p className="section-eyebrow">Global Defaults</p>
                <h2 className="section-title section-title-small">Baseline assumptions</h2>
              </div>
              <span className="status-badge status-neutral">
                {loadStates.defaults.status !== "ready" ? "Not confirmed" : settingsPersisted ? "Saved" : "Default"}
              </span>
            </div>

            <div className="form-grid">
              <label className="field-label">
                <span>Default supplier lead time</span>
                <input
                  className="input-control"
                  type="number"
                  min={1}
                  value={defaultLeadTimeDays}
                  onChange={(event) => setDefaultLeadTimeDays(event.target.value)}
                />
                <small>Used when no SKU, supplier, or category rule exists.</small>
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
                <small>Extra cover added to reorder targets so late receipts do not immediately create stockouts.</small>
              </label>
            </div>

          </SectionCard>

          <SectionCard>
            <div className="section-heading">
              <div>
                <p className="section-eyebrow">Effective Preview</p>
                <h2 className="section-title section-title-small">Which rule will apply</h2>
              </div>
            </div>
            {!settingsConfirmed ? <p className="section-copy">Load all rule sections before previewing which lead time applies.</p> : !draftValid ? <p className="section-copy">Enter valid whole-day lead times and complete each override before previewing these changes.</p> : loadStates.catalog.status !== "ready" ? <p className="section-copy">Product lookup is unavailable. Retry it to preview how the saved rules apply to products.</p> : effectivePreview.length ? (
              <div className="lead-time-preview-list">
                {effectivePreview.map((item) => (
                  <div className="lead-time-preview-row" key={item.sku.sku_id}>
                    <div>
                      <strong>{item.sku.name}</strong>
                      <span>{item.sku.sku_id}</span>
                    </div>
                    <div>
                      <b>{item.days} days</b>
                      <span>{sourceLabel(item.source)}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="section-copy">
                Sync products to preview which SKU, supplier, category, or default lead time will be used.
              </p>
            )}
          </SectionCard>
        </div>

        <div className="content-grid content-grid-2-2">
          <LeadTimeTable
            eyebrow="Supplier rules"
            title="Supplier lead times"
            description="Every SKU from the same supplier inherits this lead time unless the SKU has its own override."
            nameLabel="Supplier"
            rows={supplierRows}
            suggestions={supplierNames}
            onAdd={addSupplierRow}
            onRowsChange={setSupplierRows}
          />

          <LeadTimeTable
            eyebrow="Category rules"
            title="Category lead times"
            description="Use category defaults when the supplier is unknown or a product type has a predictable fulfillment window."
            nameLabel="Category"
            rows={categoryRows}
            suggestions={categoryNames}
            onAdd={addCategoryRow}
            onRowsChange={setCategoryRows}
          />
        </div>

        <SectionCard>
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">SKU rules</p>
              <h2 className="section-title section-title-small">SKU-specific lead times</h2>
            </div>
            <span className="status-badge status-neutral">
              {loadStates.skus.status === "ready" ? `${skuRows.length} overrides` : "Overrides not confirmed"}
            </span>
          </div>
          <p className="section-copy">
            Use SKU overrides for exceptions: imported products, made-to-order items, best sellers with special freight, or products with supplier-specific delays.
          </p>

          <div className="lead-time-sku-search">
            <label className="field-label field-label-grow">
              <span>Find SKU to override</span>
              <input
                className="input-control"
                type="search"
                placeholder="Search product, SKU, supplier, or category"
                value={skuSearch}
                onChange={(event) => setSkuSearch(event.target.value)}
              />
              <small>Type at least 2 characters. Skubase only shows the top 10 matches so large catalogs stay usable.</small>
            </label>
            <div className="lead-time-sku-counts">
              <span className="status-badge status-neutral">
                {loadStates.catalog.status === "ready" ? `${syncedSkus.length} synced SKUs` : "Product lookup unavailable"}
              </span>
              <span className="status-badge status-neutral">
                {loadStates.skus.status === "ready" ? `${skuRows.length} overrides` : "Overrides not confirmed"}
              </span>
            </div>
          </div>

          {skuSearch.trim().length < SKU_SEARCH_MIN_LENGTH ? (
            <p className="section-copy">
              Search for a SKU when you need an exception. Supplier and category rules cover the bulk of the catalog.
            </p>
          ) : filteredSkuSuggestions.length ? (
            <div className="lead-time-sku-suggestions">
              {filteredSkuSuggestions.map((sku) => (
                <button
                  type="button"
                  className="lead-time-suggestion"
                  key={sku.sku_id}
                  onClick={() => addSkuRow(sku)}
                >
                  <span>{sku.name}</span>
                  <small>{sku.sku_id} - {sku.vendor} - {sku.category}</small>
                </button>
              ))}
            </div>
          ) : (
            <p className="section-copy">
              No matching synced SKUs. Sync products first, then add SKU-specific lead times.
            </p>
          )}

          {skuRows.length ? (
            <div className="lead-time-override-section">
              <div className="lead-time-override-toolbar">
                <p className="section-copy">
                  Showing {pagedSkuRows.length} of {skuRows.length} SKU overrides.
                </p>
                {skuOverridePageCount > 1 ? (
                  <div className="button-row">
                    <button
                      type="button"
                      className="button button-secondary button-sm"
                      disabled={skuOverridePage === 1}
                      onClick={() => setSkuOverridePage((page) => Math.max(1, page - 1))}
                    >
                      Previous
                    </button>
                    <span className="status-badge status-neutral">
                      Page {skuOverridePage} of {skuOverridePageCount}
                    </span>
                    <button
                      type="button"
                      className="button button-secondary button-sm"
                      disabled={skuOverridePage === skuOverridePageCount}
                      onClick={() =>
                        setSkuOverridePage((page) =>
                          Math.min(skuOverridePageCount, page + 1)
                        )
                      }
                    >
                      Next
                    </button>
                  </div>
                ) : null}
              </div>
              <div className="lead-time-table-wrap" role="region" aria-label="SKU lead-time overrides; scroll horizontally to view all columns" tabIndex={0}>
                <table className="lead-time-table">
                  <thead>
                    <tr>
                      <th>SKU</th>
                      <th>Supplier</th>
                      <th>Category</th>
                      <th>Lead time</th>
                      <th aria-label="Actions" />
                    </tr>
                  </thead>
                  <tbody>
                    {pagedSkuRows.map((row) => (
                      <tr key={row.id}>
                        <td>
                          <strong>{row.productName || row.name}</strong>
                          <span>{row.name}</span>
                        </td>
                        <td>{row.supplier || "Unassigned"}</td>
                        <td>{row.category || "Uncategorized"}</td>
                        <td>
                          <input
                            className="input-control lead-time-days-input"
                            type="number"
                            min={1}
                            value={row.lead_time_days}
                            onChange={(event) =>
                              setSkuRows((rows) =>
                                updateRow(rows, row.id, "lead_time_days", event.target.value)
                              )
                            }
                          />
                        </td>
                        <td>
                          <button
                            type="button"
                            className="button button-secondary button-sm"
                            onClick={() =>
                              setSkuRows((rows) => {
                                const nextRows = rows.filter((candidate) => candidate.id !== row.id);
                                const nextPageCount = Math.max(
                                  1,
                                  Math.ceil(nextRows.length / SKU_OVERRIDE_PAGE_SIZE)
                                );
                                setSkuOverridePage((page) => Math.min(page, nextPageCount));
                                return nextRows;
                              })
                            }
                          >
                            Remove
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <EmptyState
              title={loadStates.skus.status === "ready" ? "No SKU overrides yet" : "SKU overrides are not confirmed"}
              description={loadStates.skus.status === "ready" ? "Add SKU overrides only for products whose lead time is different from supplier or category defaults." : "Load the saved SKU rules before changing them. Existing overrides have not been removed."}
            />
          )}
        </SectionCard>

        <div className="button-row sticky-action-row">
          <button type="submit" className="button button-primary" disabled={!settingsConfirmed || isLoadingSettings || isSavingSettings}>
            {isSavingSettings ? "Saving lead-time rules..." : "Save lead-time rules"}
          </button>
        </div>
        </fieldset>
      </form>

      {settingsError ? (
        <EmptyState
          title="Settings update needs attention"
          description={settingsError}
          tone="error"
        />
      ) : null}

      {settingsNotice ? (
        <EmptyState title="Settings update" description={settingsNotice} />
      ) : null}
    </div>
  );
}

function PriorityStep({
  number,
  title,
  copy
}: {
  number: string;
  title: string;
  copy: string;
}) {
  return (
    <div className="lead-time-priority-step">
      <span>{number}</span>
      <div>
        <strong>{title}</strong>
        <p>{copy}</p>
      </div>
    </div>
  );
}

function LeadTimeTable({
  eyebrow,
  title,
  description,
  nameLabel,
  rows,
  suggestions,
  onAdd,
  onRowsChange
}: {
  eyebrow: string;
  title: string;
  description: string;
  nameLabel: string;
  rows: OverrideRow[];
  suggestions: string[];
  onAdd: (name?: string) => void;
  onRowsChange: (rows: OverrideRow[]) => void;
}) {
  return (
    <SectionCard>
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">{eyebrow}</p>
          <h2 className="section-title section-title-small">{title}</h2>
        </div>
        <button
          type="button"
          className="button button-secondary button-sm"
          onClick={() => onAdd()}
        >
          Add row
        </button>
      </div>
      <p className="section-copy">{description}</p>

      {suggestions.length ? (
        <div className="lead-time-chip-row">
          {suggestions.slice(0, 8).map((suggestion) => (
            <button
              type="button"
              className="filter-chip"
              key={suggestion}
              onClick={() => onAdd(suggestion)}
            >
              {suggestion}
            </button>
          ))}
        </div>
      ) : null}

      <div className="lead-time-table-wrap" role="region" aria-label={`${nameLabel} lead-time rules; scroll horizontally to view all columns`} tabIndex={0}>
        <table className="lead-time-table">
          <thead>
            <tr>
              <th>{nameLabel}</th>
              <th>Lead time</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <input
                    className="input-control"
                    type="text"
                    value={row.name}
                    placeholder={nameLabel}
                    onChange={(event) =>
                      onRowsChange(updateRow(rows, row.id, "name", event.target.value))
                    }
                  />
                </td>
                <td>
                  <input
                    className="input-control lead-time-days-input"
                    type="number"
                    min={1}
                    value={row.lead_time_days}
                    onChange={(event) =>
                      onRowsChange(
                        updateRow(rows, row.id, "lead_time_days", event.target.value)
                      )
                    }
                  />
                </td>
                <td>
                  <button
                    type="button"
                    className="button button-secondary button-sm"
                    onClick={() =>
                      onRowsChange(
                        withEmptyFallback(rows.filter((candidate) => candidate.id !== row.id))
                      )
                    }
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

function buildOverrideRow(name: string, leadTimeDays: number | string): OverrideRow {
  return {
    id: crypto.randomUUID(),
    name,
    lead_time_days: leadTimeDays === "" ? "" : String(leadTimeDays)
  };
}

function buildSkuRow(
  skuId: string,
  leadTimeDays: number | string,
  sku?: SkuDetail
): SkuOverrideRow {
  return {
    ...buildOverrideRow(skuId, leadTimeDays),
    productName: sku?.name ?? "",
    supplier: sku?.vendor ?? "",
    category: sku?.category ?? ""
  };
}

function updateRow<T extends OverrideRow>(
  rows: T[],
  id: string,
  field: "name" | "lead_time_days",
  value: string
): T[] {
  return rows.map((row) => (row.id === id ? { ...row, [field]: value } : row));
}

function trimBlankRows<T extends OverrideRow>(rows: T[]): T[] {
  return rows.filter((row) => row.name.trim() || row.lead_time_days.trim());
}

function withEmptyFallback(rows: OverrideRow[]): OverrideRow[] {
  return rows.length ? rows : [buildOverrideRow("", "")];
}

function parseOverrideRows(rows: OverrideRow[], label: string) {
  const normalized = trimBlankRows(rows);
  const seen = new Set<string>();

  return normalized.map((row) => {
    const name = row.name.trim();
    const leadTimeDays = Number(row.lead_time_days);
    if (!name) {
      throw new Error(`${label} lead-time rows need a name.`);
    }
    if (!row.lead_time_days.trim() || !Number.isSafeInteger(leadTimeDays) || leadTimeDays < 1) {
      throw new Error(`${label} lead-time rows need a whole number of at least 1 day.`);
    }
    const key = name.toLowerCase();
    if (seen.has(key)) {
      throw new Error(`Duplicate ${label} lead-time row: ${name}.`);
    }
    seen.add(key);
    return { name, lead_time_days: leadTimeDays };
  });
}

function uniqueValues(values: string[]): string[] {
  return Array.from(
    new Set(values.map((value) => value.trim()).filter(Boolean))
  ).sort((a, b) => a.localeCompare(b));
}

function rowsToMap(rows: OverrideRow[]): Map<string, number> {
  const map = new Map<string, number>();
  for (const row of rows) {
    const name = row.name.trim();
    const days = Number.parseInt(row.lead_time_days, 10);
    if (name && !Number.isNaN(days) && days > 0) {
      map.set(name, days);
    }
  }
  return map;
}

function resolveEffectiveLeadTime({
  sku,
  defaultLeadTimeDays,
  skuMap,
  supplierMap,
  categoryMap
}: {
  sku: SkuDetail;
  defaultLeadTimeDays: string;
  skuMap: Map<string, number>;
  supplierMap: Map<string, number>;
  categoryMap: Map<string, number>;
}): { sku: SkuDetail; days: number; source: LeadTimeSource } {
  const fallback = Number.parseInt(defaultLeadTimeDays, 10);
  const defaultDays = Number.isNaN(fallback) || fallback < 1 ? 14 : fallback;
  const skuDays = skuMap.get(sku.sku_id);
  if (skuDays) return { sku, days: skuDays, source: "sku" };
  const supplierDays = supplierMap.get(sku.vendor);
  if (supplierDays) return { sku, days: supplierDays, source: "supplier" };
  const categoryDays = categoryMap.get(sku.category);
  if (categoryDays) return { sku, days: categoryDays, source: "category" };
  return { sku, days: defaultDays, source: "global" };
}

function sourceLabel(source: LeadTimeSource): string {
  if (source === "sku") return "SKU override";
  if (source === "supplier") return "Supplier rule";
  if (source === "category") return "Category rule";
  return "Global default";
}

function confirmSettings(value: unknown): ShopSettingsResponse {
  if (!value || typeof value !== "object") throw new Error("Global defaults response is incomplete.");
  const settings = value as ShopSettingsResponse;
  if (!Number.isSafeInteger(settings.global_default_lead_time_days) || settings.global_default_lead_time_days < 1
    || !Number.isSafeInteger(settings.global_safety_buffer_days) || settings.global_safety_buffer_days < 0
    || typeof settings.allow_mock_fallback !== "boolean" || typeof settings.is_persisted !== "boolean"
    || typeof settings.shopify_domain !== "string") throw new Error("Global defaults response is incomplete.");
  return settings;
}

function confirmOverrides(value: unknown, key: "vendor" | "category" | "sku_id"): { name: string; lead_time_days: number }[] {
  if (!value || typeof value !== "object" || !("items" in value) || !Array.isArray(value.items)) throw new Error("Saved override response is incomplete.");
  const seen = new Set<string>();
  return value.items.flatMap(item => {
    if (!item || typeof item !== "object" || typeof item[key] !== "string" || !item[key].trim()) throw new Error("A saved override has no valid name.");
    if (key === "sku_id" && item.lead_time_days === null) return [];
    if (!Number.isSafeInteger(item.lead_time_days) || item.lead_time_days < 1) throw new Error("A saved override has no valid whole-day lead time.");
    const name = item[key].trim();
    if (seen.has(name.toLowerCase())) throw new Error("The saved response has duplicate override names.");
    seen.add(name.toLowerCase());
    return [{ name, lead_time_days: item.lead_time_days }];
  });
}

function settingsSignature(settings: Pick<ShopSettingsResponse, "global_default_lead_time_days" | "global_safety_buffer_days" | "allow_mock_fallback">): string {
  return JSON.stringify([settings.global_default_lead_time_days, settings.global_safety_buffer_days, settings.allow_mock_fallback]);
}

function overrideSignature(items: { name: string; lead_time_days: number }[]): string {
  return JSON.stringify(items.map(item => [item.name, item.lead_time_days]).sort((a, b) => String(a[0]).localeCompare(String(b[0]))));
}
