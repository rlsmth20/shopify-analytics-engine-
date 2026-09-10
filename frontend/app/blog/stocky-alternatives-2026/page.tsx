import Link from "next/link";
import { MarketingNav } from "@/components/marketing-nav";
import { MarketingFooter } from "@/components/marketing-footer";

import { BLOG_POSTS } from "@/lib/blog-posts";
import { BlogArticleMeta } from "@/components/blog-article-meta";

const post = BLOG_POSTS["stocky-alternatives-2026"];

export const metadata = {
  title: `${post.title} - skubase`,
  description: post.description,
  alternates: { canonical: "/blog/stocky-alternatives-2026" },
  keywords: ["Stocky alternative", "Stocky shutdown", "Shopify Stocky end of life"],
  openGraph: { title: post.title, description: post.description, url: "/blog/stocky-alternatives-2026", type: "article" },
};

const ARTICLE_LD = {
  "@context": "https://schema.org",
  "@type": "Article",
  headline: post.title,
  datePublished: post.publishedAt,
  dateModified: post.updatedAt,
  author: { "@type": "Organization", name: "skubase" },
};

export default function StockyAlternativesPost() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <article className="blog-article">
        <BlogArticleMeta post={post} />
        <h1 className="blog-article-title">{post.title}</h1>
        <p className="blog-article-lead">
          Stocky stopped managing inventory on <strong>August 31, 2026</strong>. Shopify now directs merchants
          to its admin and POS inventory workflows, with read-only Stocky access for exports for at least 90 days
          after retirement. See <a href="https://help.shopify.com/en/manual/products/inventory/transitioning-from-stocky">Shopify&apos;s migration guidance</a> for current availability.
        </p>
        <p className="blog-article-meta">
          Prices and product availability checked September 9, 2026. Prices shown below are USD for monthly billing;
          follow the linked pricing pages for current tiers and terms.
        </p>

        <h2 className="blog-article-h2">Start with the workflows you used in Stocky</h2>
        <p>
          Shopify&apos;s <a href="https://help.shopify.com/en/manual/products/inventory/transitioning-from-stocky">built-in inventory workflows</a> cover
          purchase orders, transfers, quantity adjustments, and inventory history. Check those first, then identify
          any additional planning or reporting requirements. Shopify also offers Sidekick assistance with replenishment and draft purchase orders.
        </p>
        <p>
          Distinguish a tool that recommends what to buy from one that sends orders, receives stock, or updates
          quantities across channels. Your team may use a planning tool alongside Shopify or another operations system.
        </p>

        <h2 className="blog-article-h2">The replacements worth considering</h2>

        <h3 className="blog-article-h3">skubase</h3>
        <p>
          skubase provides forecasts, stockout risk, and a ranked daily action queue, with supplier scorecards and
          dead-stock recommendations available by plan. <Link href="/pricing">Monthly plans cost $29, $99, and $199</Link>,
          with a price-lock commitment in our <Link href="/terms">terms</Link>.
        </p>
        <p>
          Turn reorder recommendations into supplier-grouped purchase-order drafts, export them as Excel workbooks,
          and open a vendor email draft to share your order. Record receipts in Skubase to build supplier history.
          Shopify stock updates and physical receiving stay in your store or operations system. <Link href="/goodbye-stocky">See the migration details</Link>.
        </p>

        <h3 className="blog-article-h3">Inventory Planner (Sage)</h3>
        <p>
          Inventory Planner lists multi-location planning, replenishment, and buying budgets. Its <a href="https://www.inventory-planner.com/pricing/">pricing page</a> offers
          quotes based on inventory volume. <a href="https://www.brightpearl.com/brightpearl-history">Brightpearl acquired Inventory Planner in 2021</a>;
          <a href="https://www.sage.com/en-sg/news/press-releases/2022/01/sage-completes-acquisition-of-brightpearl-to-support-a-thriving-online-retail-sector/"> Sage acquired Brightpearl in January 2022</a>.
        </p>

        <h3 className="blog-article-h3">Prediko</h3>
        <p>
          Prediko lists demand forecasting, purchase-order management, and multiple stores and locations.
          Its <a href="https://www.prediko.io/pricing">monthly plans start at $49</a> for stores with less than
          $100,000 in revenue over the last 12 months. The pricing basis is total annual revenue recorded in Shopify,
          including online stores, POS, wholesale, and connected sales channels. Higher revenue tiers cost more;
          check your applicable tier and integrations before comparing costs.
        </p>

        <h3 className="blog-article-h3">Cin7 Core (DEAR)</h3>
        <p>
          Cin7 Core covers inventory, purchase orders, warehouse workflows, and accounting integrations.
          Review its <a href="https://www.cin7.com/pricing/">current plans and feature breakdown</a> for user,
          order, and integration allowances, plus forecasting add-ons. Ask for an implementation scope that
          reflects the workflows and records you need to move.
        </p>

        <h3 className="blog-article-h3">Sumtracker</h3>
        <p>
          Sumtracker separates inventory sync and stock management from its Replenish plan, which adds purchase
          orders, transfers, and forecasting. Its <a href="https://www.sumtracker.com/pricing">pricing page</a> scales
          plans by annual order volume. Compare the plan that includes your required workflows and check its
          channel and warehouse limits.
        </p>

        <h2 className="blog-article-h2">How to evaluate, in order</h2>
        <ol className="blog-article-ol">
          <li><strong>Save the records you need.</strong> Use the remaining read-only export window and keep historical files separate from the data your new tool accepts.</li>
          <li><strong>List your operational requirements.</strong> Include sales channels, locations, purchasing, receiving, and transfers.</li>
          <li><strong>Compare equivalent prices.</strong> Use the same billing cadence and your applicable revenue or order tier, including required add-ons.</li>
          <li><strong>Test the workflows.</strong> Check a sample of products, quantities, and recommendations before your team relies on them.</li>
          <li><strong>Confirm the setup scope.</strong> Ask what imports, training, support, and implementation fees are included. A demo requirement alone does not establish a setup timeline.</li>
        </ol>

        <h2 className="blog-article-h2">What to preserve after retirement</h2>
        <p>
          Shopify says historical purchase orders and stocktakes do not automatically move into Shopify, and
          suppliers cannot be exported from Stocky. Save the reports you need while read-only access remains
          available and record supplier details separately. Follow <a href="https://help.shopify.com/en/manual/products/inventory/transitioning-from-stocky">Shopify&apos;s current migration instructions</a>
          {" "}for the export window and supported workflows.
        </p>

        <h2 className="blog-article-h2">If skubase looks right</h2>
        <p>
          Start with a saved Stocky Inventory On Hand CSV to add catalog details and a stock snapshot to a CSV workspace.
          If Shopify is already connected or synced, its quantities remain authoritative; supported CSV costs and
          lead times enrich matching variants. Add non-Shopify shipment history through ShipStation for demand analysis.
          Keep old purchase orders, transfers, and supplier records in your migration archive.
        </p>

        <p>Skubase is in Shopify&apos;s review process and is not yet listed in the Shopify App Store.
          You can use a CSV workspace now, or <Link href="/tools/inventory-health-check">try the free inventory health check</Link> without installing an app.</p>

        <div className="blog-article-cta">
          <Link href="/login" className="button button-primary button-lg">Start free trial</Link>
          <Link href="/goodbye-stocky" className="button button-ghost button-lg">See migration details</Link>
        </div>
      </article>

      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ARTICLE_LD) }} />

      <MarketingFooter />
    </div>
  );
}
