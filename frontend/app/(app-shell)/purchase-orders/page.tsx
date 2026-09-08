"use client";

import { isDemoActive } from "@/lib/shopify-embedded";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth-guard";
import { ReceiptRecoveryPanel } from "@/components/receipt-recovery-panel";
import { receiptScope, listPendingReceipts, retainReceiptSubmission, readPendingReceipt, clearReceiptSubmission, confirmedReceiptResponse,
  withReceiptLock, markReceiptRejected, ReceiptSubmissionError,
  type PendingReceipt, type ReceiptInput } from "@/lib/receipt-submission";

import { BuyListEmailCard } from "@/components/buy-list-email-card";
import { CashPlanCard } from "@/components/cash-plan-card";
import { GatedFeature } from "@/components/gated-feature";
import { IdentityReviewNotice } from "@/components/identity-review-notice";
import { productRowKey, receiptLineNeedsIdentityReview, type IdentityIssue } from "@/lib/product-identity";
import {
  fetchBuyingCalendar,
  currency,
  fetchPurchaseOrders,
  receivePurchaseOrder,
  savePurchaseOrder,
  updatePurchaseOrderStatus,
  type BuyingCalendarEvent,
  type BuyingCalendarResponse,
  type PurchaseOrderDraft,
  type PurchaseOrderLine,
} from "@/lib/api-v2";
import { exportBuyPlanReport, exportPurchaseOrderReport } from "@/lib/report-export";
import { financialTotal, financialValue } from "@/lib/financial-values";
import {
  editableUnitCost, normalizeEditableLine, parseMoney, parseWholeNumber,
  previewEditablePoTotals, purchaseOrderCostsKnown, roundCurrency, sumPoTotals,
  type EditablePoDraft, type EditablePoLine,
} from "@/lib/purchase-order-finance";

const SERVICE_LEVELS = [0.9, 0.95, 0.975, 0.99];
const SERVICE_LEVEL_COPY: Record<number, string> = {
  0.9: "Lean: lower safety stock and less cash tied up, with more stockout tolerance.",
  0.95: "Balanced: standard protection for most replenishment decisions.",
  0.975: "Protected: more buffer for important or less predictable SKUs.",
  0.99: "Maximum: highest buffer and highest capital requirement.",
};
const DEMO_PO_STORAGE_KEY = "skubase_demo_saved_purchase_orders";
type ReceiptDraftLine = { qty: string; cost: string };
type ReceiptDraft = { receivedAt: string; lines: Record<string, ReceiptDraftLine> };
type ReceiptDrafts = Record<string, ReceiptDraft>;
type EditablePoDrafts = Record<string, EditablePoDraft>;

export default function PurchaseOrdersPage() {
  return (
    <GatedFeature
      capability="reorder_pos"
      title="Turn recommendations into purchase orders"
      description="Upgrade to Growth to create saved PO drafts, track partial receipts, and build supplier lead-time history."
    >
      <PurchaseOrdersContent />
    </GatedFeature>
  );
}

