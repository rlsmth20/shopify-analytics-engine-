/** Database identity is for UI state; merchant-facing SKU text stays unchanged. */
export type ProductIdentity = {
  product_id?: number | null;
  identity_ambiguous?: boolean;
  identity_warning?: string | null;
};

export type IdentityIssue = {
  product_id: number;
  sku_id: string;
  name: string;
  current_on_hand: number;
  message: string;
};

export function productRowKey(row: ProductIdentity & { sku_id: string }, fallbackIndex?: number): string {
  return Number.isSafeInteger(row.product_id) && Number(row.product_id) > 0
    ? `product:${row.product_id}`
    : `sku:${row.sku_id}${fallbackIndex === undefined ? "" : `:row:${fallbackIndex}`}`;
}

export const IDENTITY_REVIEW_MESSAGE = "More than one product uses this SKU. Review the source product mapping and give distinct variants unique SKUs, then sync again before planning purchases.";

export function uniqueSkuProduct<T extends ProductIdentity & { sku_id: string }>(products: T[], skuId: string): T | undefined {
  const matches = products.filter(product => product.sku_id === skuId);
  return matches.length === 1 && !matches[0].identity_ambiguous ? matches[0] : undefined;
}

export function skuNeedsIdentityReview(products: (ProductIdentity & { sku_id: string })[], skuId: string): boolean {
  const matches = products.filter(product => product.sku_id === skuId);
  return matches.length > 1 || matches.some(product => product.identity_ambiguous);
}

export function receiptLineNeedsIdentityReview(lines: (ProductIdentity & { sku_id: string })[], line: ProductIdentity & { sku_id: string }): boolean {
  // The existing receipt endpoint accepts a raw SKU alias, not a product ID.
  return line.identity_ambiguous === true || lines.filter(candidate => candidate.sku_id === line.sku_id).length > 1;
}
