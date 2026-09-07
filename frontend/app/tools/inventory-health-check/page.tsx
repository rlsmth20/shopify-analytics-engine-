import { MarketingNav } from "@/components/marketing-nav";
import { MarketingFooter } from "@/components/marketing-footer";
import { InventoryHealthChecker } from "@/components/inventory-health-checker";

export const metadata = {
  title: "Free Shopify inventory health check — no install required",
  description: "Check stockout risk, reorder triggers and excess stock from a SKU summary. A free inventory diagnostic that runs in your browser; no account or app installation needed.",
  alternates: { canonical: "/tools/inventory-health-check" },
};

export default function InventoryHealthCheckPage() {
  return <div className="marketing-shell"><MarketingNav /><article className="blog-article" style={{ maxWidth: 1180 }}>
    <p className="blog-article-meta">Free inventory tool · No account required</p>
    <h1 className="blog-article-title">Which inventory needs your attention?</h1>
    <p>Find products that may run short, need a reorder review, or sit above your stock target. Start with a SKU summary and see the calculations behind each priority.</p>
    <InventoryHealthChecker />
    <h2 className="blog-article-h2">What this check calculates</h2>
    <p><strong>Daily sales</strong> = units sold ÷ days in the sales period. <strong>Days of cover</strong> = on-hand units ÷ daily sales. <strong>Reorder trigger</strong> = daily sales × supplier lead time + safety stock, rounded up.</p>
    <p>Above-target stock compares on-hand units with the daily-sales estimate over your chosen cover period, plus safety stock. Multiplying those units by a supplied unit cost gives a cost-based value to review. It is not a promise of recoverable cash.</p>
    <h2 className="blog-article-h2">Use the result as a review list</h2>
    <p>This simple diagnostic uses the period you supply. It does not forecast seasonality, correct for stockout-censored sales, check incoming orders or account for reserved units, bundles, minimum order quantities or changes in demand. Compare the results with your current orders and operating context before making a purchasing decision. No recorded sales alone do not establish dead stock.</p>
    <p>Skubase is an inventory-planning app for Shopify merchants. It is currently in Shopify&apos;s review process and is not yet listed in the Shopify App Store. This free tool works independently of app installation.</p>
  </article><MarketingFooter /></div>;
}
