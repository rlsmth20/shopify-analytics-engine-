import Link from "next/link";
import { productRowKey, type IdentityIssue } from "@/lib/product-identity";

export function IdentityReviewNotice({ issues }: { issues?: IdentityIssue[] }) {
  if (!issues?.length) return null;
  return <aside className="sync-safety-note identity-review-note" aria-label="Product mapping needs review" style={{ minWidth: 0, overflowWrap: "anywhere" }}>
    <strong>{issues.length} {issues.length === 1 ? "product needs" : "products need"} mapping review</strong>
    <p className="section-copy">These products share a SKU or cannot be matched safely. Forecasts and recommendations for these products are withheld. Give distinct source variants unique SKUs and sync again.</p>
    <ul className="section-copy">{issues.slice(0, 5).map((issue, index) => <li key={productRowKey(issue, index)}><strong>{issue.name}</strong> · SKU {issue.sku_id}</li>)}</ul>
    {issues.length > 5 ? <p className="section-copy">{issues.length - 5} more products also need review.</p> : null}
    <Link className="button button-secondary" href="/store-sync">Review source data & sync</Link>
    <p className="section-copy">If an older import seems to duplicate a current product, <a href="mailto:info@skubase.io?subject=Product%20mapping%20help">contact Skubase for help reviewing the mapping</a>.</p>
  </aside>;
}
