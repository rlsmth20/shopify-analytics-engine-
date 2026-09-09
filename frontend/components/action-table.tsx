"use client";

import { Fragment, useId, useState } from "react";
import { ActionCard } from "@/components/action-card";
import type { InventoryAction } from "@/lib/api";
import { actionTableMetrics } from "@/lib/action-presentation";
import { productRowKey } from "@/lib/product-identity";
import { confidenceLabel, currencyFormatter, numberFormatter, statusLabel } from "@/lib/app-helpers";
import styles from "./action-table.module.css";

function number(value: number | null, suffix = ""): string {
  return value === null ? "Unavailable" : `${numberFormatter.format(value)}${suffix}`;
}

export function ActionTable({ actions }: { actions: InventoryAction[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const tableId = useId();
  return (
    <div className={styles.wrapper}>
      <p className={styles.hint}>Compare the queue in the selected sort order. Expand a product to see its recommendation and stock projection.</p>
      <div className={styles.scroll} tabIndex={0} role="region" aria-label="Inventory action comparison">
        <table className={styles.table}>
          <caption>Inventory actions · stock and order quantities in units · monetary estimates in USD</caption>
          <thead><tr>
            <th scope="col">Product / priority</th>
            <th scope="col" className={styles.numeric}>On hand</th>
            <th scope="col" className={styles.numeric}>Stock coverage</th>
            <th scope="col" className={styles.numeric}>Order quantity</th>
            <th scope="col" className={styles.numeric}>Financial exposure</th>
            <th scope="col">Data confidence</th>
            <th scope="col">Recommendation</th>
          </tr></thead>
          <tbody>{actions.map((action, index) => {
            const metrics = actionTableMetrics(action);
            const key = `${action.status}-${productRowKey(action, index)}`;
            const open = expanded === key;
            const detailId = `${tableId}-${index}`;
            return <Fragment key={key}>
              <tr>
                <th scope="row" className={styles.product}>
                  <strong>{action.name}</strong>
                  <span className={styles.secondary}>SKU {action.sku_id}</span>
                  <span className={styles.statusLine}><span className={`pill pill-${action.status}`}>{metrics.identityReview ? "Review SKU mapping" : metrics.historyReview ? "Review history" : statusLabel[action.status]}</span><span className={styles.secondary}>Priority {number(metrics.priority)}</span></span>
                </th>
                <td data-label="On hand" className={styles.numeric}>{number(metrics.stock, " units")}</td>
                <td data-label="Stock coverage" className={styles.numeric}>
                  <strong>{metrics.identityReview ? "Needs mapping review" : metrics.historyReview ? "Needs history" : number(metrics.coverage, " days")}</strong>
                  <span className={styles.secondary}>Lead time: {number(metrics.leadTime, " days")}</span>
                  {metrics.runsOutBeforeDelivery ? <span className={styles.risk}>May run out before delivery</span> : null}
                </td>
                <td data-label="Order quantity" className={styles.numeric}>{metrics.reorderUnits === null ? action.status === "urgent" ? "Unavailable" : "—" : number(metrics.reorderUnits, " units")}<span className={styles.secondary}>{metrics.identityReview ? "Withheld until mapping review" : action.status === "urgent" ? "Suggested replenishment" : "No reorder suggested"}</span></td>
                <td data-label="Financial exposure" className={styles.numeric}>{metrics.impact === null ? "Not established" : currencyFormatter.format(metrics.impact)}<span className={styles.secondary}>{action.status === "urgent" ? "Estimated profit at risk" : "Capital tied up"}</span></td>
                <td data-label="Data confidence"><span className={action.data_quality_confidence === "low" ? styles.risk : undefined}>{confidenceLabel[action.data_quality_confidence]}</span>{action.data_quality_warnings.length > 0 ? <span className={styles.secondary}>{action.data_quality_warnings.length} {action.data_quality_warnings.length === 1 ? "warning" : "warnings"} in details</span> : null}</td>
                <td><button className={`button button-secondary ${styles.review}`} type="button" aria-expanded={open} aria-controls={detailId} aria-label={`${open ? "Hide" : "Review"} recommendation for ${action.name}`} onClick={() => setExpanded(open ? null : key)}>{open ? "Hide details" : "Review"}</button></td>
              </tr>
              <tr id={detailId} hidden={!open}><td colSpan={7} className={styles.expanded}>{open ? <ActionCard action={action} /> : null}</td></tr>
            </Fragment>;
          })}</tbody>
        </table>
      </div>
    </div>
  );
}
