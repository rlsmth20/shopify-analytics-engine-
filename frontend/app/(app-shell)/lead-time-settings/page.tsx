"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type FormEvent } from "react";

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
  const { shopifyDomain, setShopifyDomain, hasHydrated } = useStoredShopDomain();
  const [defaultLeadTimeDays, setDefaultLeadTimeDays] = useState("14");
  const [safetyBufferDays, setSafetyBufferDays] = useState("7");
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

  const effectivePreview = useMemo(
    () =>
      syncedSkus.slice(0, 8).map((sku) =>
        resolveEffectiveLeadTime({
          sku,
          defaultLeadTimeDays,
          skuMap,
          supplierMap,
          categoryMap
        })
      ),
    [categoryMap, defaultLeadTimeDays, skuMap, supplierMap, syncedSkus]
  );

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
      const [settings, vendorLeadTimes, categoryLeadTimes, skuLeadTimes, skus] =
        await Promise.all([
          fetchShopSettings(targetDomain),
          fetchVendorLeadTimes(targetDomain),
          fetchCategoryLeadTimes(targetDomain),
          fetchSkuLeadTimes(targetDomain),
          fetchSkus()
        ]);
      applyShopSettings(settings);
      setShopifyDomain(settings.shopify_domain);
      setSyncedSkus(skus);
      setSupplierRows(
        withEmptyFallback(
          vendorLeadTimes.items.map((item) =>
            buildOverrideRow(item.vendor, item.lead_time_days)
          )
        )
      );
      setCategoryRows(
        withEmptyFallback(
          categoryLeadTimes.items.map((item) =>
            buildOverrideRow(item.category, item.lead_time_days)
          )
        )
      );
      setSkuRows(
        skuLeadTimes.items.map((item) => {
          const sku = skus.find((candidate) => candidate.sku_id === item.sku_id);
          return buildSkuRow(item.sku_id, item.lead_time_days ?? "", sku);
        })
      );
      setSkuOverridePage(1);
      setSettingsNotice(
        settings.is_persisted
          ? "Loaded saved lead-time rules. SKU overrides beat supplier and category defaults."
          : "Loaded default lead-time rules. Add supplier, category, or SKU overrides as needed."
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

    if (
      Number.isNaN(nextDefaultLeadTimeDays) ||
      nextDefaultLeadTimeDays < 1 ||
      Number.isNaN(nextSafetyBufferDays) ||
      nextSafetyBufferDays < 0
    ) {
      setSettingsError("Lead time must be at least 1 day and safety buffer cannot be negative.");
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

    setIsSavingSettings(true);
    setSettingsError(null);
    setSettingsNotice(null);

    try {
      const [settings, savedSupplierLeadTimes, savedCategoryLeadTimes, savedSkuLeadTimes] =
        await Promise.all([
          saveShopSettings({
            shopify_domain: targetDomain,
            global_default_lead_time_days: nextDefaultLeadTimeDays,
            global_safety_buffer_days: nextSafetyBufferDays,
            allow_mock_fallback: allowMockFallback
          }),
          saveVendorLeadTimes({
            shopify_domain: targetDomain,
            items: supplierLeadTimes
          }),
          saveCategoryLeadTimes({
            shopify_domain: targetDomain,
            items: categoryLeadTimes
          }),
          saveSkuLeadTimes({
            shopify_domain: targetDomain,
            items: skuLeadTimes
          })
        ]);
      applyShopSettings(settings);
      setShopifyDomain(settings.shopify_domain);
      setSupplierRows(
        withEmptyFallback(
          savedSupplierLeadTimes.items.map((item) =>
            buildOverrideRow(item.vendor, item.lead_time_days)
          )
        )
      );
      setCategoryRows(
        withEmptyFallback(
          savedCategoryLeadTimes.items.map((item) =>
            buildOverrideRow(item.category, item.lead_time_days)
          )
        )
      );
      setSkuRows(
        savedSkuLeadTimes.items.map((item) => {
          const sku = syncedSkus.find((candidate) => candidate.sku_id === item.sku_id);
          return buildSkuRow(item.sku_id, item.lead_time_days ?? "", sku);
        })
      );
      setSkuOverridePage(1);
      setSettingsNotice(
        `Saved ${savedSkuLeadTimes.items.length} SKU, ${savedSupplierLeadTimes.items.length} supplier, and ${savedCategoryLeadTimes.items.length} category lead-time rules.`
      );
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
            <p className="section-eyebrow">Inventory Rules</p>
            <h2 className="section-title">Lead-time control center</h2>
          </div>
          <p className="section-copy">
            Set default, supplier, category, and SKU-specific lead times that feed the Action Queue, Forecast, and Reorder / POs.
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
            {isLoadingSettings ? "Loading..." : "Refresh rules"}
          </button>
        </div>
      </SectionCard>

      <form className="page-stack" onSubmit={handleSaveSettings}>
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
                {settingsPersisted ? "Saved" : "Default"}
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

            <details className="advanced-settings">
              <summary>Advanced settings</summary>
              <label className="toggle-row">
                <div>
                  <span className="toggle-title">Allow sample fallback</span>
                  <p className="toggle-copy">
                    If disabled, the Action Queue returns an error when the database does not have usable live data.
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={allowMockFallback}
                  onChange={(event) => setAllowMockFallback(event.target.checked)}
                />
              </label>
            </details>
          </SectionCard>

          <SectionCard>
            <div className="section-heading">
              <div>
                <p className="section-eyebrow">Effective Preview</p>
                <h2 className="section-title section-title-small">Which rule will apply</h2>
              </div>
            </div>
            {effectivePreview.length ? (
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
              {skuRows.length} overrides
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
                {syncedSkus.length} synced SKUs
              </span>
              <span className="status-badge status-neutral">
                {skuRows.length} overrides
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
                  <small>{sku.sku_id} · {sku.vendor} · {sku.category}</small>
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
              <div className="lead-time-table-wrap">
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
              title="No SKU overrides yet"
              description="Add SKU overrides only for products whose lead time is different from supplier or category defaults."
            />
          )}
        </SectionCard>

        <div className="button-row sticky-action-row">
          <button type="submit" className="button button-primary" disabled={isSavingSettings}>
            {isSavingSettings ? "Saving lead-time rules..." : "Save lead-time rules"}
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

      <div className="lead-time-table-wrap">
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
    const leadTimeDays = Number.parseInt(row.lead_time_days, 10);
    if (!name) {
      throw new Error(`${label} lead-time rows need a name.`);
    }
    if (Number.isNaN(leadTimeDays) || leadTimeDays < 1) {
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