function PurchaseOrdersContent() {
  const { user } = useAuth();
  const [drafts, setDrafts] = useState<PurchaseOrderDraft[]>([]);
  const [calendar, setCalendar] = useState<BuyingCalendarResponse | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [serviceLevel, setServiceLevel] = useState(0.95);
  const [shippingCost, setShippingCost] = useState(35);
  const [search, setSearch] = useState("");
  const [quickView, setQuickView] = useState<"all" | "week" | "at-risk" | "high-value">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [busyPo, setBusyPo] = useState<string | null>(null);
  const [receivingPo, setReceivingPo] = useState<string | null>(null);
  const [receiptDrafts, setReceiptDrafts] = useState<ReceiptDrafts>({});
  const [editingPo, setEditingPo] = useState<string | null>(null);
  const [editDrafts, setEditDrafts] = useState<EditablePoDrafts>({});
  const [operationNotice, setOperationNotice] = useState<string | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [identityIssues, setIdentityIssues] = useState<IdentityIssue[]>([]);
  const [recovery, setRecovery] = useState<{ scope: string | null; entries: PendingReceipt[]; error: string | null }>({ scope: null, entries: [], error: null });
  const inFlightReceipts = useRef(new Set<string>());
  const demo = user.id === 0;
  const scope = demo ? "demo" : receiptScope(user.shop_id, user.id);
  const activeScope = useRef<string | null>(scope);
  activeScope.current = scope;
  const recoveryReady = demo || (recovery.scope === scope && !recovery.error);
  const pendingReceipts = recovery.scope === scope ? recovery.entries : [];

  useEffect(() => {
    activeScope.current = scope;
    function readRecovery() {
      if (demo) { setRecovery({ scope, entries: [], error: null }); return; }
      try { setRecovery({ scope, entries: listPendingReceipts(window.localStorage, scope), error: null }); }
      catch (error) { setRecovery({ scope, entries: [], error: errorMessage(error, "Saved receipt submissions could not be read in this browser.") }); }
    }
    readRecovery();
    window.addEventListener("storage", readRecovery);
    return () => { window.removeEventListener("storage", readRecovery); activeScope.current = null; };
  }, [scope, demo]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    Promise.all([
      fetchPurchaseOrders(serviceLevel, shippingCost, controller.signal),
      fetchBuyingCalendar(serviceLevel, shippingCost, 180, controller.signal),
    ])
      .then(([r, calendarResponse]) => {
        if (controller.signal.aborted) return;
        const nextDrafts = isDemoMode()
          ? mergeDemoSavedPurchaseOrders(r.drafts)
          : r.drafts;
        setDrafts(nextDrafts);
        setCalendar(calendarResponse);
        setIdentityIssues(r.identity_issues ?? calendarResponse.identity_issues ?? []);
        setTotal(sumPoTotals(nextDrafts));
        setOperationError(null);
      })
      .catch((e) => {
        if (controller.signal.aborted || isAbortError(e)) return;
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [serviceLevel, shippingCost]);

  const savedDrafts = drafts.filter(isSavedPurchaseOrder);
  const visibleSavedDrafts = filterPurchaseOrders(savedDrafts, search, quickView);
  const visibleDrafts = filterPurchaseOrders(drafts, search, quickView);
  const supplyPlan = buildSupplyPlan(visibleDrafts);
  const visibleCalendarEvents = filterBuyingCalendarEvents(calendar?.events ?? [], search);
  const calendarSummary = buildCalendarSummary(visibleCalendarEvents);

  const receiptRecovery = <ReceiptRecoveryPanel entries={pendingReceipts} error={recovery.scope === scope ? recovery.error : null} busyPo={busyPo}
    onRetry={entry => void submitReceipt(entry.po_id)} onCorrect={entry => void correctRejectedReceipt(entry)} onReview={poId => { setSearch(""); setQuickView("all"); setExpanded(poId); }} />;
  if (error) return <div className="page-stack">{receiptRecovery}<p className="page-error-copy">{error}</p>{operationError ? <p role="alert">{operationError}</p> : null}{operationNotice ? <p role="status">{operationNotice}</p> : null}</div>;

  return (
    <div className="po-page">
      {receiptRecovery}
      <IdentityReviewNotice issues={identityIssues} />
      <CashPlanCard serviceLevel={serviceLevel} shippingCost={shippingCost} />
      <div className="po-toolbar">
        <div className="po-service-level-control">
          <p className="muted small">Stockout protection target</p>
          <div className="segmented">
            {SERVICE_LEVELS.map((l) => (
              <button
                key={l}
                type="button"
                className={`segmented-btn${
                  serviceLevel === l ? " segmented-btn-active" : ""
                }`}
                onClick={() => {
                  setOperationNotice(null);
                  setServiceLevel(l);
                }}
              >
                {(l * 100).toFixed(1)}%
              </button>
            ))}
          </div>
          <p className="muted small">
            {SERVICE_LEVEL_COPY[serviceLevel]} {loading ? "Updating reorder plan..." : "Changes recalculate safety stock and recommended quantities."}
          </p>
        </div>
        <div className="po-total">
          <p className="muted small">Total capital required, incl. shipping</p>
          <p className="po-total-value">{currency(total)}</p>
          {total === null && !loading ? <p className="muted small">Add missing supplier unit costs to calculate the complete total.</p> : null}
          <button
            type="button"
            className="button button-secondary"
            style={{ marginTop: "8px" }}
            disabled={visibleDrafts.length === 0}
            onClick={() => void exportBuyPlanReport(visibleDrafts)}
          >
            Export full buy plan
          </button>
        </div>
      </div>
      <div className="po-shipping-control">
        <label className="field-label">
          <span>Estimated shipping / freight per PO</span>
          <input
            className="input-control"
            type="number"
            min="0"
            step="5"
            value={shippingCost}
            onChange={(event) => {
              const next = Number(event.target.value);
              setShippingCost(Number.isFinite(next) ? Math.max(next, 0) : 0);
            }}
          />
        </label>
        <p className="muted small">
          Used in reorder economics so Skubase avoids freight-heavy top-up orders
          that could create overstock.
        </p>
      </div>

      <section className="planning-preview-grid">
        <PlanningCard
          title="Buying Calendar"
          label={`Next ${calendar?.horizon_days ?? 180} days`}
          value={currency(calendar ? calendarSummary.totalCost : null)}
          note={`${calendarSummary.futureCount} future planned buy${calendarSummary.futureCount === 1 ? "" : "s"} and ${calendarSummary.dueNowCount} due this week`}
        />
        <PlanningCard
          title="Current PO Drafts"
          label="Recommended now"
          value={currency(loading ? null : supplyPlan.next90Value)}
          note={`${supplyPlan.next90Units} recommended units across ${visibleDrafts.length} draft${visibleDrafts.length === 1 ? "" : "s"}`}
        />
      </section>

      <BuyingCalendarPanel
        events={visibleCalendarEvents}
        loading={loading}
        horizonDays={calendar?.horizon_days ?? 180}
        totalCost={calendar ? calendarSummary.totalCost : null}
      />

      <section className="po-filter-panel">
        <label className="forecast-search">
          <span>Search</span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search product, SKU, or supplier"
          />
        </label>
        <div className="quick-filter-row">
          {[
            ["all", "All"],
            ["week", "Running out this week"],
            ["at-risk", "At risk"],
            ["high-value", "High value"],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={`quick-filter-chip${quickView === key ? " quick-filter-chip-active" : ""}`}
              onClick={() => setQuickView(key as typeof quickView)}
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      {operationNotice || operationError ? (
        <div className={`po-feedback${operationError ? " po-feedback-error" : ""}`} role="status">
          {operationError ?? operationNotice}
        </div>
      ) : null}

      {loading ? <p className="page-loading">Generating POs…</p> : null}

      <section className="po-saved-ledger">
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Saved PO ledger</p>
            <h2>Drafts and receipts you can come back to</h2>
            <p className="muted small">
              Saved purchase orders persist receipt history so partial shipments,
              remaining units, and supplier lead-time observations are not lost.
            </p>
          </div>
        </div>
        {visibleSavedDrafts.length > 0 ? (
          <div className="po-ledger-table-wrap">
            <table className="po-ledger-table">
              <thead>
                <tr>
                  <th>PO</th>
                  <th>Supplier</th>
                  <th>Status</th>
                  <th>Received</th>
                  <th>Remaining</th>
                  <th>Receipts</th>
                  <th>Expected</th>
                  <th>Total</th>
                  <th>Next step</th>
                </tr>
              </thead>
              <tbody>
                {visibleSavedDrafts.map((po) => {
                  const received = receivedUnits(po);
                  const ordered = orderedUnits(po);
                  const remaining = Math.max(ordered - received, 0);
                  const latestReceipt = latestReceiptDate(po);
                  const receiptCount = po.receipts?.length ?? 0;
                  return (
                    <tr key={`saved-${po.po_id}`}>
                      <td>
                        <strong>{po.po_id}</strong>
                        <span>{po.lines.length} line{po.lines.length === 1 ? "" : "s"}</span>
                      </td>
                      <td>{po.vendor}</td>
                      <td>
                        <span className={`po-status po-status-${po.status}`}>
                          {formatPoStatus(po.status)}
                        </span>
                      </td>
                      <td>{received} / {ordered}</td>
                      <td>{remaining}</td>
                      <td>
                        {receiptCount}
                        <span>{latestReceipt ? `Last ${latestReceipt}` : "No receipt dates"}</span>
                      </td>
                      <td>{po.expected_arrival_date}</td>
                      <td>{currency(financialValue(po, "total_cost", po.total_cost))}</td>
                      <td>
                        <div className="po-ledger-actions">
                          <button
                            type="button"
                            className="button button-ghost button-sm"
                            onClick={() => setExpanded(po.po_id)}
                          >
                            Open
                          </button>
                          {remaining > 0 ? (
                            <button
                              type="button"
                              className="button button-secondary button-sm"
                              onClick={() => {
                                setExpanded(po.po_id);
                                startPartialReceipt(po);
                              }}
                            >
                              Receive rest
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state empty-state-compact">
            <p className="empty-state-title">No saved PO drafts yet</p>
            <p className="empty-state-copy">
              Save a draft below to create a persistent PO record. Once saved,
              receipts will stay attached when you leave and come back.
            </p>
          </div>
        )}
      </section>

      {visibleDrafts.length === 0 && !loading ? (
        <div className="empty-state">
          <p className="empty-state-title">{drafts.length === 0 ? "No purchase order recommendations available" : "No PO drafts match"}</p>
          <p className="empty-state-copy">
            {drafts.length === 0
              ? "The current data and service level produced no purchase order recommendations. Check that sales history, inventory and lead times are complete before deciding no stock is needed."
              : "Clear search or quick filters to see more draft purchase orders."}
          </p>
        </div>
      ) : null}

      <div className="po-list">
        {visibleDrafts.map((po) => {
          const remainingUnits = remainingPurchaseOrderUnits(po);
          const hasAmbiguousReceipts = po.lines.some(line => remainingLineQuantity(line) > 0 && receiptLineNeedsIdentityReview(po.lines, line));
          const canReceiveUnits = po.lines.some(line => remainingLineQuantity(line) > 0 && !receiptLineNeedsIdentityReview(po.lines, line));
          const costsKnown = purchaseOrderCostsKnown(po);
          const receiptPending = pendingReceipts.some(entry => entry.po_id === po.po_id);
          const detailsId = `po-details-${encodeURIComponent(po.po_id)}`;
          return (
          <div key={po.po_id} className="po-card">
            <button
              type="button"
              className="po-card-head"
              aria-label={`Purchase order ${po.po_id} from ${po.vendor}`}
              aria-expanded={expanded === po.po_id}
              aria-controls={detailsId}
              onClick={() => setExpanded(expanded === po.po_id ? null : po.po_id)}
            >
              <span>
                <span className="po-card-vendor">{po.vendor}</span>
                <span className="po-card-meta">
                  {po.po_id} · {po.lines.length} line
                  {po.lines.length === 1 ? "" : "s"} · arrives ~
                  {po.expected_arrival_date}
                </span>
              </span>
              <span className="po-card-cost">
                <span className="po-card-total">{currency(financialValue(po, "total_cost", po.total_cost))}</span>
                <span className="po-card-meta">
                  {currency(financialValue(po, "subtotal_cost", po.subtotal_cost))} items + {currency(po.shipping_cost)} shipping
                </span>
                <span className={`po-status po-status-${po.status}`}>
                  {formatPoStatus(po.status)}
                </span>
                <span className={`po-source po-source-${po.source ?? "recommended"}`}>
                  {isSavedPurchaseOrder(po) ? "Saved record" : "Recommendation"}
                </span>
              </span>
            </button>
            <div id={detailsId} hidden={expanded !== po.po_id}>
            {expanded === po.po_id ? (
              <div className="po-card-body">
                {editingPo === po.po_id ? (
                  <PurchaseOrderEditForm
                    po={po}
                    draft={editDrafts[po.po_id] ?? toEditablePoDraft(po)}
                    busy={busyPo === po.po_id}
                    onUpdate={(patch) => updateEditDraft(po.po_id, patch)}
                    onLineUpdate={(index, patch) => updateEditLine(po.po_id, index, patch)}
                    onAddLine={() => addEditLine(po.po_id)}
                    onRemoveLine={(index) => removeEditLine(po.po_id, index)}
                    onSave={() => void saveEditedPo(po)}
                    onCancel={() => cancelEditingPo(po.po_id)}
                  />
                ) : (
                  <>
                    <p className="po-rationale">{po.rationale}</p>
                    {!isSavedPurchaseOrder(po) ? <p className="section-copy">Save this draft before recording a delivery.</p> : null}
                    {receiptPending ? <p className="sync-safety-note identity-review-note">A receipt is awaiting confirmation. Use “Retry same receipt” above before editing this PO or entering another delivery.</p> : null}
                    {hasAmbiguousReceipts ? <p className="sync-safety-note">Some remaining lines need SKU mapping review. Receipts for those lines are blocked so stock is not added to the wrong product. You can receive other uniquely matched lines; saved PO history and safe edits remain available.</p> : null}
                    {!costsKnown ? <p className="muted small">Supplier unit costs are missing. Edit this PO and enter the actual costs before saving, approving, or recording a shipment.</p> : null}
                    <table className="po-table">
                      <thead>
                        <tr>
                          <th>SKU</th>
                          <th>Qty</th>
                          <th>Received</th>
                          <th>Unit cost</th>
                          <th>Extended</th>
                        </tr>
                      </thead>
                      <tbody>
                        {po.lines.map((line, index) => (
                          <tr key={productRowKey(line, index)}>
                            <td>
                              <strong>{line.name}</strong>
                              <span className="po-line-sku">{line.sku_id}</span>
                              {receiptLineNeedsIdentityReview(po.lines, line) ? <small>SKU mapping needs review</small> : null}
                            </td>
                            <td>{line.qty}</td>
                            <td>
                              {line.received_qty ?? 0} / {line.qty}
                            </td>
                            <td>{currency(financialValue(line, "unit_cost", line.unit_cost))}</td>
                            <td>{currency(financialValue(line, "extended_cost", line.extended_cost))}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <div className="po-cost-breakdown">
                      <span>Subtotal {currency(financialValue(po, "subtotal_cost", po.subtotal_cost))}</span>
                      <span>Shipping {currency(po.shipping_cost)}</span>
                      <strong>Total {currency(financialValue(po, "total_cost", po.total_cost))}</strong>
                    </div>
                    {po.receipts?.length ? (
                      <div className="po-receipt-history">
                        <div className="section-heading section-heading-compact">
                          <div>
                            <p className="section-eyebrow">Receipt history</p>
                            <h3>Supplier delivery observations</h3>
                            <p className="muted small">
                              Receipt dates feed supplier on-time delivery, fill rate,
                              and lead-time history.
                            </p>
                          </div>
                        </div>
                        <table className="po-table">
                          <thead>
                            <tr>
                              <th>Receipt date</th>
                              <th>SKU</th>
                              <th>Qty received</th>
                              <th>Unit cost</th>
                              <th>Days to receipt</th>
                              <th>Expected</th>
                              <th>Timing</th>
                            </tr>
                          </thead>
                          <tbody>
                            {po.receipts.map((receipt) => (
                              <tr key={`${receipt.id}-${receipt.sku_id}`}>
                                <td>{formatReceiptDate(receipt.received_at)}</td>
                                <td>
                                  <strong>{lineNameForSku(po, receipt.sku_id)}</strong>
                                  <span className="po-line-sku">{receipt.sku_id}</span>
                                </td>
                                <td>{receipt.received_qty}</td>
                                <td>{currency(receipt.received_unit_cost)}</td>
                                <td>{formatDaysToReceipt(po.created_at, receipt.received_at)}</td>
                                <td>{receipt.expected_arrival_date || "Not set"}</td>
                                <td>{formatReceiptTiming(receipt.expected_arrival_date, receipt.received_at)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="po-receipt-empty">
                        <strong>No receipt dates recorded yet.</strong>
                        <span>
                          Record a receipt date when inventory arrives so supplier
                          on-time delivery and lead-time history can be measured.
                        </span>
                      </div>
                    )}
                  </>
                )}
                <div className="po-card-actions">
                  <button
                    type="button"
                    className="button button-secondary"
                    onClick={() => startEditingPo(po)}
                    disabled={!recoveryReady || receiptPending || busyPo === po.po_id || editingPo === po.po_id || po.status === "received" || po.status === "cancelled"}
                  >
                    Edit PO
                  </button>
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={() => void saveDraft(po)}
                    disabled={!recoveryReady || receiptPending || busyPo === po.po_id || editingPo === po.po_id || !costsKnown}
                  >
                    {busyPo === po.po_id ? "Saving..." : costsKnown ? "Save draft" : "Add unit costs first"}
                  </button>
                  <button
                    type="button"
                    className="button button-secondary"
                    onClick={() => void markStatus(po, "approved")}
                    disabled={!recoveryReady || receiptPending || busyPo === po.po_id || editingPo === po.po_id || po.status === "approved" || !costsKnown}
                  >
                    {busyPo === po.po_id ? "Approving..." : "Approve PO"}
                  </button>
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={() => {
                      sendPurchaseOrderToVendor(po);
                      setOperationNotice(`Email draft opened for ${po.po_id}. After sending it, use Mark as sent to update the PO.`);
                    }}
                    disabled={busyPo === po.po_id || editingPo === po.po_id || !costsKnown}
                  >
                    Open vendor email draft
                  </button>
                  <button
                    type="button"
                    className="button button-secondary"
                    onClick={() => void markStatus(po, "sent")}
                    disabled={!recoveryReady || receiptPending || busyPo === po.po_id || editingPo === po.po_id || !costsKnown || ["sent", "partially_received", "received", "cancelled"].includes(po.status)}
                    title="Use after you have sent the purchase order to the supplier."
                  >
                    Mark as sent
                  </button>
                  <button
                    type="button"
                    className="button button-ghost"
                    onClick={() => startPartialReceipt(po)}
                    disabled={!recoveryReady || receiptPending || !isSavedPurchaseOrder(po) || busyPo === po.po_id || editingPo === po.po_id || !canReceiveUnits || !costsKnown}
                    title={!canReceiveUnits ? hasAmbiguousReceipts ? "Review SKU mapping before receiving remaining lines." : "All units on this PO have already been received." : undefined}
                  >
                    Receive partial
                  </button>
                  <button
                    type="button"
                    className="button button-ghost"
                    onClick={() => void receiveAll(po)}
                    disabled={!recoveryReady || receiptPending || !isSavedPurchaseOrder(po) || busyPo === po.po_id || editingPo === po.po_id || !canReceiveUnits || hasAmbiguousReceipts || !costsKnown}
                    title={hasAmbiguousReceipts ? "Use partial receipt for uniquely matched lines, then review the remaining SKU mappings." : !canReceiveUnits ? "All units on this PO have already been received." : undefined}
                  >
                    {busyPo === po.po_id ? "Receiving..." : "Receive all"}
                  </button>
                  <button
                    type="button"
                    className="button button-ghost"
                    onClick={() => exportPurchaseOrderReport(po)}
                    disabled={editingPo === po.po_id}
                  >
                    Export styled Excel
                  </button>
                </div>
                {receivingPo === po.po_id && editingPo !== po.po_id && !receiptPending ? (
                  <div className="po-receipt-form">
                    <div className="section-heading">
                      <div>
                        <p className="section-eyebrow">Receiving</p>
                        <h3>Record shipment quantities</h3>
                        <p className="muted small">
                          Use the actual receipt date for this shipment. Partial
                          shipments can be recorded as separate receipt events.
                        </p>
                      </div>
                    </div>
                    <label className="field-label po-receipt-date-field">
                      <span>Receipt date</span>
                      <input
                        className="input-control"
                        type="date"
                        value={receiptDrafts[po.po_id]?.receivedAt ?? todayInputDate()}
                        onChange={(event) => updateReceiptDate(po.po_id, event.target.value)}
                      />
                      <small>
                        Used to calculate supplier on-time delivery and days to receipt.
                      </small>
                    </label>
                    <table className="po-table">
                      <thead>
                        <tr>
                          <th>SKU</th>
                          <th>Ordered</th>
                          <th>Already received</th>
                          <th>Qty to receive</th>
                          <th>Unit cost</th>
                        </tr>
                      </thead>
                      <tbody>
                        {po.lines.map((line, index) => {
                          const remainingQty = remainingLineQuantity(line);
                          const identityBlocked = receiptLineNeedsIdentityReview(po.lines, line);
                          const draftLine = receiptDrafts[po.po_id]?.lines[line.sku_id] ?? {
                            qty: String(remainingQty),
                            cost: editableUnitCost(line),
                          };
                          const safeDraftQty = identityBlocked ? "0" : clampReceiptInput(draftLine.qty, remainingQty);
                          return (
                            <tr key={productRowKey(line, index)}>
                              <td>{line.name}{identityBlocked ? <small>SKU {line.sku_id}: mapping review required</small> : null}</td>
                              <td>{line.qty}</td>
                              <td>{line.received_qty ?? 0}</td>
                              <td>
                                <input
                                  className="input-control"
                                  type="number"
                                  min="0"
                                  max={remainingQty}
                                  step="1"
                                  value={safeDraftQty}
                                  disabled={remainingQty === 0 || identityBlocked}
                                  onChange={(event) =>
                                    updateReceiptLine(po.po_id, line.sku_id, {
                                      qty: event.target.value,
                                    })
                                  }
                                />
                              </td>
                              <td>
                                <input
                                  className="input-control"
                                  type="number"
                                  min="0"
                                  step="0.01"
                                  value={draftLine.cost}
                                  disabled={identityBlocked}
                                  onChange={(event) =>
                                    updateReceiptLine(po.po_id, line.sku_id, {
                                      cost: event.target.value,
                                    })
                                  }
                                />
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                    <div className="button-row">
                      <button
                        type="button"
                        className="button button-primary"
                        onClick={() => void recordPartialReceipt(po)}
                        disabled={!recoveryReady || busyPo === po.po_id}
                      >
                        {busyPo === po.po_id ? "Recording..." : "Record receipt"}
                      </button>
                      <button
                        type="button"
                        className="button button-ghost"
                        onClick={() => setReceivingPo(null)}
                        disabled={busyPo === po.po_id}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
            </div>
          </div>
        );
        })}
      </div>
      <BuyListEmailCard />
    </div>
  );

  async function refresh() {
    const [r, calendarResponse] = await Promise.all([
      fetchPurchaseOrders(serviceLevel, shippingCost),
      fetchBuyingCalendar(serviceLevel, shippingCost, 180),
    ]);
    const nextDrafts = isDemoMode()
      ? mergeDemoSavedPurchaseOrders(r.drafts)
      : r.drafts;
    setDrafts(nextDrafts);
    setCalendar(calendarResponse);
    setIdentityIssues(r.identity_issues ?? calendarResponse.identity_issues ?? []);
    setTotal(sumPoTotals(nextDrafts));
  }

  async function saveDraft(po: PurchaseOrderDraft): Promise<boolean> {
    if (blockPendingReceipt(po.po_id)) return false;
    if (!requireRecordedCosts(po)) return false;
    setBusyPo(po.po_id);
    setOperationError(null);
    setOperationNotice(null);
    try {
      const response = await savePurchaseOrder(po);
      const savedPo = markSaved(response.po ?? po);
      persistDemoPurchaseOrder(savedPo);
      upsertDraft(savedPo);
      setOperationNotice(`Saved draft ${po.po_id}.`);
      if (!isDemoMode()) await refresh();
      return true;
    } catch (error) {
      setOperationError(errorMessage(error, "Could not save purchase order draft."));
      return false;
    } finally {
      setBusyPo(null);
    }
  }

  async function saveEditedPo(po: PurchaseOrderDraft) {
    const editedPo = buildEditedPo(po, editDrafts[po.po_id] ?? toEditablePoDraft(po));
    if (!editedPo) return;

    const saved = await saveDraft(editedPo);
    if (saved) {
      setEditingPo(null);
      setEditDrafts((current) => {
        const { [po.po_id]: _removed, ...rest } = current;
        return rest;
      });
    }
  }

  async function markStatus(po: PurchaseOrderDraft, status: PurchaseOrderDraft["status"]) {
    if (blockPendingReceipt(po.po_id)) return;
    if (!requireRecordedCosts(po)) return;
    setBusyPo(po.po_id);
    setOperationError(null);
    setOperationNotice(null);
    try {
      await savePurchaseOrder(po);
      const response = await updatePurchaseOrderStatus(po.po_id, status);
      const nextPo = markSaved(response.po ?? { ...po, status });
      persistDemoPurchaseOrder(nextPo);
      upsertDraft(nextPo);
      setOperationNotice(
        status === "sent"
          ? `Purchase order ${po.po_id} marked as sent to the supplier.`
          : `Purchase order ${po.po_id} marked ${formatPoStatus(status).toLowerCase()}.`
      );
      if (!isDemoMode()) await refresh();
    } catch (error) {
      setOperationError(errorMessage(error, `Could not mark purchase order ${formatPoStatus(status).toLowerCase()}.`));
    } finally {
      setBusyPo(null);
    }
  }

  function startPartialReceipt(po: PurchaseOrderDraft) {
    if (blockPendingReceipt(po.po_id)) return;
    if (!isSavedPurchaseOrder(po)) { setOperationError("Save this draft before recording a delivery."); return; }
    if (!requireRecordedCosts(po)) return;
    if (remainingPurchaseOrderUnits(po) > 0 && po.lines.every(line => remainingLineQuantity(line) <= 0 || receiptLineNeedsIdentityReview(po.lines, line))) {
      setOperationError("No uniquely matched lines remain to receive. Review SKU mappings before recording these receipts.");
      return;
    }
    if (remainingPurchaseOrderUnits(po) <= 0) {
      setOperationNotice(`Purchase order ${po.po_id} is already fully received.`);
      setOperationError(null);
      setReceivingPo(null);
      return;
    }
    setEditingPo(null);
    setReceivingPo(po.po_id);
    setReceiptDrafts((current) => {
      if (current[po.po_id]) return current;
      return {
        ...current,
        [po.po_id]: {
          receivedAt: todayInputDate(),
          lines: Object.fromEntries(
            po.lines.map((line) => [
              line.sku_id,
              { qty: receiptLineNeedsIdentityReview(po.lines, line) ? "0" : String(remainingLineQuantity(line)), cost: editableUnitCost(line) },
            ])
          ),
        },
      };
    });
  }

  function startEditingPo(po: PurchaseOrderDraft) {
    if (blockPendingReceipt(po.po_id)) return;
    setReceivingPo(null);
    setEditingPo(po.po_id);
    setEditDrafts((current) => ({
      ...current,
      [po.po_id]: current[po.po_id] ?? toEditablePoDraft(po),
    }));
  }

  function requireRecordedCosts(po: PurchaseOrderDraft): boolean {
    if (purchaseOrderCostsKnown(po)) return true;
    setOperationError("Enter an actual unit cost for every PO line before continuing.");
    setOperationNotice(null);
    setExpanded(po.po_id);
    startEditingPo(po);
    return false;
  }

  function cancelEditingPo(poId: string) {
    setEditingPo(null);
    setOperationError(null);
    setEditDrafts((current) => {
      const { [poId]: _removed, ...rest } = current;
      return rest;
    });
  }

  function updateEditDraft(poId: string, patch: Partial<EditablePoDraft>) {
    setEditDrafts((current) => ({
      ...current,
      [poId]: {
        ...(current[poId] ?? emptyEditablePoDraft()),
        ...patch,
      },
    }));
  }

  function updateEditLine(
    poId: string,
    index: number,
    patch: Partial<EditablePoLine>
  ) {
    setEditDrafts((current) => {
      const draft = current[poId] ?? emptyEditablePoDraft();
      return {
        ...current,
        [poId]: {
          ...draft,
          lines: draft.lines.map((line, lineIndex) =>
            lineIndex === index ? { ...line, ...patch } : line
          ),
        },
      };
    });
  }

  function addEditLine(poId: string) {
    setEditDrafts((current) => {
      const draft = current[poId] ?? emptyEditablePoDraft();
      return {
        ...current,
        [poId]: {
          ...draft,
          lines: [
            ...draft.lines,
            {
              sku_id: "",
              name: "",
              qty: "1",
              unit_cost: "",
              received_qty: 0,
            },
          ],
        },
      };
    });
  }

  function removeEditLine(poId: string, index: number) {
    setEditDrafts((current) => {
      const draft = current[poId] ?? emptyEditablePoDraft();
      return {
        ...current,
        [poId]: {
          ...draft,
          lines: draft.lines.filter((_line, lineIndex) => lineIndex !== index),
        },
      };
    });
  }

  function buildEditedPo(
    po: PurchaseOrderDraft,
    draft: EditablePoDraft
  ): PurchaseOrderDraft | null {
    const vendor = draft.vendor.trim();
    const expectedArrivalDate = draft.expected_arrival_date.trim();
    const rationale = draft.rationale.trim();
    const shipping = parseMoney(draft.shipping_cost);

    if (!vendor) {
      setOperationError("Supplier is required before saving the purchase order.");
      return null;
    }
    if (!expectedArrivalDate) {
      setOperationError("Expected arrival date is required before saving the purchase order.");
      return null;
    }
    if (shipping === null) {
      setOperationError("Shipping / freight must be a valid non-negative number.");
      return null;
    }

    const lines = draft.lines
      .map((line) => normalizeEditableLine(line))
      .filter((line): line is PurchaseOrderLine => Boolean(line));

    if (lines.length === 0 || lines.length !== draft.lines.length) {
      setOperationError("Every line needs a SKU, product, whole quantity of at least one (and no less than received), and an actual non-negative unit cost. Enter 0 only when the item has no cost.");
      return null;
    }

    if (new Set(lines.map((line) => line.sku_id)).size !== lines.length) {
      setOperationError("Each SKU may appear only once. Combine its quantities before saving.");
      return null;
    }

    const subtotal = lines.reduce((sum, line) => sum + line.extended_cost, 0);
    return {
      ...po,
      vendor,
      expected_arrival_date: expectedArrivalDate,
      rationale: rationale || "Manually edited purchase order.",
      lines,
      subtotal_cost: roundCurrency(subtotal),
      shipping_cost: shipping,
      total_cost: roundCurrency(subtotal + shipping),
      financial_values_known: true,
      financial_values: { subtotal_cost: roundCurrency(subtotal), total_cost: roundCurrency(subtotal + shipping) },
    };
  }

  function updateReceiptLine(
    poId: string,
    skuId: string,
    patch: Partial<ReceiptDraftLine>
  ) {
    setReceiptDrafts((current) => ({
      ...current,
      [poId]: {
        receivedAt: current[poId]?.receivedAt ?? todayInputDate(),
        lines: {
          ...current[poId]?.lines,
          [skuId]: {
            qty: current[poId]?.lines[skuId]?.qty ?? "",
            cost: current[poId]?.lines[skuId]?.cost ?? "",
            ...patch,
          },
        },
      },
    }));
  }

  function updateReceiptDate(poId: string, receivedAt: string) {
    setReceiptDrafts((current) => ({
      ...current,
      [poId]: {
        receivedAt,
        lines: current[poId]?.lines ?? {},
      },
    }));
  }

  function clearReceiptDraft(poId: string) {
    setReceiptDrafts((current) => {
      const rest = { ...current };
      delete rest[poId];
      return rest;
    });
  }

  async function recordPartialReceipt(po: PurchaseOrderDraft) {
    if (blockPendingReceipt(po.po_id)) return;
    if (!isSavedPurchaseOrder(po)) { setOperationError("Save this draft before recording a delivery."); return; }
    if (!requireRecordedCosts(po)) return;
    const draft = receiptDrafts[po.po_id];
    const receivedAt = receiptDateToIso(draft?.receivedAt ?? todayInputDate());
    if (remainingPurchaseOrderUnits(po) <= 0) {
      setOperationNotice(`Purchase order ${po.po_id} is already fully received.`);
      setOperationError(null);
      setReceivingPo(null);
      return;
    }
    const lines = po.lines
      .filter(line => !receiptLineNeedsIdentityReview(po.lines, line))
      .map((line) => {
        const receiptLine = draft?.lines[line.sku_id];
        const receivedQty = Number(receiptLine?.qty ?? 0);
        const receivedUnitCost = parseMoney(receiptLine?.cost ?? editableUnitCost(line));
        const remainingQty = remainingLineQuantity(line);
        return {
          sku_id: line.sku_id,
          received_qty: Number.isFinite(receivedQty)
            ? Math.min(Math.max(Math.round(receivedQty), 0), remainingQty)
            : 0,
          received_unit_cost: receivedUnitCost,
        };
      })
      .filter((line) => line.received_qty > 0);

    if (lines.length === 0) {
      setOperationNotice(null);
      setOperationError("Enter a quantity for at least one SKU with units still remaining.");
      return;
    }

    if (lines.some((line) => line.received_unit_cost === null)) {
      setOperationNotice(null);
      setOperationError("Enter the actual unit cost for each received item. Use 0 only for items with no cost.");
      return;
    }

    await submitReceipt(po.po_id, { lines, received_at: receivedAt }, po);
  }

  async function receiveAll(po: PurchaseOrderDraft) {
    if (blockPendingReceipt(po.po_id)) return;
    if (!isSavedPurchaseOrder(po)) { setOperationError("Save this draft before recording a delivery."); return; }
    if (!requireRecordedCosts(po)) return;
    if (po.lines.some(line => remainingLineQuantity(line) > 0 && receiptLineNeedsIdentityReview(po.lines, line))) {
      setOperationError("Review ambiguous SKU mappings before receiving all. Use partial receipt for uniquely matched lines.");
      return;
    }
    const lines = po.lines.map((line) => ({
      sku_id: line.sku_id,
      received_qty: remainingLineQuantity(line),
      received_unit_cost: financialValue(line, "unit_cost", line.unit_cost),
    })).filter((line) => line.received_qty > 0);
    if (lines.length === 0) {
      setOperationNotice(`Purchase order ${po.po_id} is already fully received.`);
      return;
    }
    await submitReceipt(po.po_id, { lines, received_at: new Date().toISOString() }, po);
  }

  function blockPendingReceipt(poId: string): boolean {
    if (demo) return false;
    try {
      if (!recoveryReady) throw new Error("Receipt recovery must finish loading before this PO can be changed.");
      if (readPendingReceipt(window.localStorage, scope, poId)) throw new Error("A receipt is awaiting confirmation for this PO. Resolve it using the saved receipt recovery controls before making another change.");
      return false;
    } catch (error) { setOperationError(errorMessage(error, "Receipt recovery could not be checked.")); return true; }
  }

  function reloadReceiptRecovery() {
    if (activeScope.current !== scope) return;
    setRecovery({ scope, entries: listPendingReceipts(window.localStorage, scope), error: null });
  }

  async function submitReceipt(poId: string, input?: ReceiptInput, currentPo?: PurchaseOrderDraft) {
    const lockKey = `${scope}${poId}`;
    if (inFlightReceipts.current.has(lockKey)) return;
    inFlightReceipts.current.add(lockKey);
    setBusyPo(poId); setOperationError(null); setOperationNotice(null);
    let record: PendingReceipt | null = null;
    try {
      if (demo) {
        if (!input || !currentPo) return;
        const nextPo = markSaved(applyReceiptToPo(currentPo, input.lines, input.received_at));
        persistDemoPurchaseOrder(nextPo); upsertDraft(nextPo); clearReceiptDraft(poId); setReceivingPo(null);
        setOperationNotice(`Sample receipt recorded: ${sumReceiptQty(input.lines)} units. No store inventory was changed.`);
        return;
      }
      if (!recoveryReady) throw new Error("Receipt recovery must finish loading before submitting a delivery.");
      record = await withReceiptLock(navigator.locks, scope, poId, () => {
        const pending = readPendingReceipt(window.localStorage, scope, poId);
        if (pending) return pending;
        if (!input) throw new Error("This receipt recovery record is no longer pending. Review the current PO history before entering another delivery.");
        return retainReceiptSubmission(window.localStorage, scope, poId, input);
      });
      reloadReceiptRecovery();
      if (record.rejection) throw new Error("This submission was rejected without recording received units. Use Correct rejected receipt before making changes.");
      if (activeScope.current !== scope) return;
      const response = await receivePurchaseOrder(poId, record.payload);
      if (!confirmedReceiptResponse(response, record)) throw new Error("The receipt result could not be verified. Retry the saved submission; do not enter this delivery again.");
      await withReceiptLock(navigator.locks, scope, poId, () => clearReceiptSubmission(window.localStorage, scope, record!));
      if (activeScope.current !== scope) return;
      upsertDraft(markSaved(response.po)); clearReceiptDraft(poId); setReceivingPo(null); reloadReceiptRecovery();
      const units = sumReceiptQty(record.payload.lines);
      setOperationNotice(response.replayed
        ? `Already recorded: ${units} units for ${poId}. No additional received units were counted by this retry.`
        : `Recorded ${units} received unit${units === 1 ? "" : "s"} for ${poId} on ${formatReceiptDate(record.payload.received_at)}.`);
      void refresh().catch(() => { if (activeScope.current === scope) setOperationError("The receipt is confirmed, but the latest purchase-order list could not be refreshed. Reload to check current totals."); });
    } catch (error) {
      if (record && error instanceof ReceiptSubmissionError && error.notAppliedRequestId === record.payload.request_id) {
        try { await withReceiptLock(navigator.locks, scope, poId, () => markReceiptRejected(window.localStorage, scope, record!, error.message)); reloadReceiptRecovery(); }
        catch { /* Keep the original frozen submission when recovery storage cannot be updated. */ }
      }
      if (activeScope.current === scope) setOperationError(errorMessage(error, "Receipt confirmation was interrupted. Retry the saved submission to check it safely."));
    } finally {
      inFlightReceipts.current.delete(lockKey);
      if (activeScope.current === scope) setBusyPo(null);
    }
  }

  async function correctRejectedReceipt(record: PendingReceipt) {
    if (inFlightReceipts.current.has(`${scope}${record.po_id}`)) return;
    try {
      await withReceiptLock(navigator.locks, scope, record.po_id, () => {
        const stored = readPendingReceipt(window.localStorage, scope, record.po_id);
        if (!stored?.rejection || stored.payload.request_id !== record.payload.request_id) throw new Error("This receipt is not confirmed as rejected. Retry the saved submission before changing it.");
        clearReceiptSubmission(window.localStorage, scope, stored);
      });
      if (activeScope.current !== scope) return;
      reloadReceiptRecovery(); clearReceiptDraft(record.po_id); setReceivingPo(null); setExpanded(record.po_id);
      setOperationError(null); setOperationNotice("The rejected submission was cleared. No receipt was recorded for it. Review the current PO and enter the corrected delivery.");
      await refresh();
    } catch (error) { setOperationError(errorMessage(error, "The receipt recovery record could not be cleared.")); }
  }

  function upsertDraft(nextPo: PurchaseOrderDraft) {
    setDrafts((current) => {
      const exists = current.some((draft) => draft.po_id === nextPo.po_id);
      const nextDrafts = exists
        ? current.map((draft) => (draft.po_id === nextPo.po_id ? nextPo : draft))
        : [nextPo, ...current];
      setTotal(sumPoTotals(nextDrafts));
      return nextDrafts;
    });
  }
}

function isSavedPurchaseOrder(po: PurchaseOrderDraft): boolean {
  return po.source === "saved" || po.status !== "draft" || receivedUnits(po) > 0;
}

function markSaved(po: PurchaseOrderDraft): PurchaseOrderDraft {
  return {
    ...po,
    source: "saved",
  };
}

function orderedUnits(po: PurchaseOrderDraft): number {
  return po.lines.reduce((sum, line) => sum + line.qty, 0);
}

function receivedUnits(po: PurchaseOrderDraft): number {
  return po.lines.reduce((sum, line) => sum + (line.received_qty ?? 0), 0);
}

function remainingLineQuantity(line: Pick<PurchaseOrderLine, "qty" | "received_qty">): number {
  return Math.max(line.qty - (line.received_qty ?? 0), 0);
}

function remainingPurchaseOrderUnits(po: PurchaseOrderDraft): number {
  return po.lines.reduce((sum, line) => sum + remainingLineQuantity(line), 0);
}

function clampReceiptInput(value: string, remainingQty: number): string {
  if (value.trim() === "") return value;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "0";
  return String(Math.min(Math.max(Math.round(parsed), 0), remainingQty));
}

function latestReceiptDate(po: PurchaseOrderDraft): string | null {
  const latest = po.receipts?.[0]?.received_at ?? po.received_at;
  return latest ? formatReceiptDate(latest) : null;
}

function lineNameForSku(po: PurchaseOrderDraft, skuId: string): string {
  return po.lines.find((line) => line.sku_id === skuId)?.name ?? skuId;
}

function todayInputDate(): string {
  return new Date().toISOString().slice(0, 10);
}

function receiptDateToIso(value: string): string {
  if (!value) return new Date().toISOString();
  const parsed = new Date(`${value}T12:00:00`);
  return Number.isNaN(parsed.getTime()) ? new Date().toISOString() : parsed.toISOString();
}

function formatReceiptDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Date unavailable";
  return parsed.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatReceiptTiming(expectedDate: string, receivedAt: string): string {
  const expected = parseDateOnly(expectedDate);
  const received = parseDateOnly(receivedAt);
  if (!expected || !received) return "Expected date unavailable";
  const diffDays = Math.round((received.getTime() - expected.getTime()) / 86_400_000);
  if (diffDays === 0) return "On expected date";
  if (diffDays < 0) return `${Math.abs(diffDays)} day${Math.abs(diffDays) === 1 ? "" : "s"} early`;
  return `${diffDays} day${diffDays === 1 ? "" : "s"} late`;
}

function formatDaysToReceipt(createdAt: string, receivedAt: string): string {
  const created = parseDateOnly(createdAt);
  const received = parseDateOnly(receivedAt);
  if (!created || !received) return "Unavailable";
  const diffDays = Math.max(0, Math.round((received.getTime() - created.getTime()) / 86_400_000));
  return `${diffDays} day${diffDays === 1 ? "" : "s"}`;
}

function parseDateOnly(value: string): Date | null {
  if (!value) return null;
  const datePart = value.includes("T") ? value.slice(0, 10) : value;
  const parsed = new Date(`${datePart}T12:00:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function mergeDemoSavedPurchaseOrders(drafts: PurchaseOrderDraft[]): PurchaseOrderDraft[] {
  const saved = loadDemoSavedPurchaseOrders();
  if (saved.length === 0) return drafts;
  const savedById = new Map(saved.map((po) => [po.po_id, po]));
  const merged = drafts.map((po) => savedById.get(po.po_id) ?? po);
  const generatedIds = new Set(merged.map((po) => po.po_id));
  const savedOnly = saved.filter((po) => !generatedIds.has(po.po_id));
  return [...savedOnly, ...merged];
}

function loadDemoSavedPurchaseOrders(): PurchaseOrderDraft[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(DEMO_PO_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isPurchaseOrderLike).map(markSaved);
  } catch {
    return [];
  }
}

function persistDemoPurchaseOrder(po: PurchaseOrderDraft): void {
  if (!isDemoMode() || typeof window === "undefined") return;
  const saved = loadDemoSavedPurchaseOrders();
  const nextPo = markSaved(po);
  const next = saved.some((draft) => draft.po_id === nextPo.po_id)
    ? saved.map((draft) => (draft.po_id === nextPo.po_id ? nextPo : draft))
    : [nextPo, ...saved];
  window.localStorage.setItem(DEMO_PO_STORAGE_KEY, JSON.stringify(next));
}

function isPurchaseOrderLike(value: unknown): value is PurchaseOrderDraft {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<PurchaseOrderDraft>;
  return (
    typeof candidate.po_id === "string" &&
    typeof candidate.vendor === "string" &&
    Array.isArray(candidate.lines)
  );
}

function PurchaseOrderEditForm({
  po,
  draft,
  busy,
  onUpdate,
  onLineUpdate,
  onAddLine,
  onRemoveLine,
  onSave,
  onCancel,
}: {
  po: PurchaseOrderDraft;
  draft: EditablePoDraft;
  busy: boolean;
  onUpdate: (patch: Partial<EditablePoDraft>) => void;
  onLineUpdate: (index: number, patch: Partial<EditablePoLine>) => void;
  onAddLine: () => void;
  onRemoveLine: (index: number) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  const preview = previewEditablePoTotals(draft);

  return (
    <div className="po-edit-form">
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">Edit purchase order</p>
          <h3>Adjust quantities, costs, freight, and line items</h3>
        </div>
      </div>
      <div className="po-edit-grid">
        <label className="field-label">
          <span>Supplier</span>
          <input
            className="input-control"
            value={draft.vendor}
            onChange={(event) => onUpdate({ vendor: event.target.value })}
          />
        </label>
        <label className="field-label">
          <span>Expected arrival</span>
          <input
            className="input-control"
            type="date"
            value={draft.expected_arrival_date}
            onChange={(event) => onUpdate({ expected_arrival_date: event.target.value })}
          />
        </label>
        <label className="field-label">
          <span>Shipping / freight</span>
          <input
            className="input-control"
            type="number"
            min="0"
            step="0.01"
            value={draft.shipping_cost}
            onChange={(event) => onUpdate({ shipping_cost: event.target.value })}
          />
        </label>
      </div>
      <label className="field-label">
        <span>Rationale / internal note</span>
        <textarea
          className="input-control po-edit-note"
          value={draft.rationale}
          onChange={(event) => onUpdate({ rationale: event.target.value })}
        />
      </label>
      <div className="po-edit-lines">
        <div className="po-edit-lines-head">
          <p className="section-eyebrow">Lines</p>
          <button type="button" className="button button-ghost" onClick={onAddLine}>
            Add line
          </button>
        </div>
        <div className="po-edit-line-list">
          {draft.lines.map((line, index) => {
            const qty = parseWholeNumber(line.qty);
            const unitCost = parseMoney(line.unit_cost);
            const extended =
              qty === null || unitCost === null ? null : roundCurrency(qty * unitCost);
            const minQty = line.received_qty ?? 0;
            return (
              <div className="po-edit-line-row" key={`${po.po_id}-${index}`}>
                <label className="field-label">
                  <span>SKU</span>
                  <input
                    className="input-control"
                    value={line.sku_id}
                    onChange={(event) => onLineUpdate(index, { sku_id: event.target.value })}
                  />
                </label>
                <label className="field-label po-edit-product-field">
                  <span>Product</span>
                  <input
                    className="input-control"
                    value={line.name}
                    onChange={(event) => onLineUpdate(index, { name: event.target.value })}
                  />
                </label>
                <label className="field-label">
                  <span>Qty</span>
                  <input
                    className="input-control"
                    type="number"
                    min={minQty}
                    step="1"
                    value={line.qty}
                    onChange={(event) => onLineUpdate(index, { qty: event.target.value })}
                  />
                </label>
                <label className="field-label">
                  <span>Unit cost</span>
                  <input
                    className="input-control"
                    type="number"
                    min="0"
                    step="0.01"
                    value={line.unit_cost}
                    placeholder="Enter actual cost"
                    required
                    onChange={(event) => onLineUpdate(index, { unit_cost: event.target.value })}
                  />
                </label>
                <div className="po-edit-extended">
                  <span>Extended</span>
                  <strong>{currency(extended)}</strong>
                  {minQty > 0 ? <small>{minQty} already received</small> : null}
                </div>
                <button
                  type="button"
                  className="button button-ghost po-line-remove"
                  onClick={() => onRemoveLine(index)}
                  disabled={draft.lines.length === 1 || minQty > 0}
                  title={minQty > 0 ? "Received lines cannot be removed" : undefined}
                >
                  Remove
                </button>
              </div>
            );
          })}
        </div>
      </div>
      <div className="po-edit-summary">
        <span>Subtotal {currency(preview.subtotal)}</span>
        <span>Shipping {currency(preview.shipping)}</span>
        <strong>Total {currency(preview.total)}</strong>
      </div>
      <div className="button-row">
        <button
          type="button"
          className="button button-primary"
          onClick={onSave}
          disabled={busy}
        >
          {busy ? "Saving..." : "Save changes"}
        </button>
        <button
          type="button"
          className="button button-ghost"
          onClick={onCancel}
          disabled={busy}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function BuyingCalendarPanel({
  events,
  loading,
  horizonDays,
  totalCost,
}: {
  events: BuyingCalendarEvent[];
  loading: boolean;
  horizonDays: number;
  totalCost: number | null;
}) {
  const previewEvents = events.slice(0, 8);
  return (
    <section className="buying-calendar-panel">
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">Buying calendar</p>
          <h2>Future POs by order date</h2>
          <p className="muted small">
            Planned buys are projected from reorder-point timing across the next {horizonDays} days.
            Open saved POs stay visible until they are received or cancelled.
          </p>
        </div>
        <div className="buying-calendar-total">
          <span>Total planned cost</span>
          <strong>{currency(totalCost)}</strong>
        </div>
      </div>
      {loading ? (
        <p className="page-loading">Building buying calendar...</p>
      ) : previewEvents.length > 0 ? (
        <div className="buying-calendar-table-wrap">
          <table className="buying-calendar-table">
            <thead>
              <tr>
                <th>Buy by</th>
                <th>Supplier</th>
                <th>Status</th>
                <th>Arrives</th>
                <th>Lines</th>
                <th>Units</th>
                <th>Cost</th>
                <th>Why</th>
              </tr>
            </thead>
            <tbody>
              {previewEvents.map((event) => (
                <tr key={event.event_id}>
                  <td>
                    <strong>{formatCalendarDate(event.order_by_date)}</strong>
                    <span>{formatOrderTiming(event)}</span>
                  </td>
                  <td>{event.vendor}</td>
                  <td>
                    <span className={`buying-calendar-status buying-calendar-status-${event.urgency}`}>
                      {formatCalendarStatus(event)}
                    </span>
                    <span>{event.source === "saved" ? formatPoStatus(event.status as PurchaseOrderDraft["status"]) : "planned"}</span>
                  </td>
                  <td>{formatCalendarDate(event.expected_arrival_date)}</td>
                  <td>
                    <strong>{event.line_count}</strong>
                    <span>{formatCalendarLinePreview(event)}</span>
                  </td>
                  <td>{event.total_units}</td>
                  <td>{currency(financialValue(event, "estimated_cost", event.estimated_cost))}</td>
                  <td>{event.rationale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state empty-state-compact">
          <p className="empty-state-title">No planned buys in this horizon</p>
          <p className="empty-state-copy">
            The current data produced no planned buys for the selected window. Check sales-history coverage, current stock and lead times; an empty calendar does not confirm that no purchases are needed.
          </p>
        </div>
      )}
      {!loading && events.length > previewEvents.length ? (
        <p className="muted small">
          Showing the next {previewEvents.length} calendar events. Use search to narrow by supplier,
          product, or SKU.
        </p>
      ) : null}
    </section>
  );
}

function PlanningCard({
  title,
  label,
  value,
  note,
}: {
  title: string;
  label: string;
  value: string;
  note: string;
}) {
  return (
    <article className="planning-card">
      <span>{title}</span>
      <p>{label}</p>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}

function filterPurchaseOrders(
  drafts: PurchaseOrderDraft[],
  search: string,
  quickView: "all" | "week" | "at-risk" | "high-value",
): PurchaseOrderDraft[] {
  const needle = search.trim().toLowerCase();
  return drafts.filter((po) => {
    if (
      needle &&
      ![
        po.vendor,
        po.po_id,
        po.rationale,
        ...po.lines.flatMap((line) => [line.name, line.sku_id]),
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle)
    ) {
      return false;
    }
    const rationale = po.rationale.toLowerCase();
    if (quickView === "week") {
      return rationale.includes("critical") || rationale.includes("urgent") || rationale.includes("stockout");
    }
    if (quickView === "at-risk") {
      return po.lines.length > 0;
    }
    if (quickView === "high-value") {
      const value = financialValue(po, "total_cost", po.total_cost);
      return value !== null && value >= 3000;
    }
    return true;
  });
}

function filterBuyingCalendarEvents(
  events: BuyingCalendarEvent[],
  search: string,
): BuyingCalendarEvent[] {
  const needle = search.trim().toLowerCase();
  if (!needle) return events;
  return events.filter((event) =>
    [
      event.vendor,
      event.status,
      event.rationale,
      ...event.lines.flatMap((line) => [line.name, line.sku_id]),
    ]
      .join(" ")
      .toLowerCase()
      .includes(needle)
  );
}

function buildCalendarSummary(events: BuyingCalendarEvent[]): {
  totalCost: number | null;
  dueNowCount: number;
  futureCount: number;
} {
  return {
    totalCost: financialTotal(events.map((event) => financialValue(event, "estimated_cost", event.estimated_cost))),
    dueNowCount: events.filter((event) => event.urgency === "due_now" || event.urgency === "this_week").length,
    futureCount: events.filter((event) => event.urgency === "future").length,
  };
}

function formatCalendarDate(value: string): string {
  const parsed = parseDateOnly(value);
  if (!parsed) return "Date unavailable";
  return parsed.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function formatOrderTiming(event: BuyingCalendarEvent): string {
  if (event.urgency === "open") {
    if (event.days_until_order < 0) {
      const daysAgo = Math.abs(event.days_until_order);
      return `Ordered ${daysAgo} day${daysAgo === 1 ? "" : "s"} ago`;
    }
    return "Open PO";
  }
  if (event.days_until_order <= 0) return "Order now";
  if (event.days_until_order === 1) return "Tomorrow";
  return `${event.days_until_order} days out`;
}

function formatCalendarStatus(event: BuyingCalendarEvent): string {
  if (event.urgency === "open") return "Open PO";
  if (event.urgency === "due_now") return "Due now";
  if (event.urgency === "this_week") return "This week";
  return "Future";
}

function formatCalendarLinePreview(event: BuyingCalendarEvent): string {
  const names = event.lines.slice(0, 2).map((line) => line.name);
  if (event.lines.length > 2) {
    names.push(`+${event.lines.length - 2} more`);
  }
  return names.join(", ");
}

function buildSupplyPlan(drafts: PurchaseOrderDraft[]): {
  next90Units: number;
  next90Value: number | null;
} {
  const next90Units = drafts.reduce(
    (sum, po) => sum + po.lines.reduce((lineSum, line) => lineSum + line.qty, 0),
    0,
  );
  const next90Value = sumPoTotals(drafts);
  return {
    next90Units,
    next90Value,
  };
}

function toEditablePoDraft(po: PurchaseOrderDraft): EditablePoDraft {
  return {
    vendor: po.vendor,
    expected_arrival_date: po.expected_arrival_date,
    shipping_cost: String(po.shipping_cost ?? 0),
    rationale: po.rationale,
    lines: po.lines.map((line) => ({
      sku_id: line.sku_id,
      name: line.name,
      qty: String(line.qty),
      unit_cost: editableUnitCost(line),
      received_qty: line.received_qty ?? 0,
    })),
  };
}

function emptyEditablePoDraft(): EditablePoDraft {
  return {
    vendor: "",
    expected_arrival_date: "",
    shipping_cost: "0",
    rationale: "",
    lines: [],
  };
}

type ReceiptLinePayload = {
  sku_id: string;
  received_qty: number;
  received_unit_cost?: number | null;
};

function applyReceiptToPo(
  po: PurchaseOrderDraft,
  receiptLines: ReceiptLinePayload[],
  receivedAt: string
): PurchaseOrderDraft {
  const receivedBySku = new Map(receiptLines.map((line) => [line.sku_id, line.received_qty]));
  const lines = po.lines.map((line) => {
    const receiptQty = receivedBySku.get(line.sku_id) ?? 0;
    return {
      ...line,
      received_qty: Math.min(line.qty, (line.received_qty ?? 0) + receiptQty),
    };
  });
  const fullyReceived = lines.every((line) => line.received_qty >= line.qty);
  const anyReceived = lines.some((line) => line.received_qty > 0);
  const receiptEvents = receiptLines
    .filter((line) => line.received_qty > 0)
    .map((receiptLine, index) => {
      const originalLine = po.lines.find((line) => line.sku_id === receiptLine.sku_id);
      return {
        id: `${po.po_id}-${Date.now()}-${index}`,
        sku_id: receiptLine.sku_id,
        ordered_qty: originalLine?.qty ?? receiptLine.received_qty,
        received_qty: receiptLine.received_qty,
        ordered_unit_cost: originalLine?.unit_cost ?? receiptLine.received_unit_cost ?? 0,
        received_unit_cost: receiptLine.received_unit_cost ?? originalLine?.unit_cost ?? 0,
        expected_arrival_date: po.expected_arrival_date,
        received_at: receivedAt,
        created_at: new Date().toISOString(),
      };
    });
  return {
    ...po,
    lines,
    status: fullyReceived ? "received" : anyReceived ? "partially_received" : po.status,
    received_at: anyReceived ? receivedAt : po.received_at,
    receipts: [...receiptEvents, ...(po.receipts ?? [])],
  };
}

function sumReceiptQty(lines: ReceiptLinePayload[]): number {
  return lines.reduce((sum, line) => sum + line.received_qty, 0);
}

function isDemoMode(): boolean {
  return isDemoActive();
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function formatPoStatus(status: PurchaseOrderDraft["status"]): string {
  return status.replace(/_/g, " ");
}

function isAbortError(error: unknown): boolean {
  return (
    error instanceof DOMException && error.name === "AbortError"
  ) || (
    error instanceof Error &&
    (error.name === "AbortError" || error.message.toLowerCase().includes("aborted"))
  );
}

function sendPurchaseOrderToVendor(po: PurchaseOrderDraft): void {
  const subject = encodeURIComponent(`${po.po_id} purchase order`);
  const body = encodeURIComponent(
    [
      `Purchase order ${po.po_id}`,
      `Supplier: ${po.vendor}`,
      `Expected arrival: ${po.expected_arrival_date}`,
      `Subtotal: ${currency(financialValue(po, "subtotal_cost", po.subtotal_cost))}`,
      `Shipping/freight: ${currency(po.shipping_cost)}`,
      `Total: ${currency(financialValue(po, "total_cost", po.total_cost))}`,
      "",
      "Lines:",
      ...po.lines.map(
        (line) =>
          `- ${line.name}: ${line.qty} units @ ${currency(financialValue(line, "unit_cost", line.unit_cost))} = ${currency(
            financialValue(line, "extended_cost", line.extended_cost)
          )}`
      ),
      "",
      po.rationale,
    ].join("\n")
  );

  window.location.href = `mailto:?subject=${subject}&body=${body}`;
}
