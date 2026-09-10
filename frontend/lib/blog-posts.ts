// Keep article previews, metadata and review dates together.
export const BLOG_POSTS = {
  "stocky-alternatives-2026": {
    title: "Stocky alternatives for Shopify merchants in 2026",
    description: "Stocky has retired. Compare Shopify's built-in workflows, inventory planning apps, and a practical path to your next purchase order.",
    publishedAt: "2026-04-25", updatedAt: "2026-09-09", category: "Migration",
  },
  "inventory-planner-alternative": {
    title: "Inventory Planner alternatives in 2026",
    description: "Compare Shopify inventory planning options, current pricing sources, purchase-order workflows, and the data you need to switch.",
    publishedAt: "2026-04-29", updatedAt: "2026-09-09", category: "Comparison",
  },
  "shopify-safety-stock-formula": {
    title: "How to calculate safety stock for your Shopify store",
    description: "A worked safety-stock and reorder-point example, with practical steps for using demand and supplier lead-time data.",
    publishedAt: "2026-04-29", updatedAt: "2026-09-09", category: "Forecasting",
  },
  "why-six-month-moving-average-overstocks-you": {
    title: "When a six-month inventory average leads to overstock",
    description: "Separate your sales-history window from your stock target, then use lead times and demand changes to review what to reorder.",
    publishedAt: "2026-04-25", updatedAt: "2026-09-09", category: "Forecasting",
  },
  "how-to-clear-dead-stock-shopify": {
    title: "How to clear dead stock on Shopify: markdown, bundle, wholesale, or write-off",
    description: "Compare four ways to handle slow inventory using net recovery, carrying costs, and the next realistic selling opportunity.",
    publishedAt: "2026-04-29", updatedAt: "2026-09-09", category: "Inventory planning",
  },
} as const;

export function blogDate(date: string): string {
  return new Date(`${date}T12:00:00Z`).toLocaleDateString("en-US", {
    month: "long", day: "numeric", year: "numeric", timeZone: "UTC",
  });
}
