import { MarketingNav } from "@/components/marketing-nav";
import { MarketingFooter } from "@/components/marketing-footer";
import { ReorderCalculator } from "@/components/reorder-calculator";

export const metadata = {
  title: "Free Shopify reorder point calculator",
  description: "Calculate when to reorder with daily sales, supplier lead time and safety stock. See the formula and inventory position before making a purchase decision.",
  alternates: { canonical: "/tools/reorder-point-calculator" },
};

export default function ReorderPointPage() {
  return <div className="marketing-shell"><MarketingNav /><article className="blog-article">
    <p className="blog-article-meta">Free inventory planning tool · No account required</p>
    <h1 className="blog-article-title">When should you reorder?</h1>
    <p>Use one SKU’s average daily demand, supplier lead time and safety stock to calculate a reorder point. Your entries stay in your browser.</p>
    <ReorderCalculator />
    <h2 className="blog-article-h2">The calculation</h2>
    <p><strong>Reorder point = average daily demand × lead time in days + safety stock.</strong> Round up to the next whole unit. Compare this threshold with inventory position: on-hand units plus confirmed incoming units, minus committed units that are not already deducted from on-hand stock.</p>
    <p>This is an ordering trigger, not an order quantity. Before purchasing, check the arrival dates of open orders, supplier minimums, upcoming promotions and changes in demand. A late incoming order may not cover demand in time.</p>
    <h2 className="blog-article-h2">Choose inputs you can explain</h2>
    <p>Use a representative demand period. Sales during stockouts can understate actual demand, while a promotion can overstate normal sales. Include handling and transit in lead time. Safety stock is an explicit buffer you choose here; this calculator does not infer a service level or predict seasonal demand.</p>
    <p>Skubase helps you examine inventory priorities across your Shopify store. The first step is a read-only analysis; you remain in control of purchasing decisions.</p>
  </article><MarketingFooter /></div>;
}
