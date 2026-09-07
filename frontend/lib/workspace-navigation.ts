import type { PlanTierKey } from "./plans";

export type NavItem = {
  href: string;
  label: string;
  section: "Command" | "Intelligence" | "Operations" | "Settings";
  icon: string;
  keywords: string;
  minTier?: PlanTierKey;
  searchOnly?: boolean;
  adminOnly?: boolean;
};

export const WORKSPACE_NAVIGATION: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", section: "Command", icon: "DB", keywords: "home overview start today" },
  { href: "/actions", label: "Action Queue", section: "Command", icon: "AQ", keywords: "what next priority urgent stockout low stock recommendations" },
  { href: "/alerts", label: "Alerts & notifications", section: "Command", icon: "AR", keywords: "email emails slack webhook notification notifications rules stockout low stock warning setup send enable pause" },
  { href: "/growth", label: "Growth dashboard", section: "Command", icon: "GR", keywords: "outreach marketing customers acquisition experiments leads campaign", adminOnly: true },
  { href: "/forecast", label: "Forecast", section: "Intelligence", icon: "FC", minTier: "growth", keywords: "predict prediction demand future stockout low stock sales" },
  { href: "/analytics", label: "Inventory health", section: "Intelligence", icon: "IH", keywords: "analytics charts abc xyz stock performance" },
  { href: "/reports", label: "Reports & exports", section: "Intelligence", icon: "RX", keywords: "download excel spreadsheet report csv schedule email" },
  { href: "/suppliers", label: "Suppliers", section: "Intelligence", icon: "SP", minTier: "scale", keywords: "vendor vendors supplier performance delivery late lead time scorecard" },
  { href: "/purchase-orders", label: "Purchase orders", section: "Operations", icon: "PO", minTier: "growth", keywords: "reorder replenish restock buy buying list po pos supplier suppliers order receipt receive received freight shipping weekly email digest schedule send" },
  { href: "/stocky-migration", label: "Stocky migration", section: "Operations", icon: "SM", keywords: "replace stocky setup checklist getting started" },
  { href: "/transfers", label: "Stock transfers", section: "Operations", icon: "TR", minTier: "scale", keywords: "move transfer locations warehouse rebalance" },
  { href: "/bundles", label: "Bundle opportunities", section: "Operations", icon: "BO", minTier: "growth", keywords: "bundle bundles cross sell pair co purchase" },
  { href: "/liquidation", label: "Dead stock recovery", section: "Operations", icon: "DS", keywords: "deadstock overstock slow moving clearance markdown recover cash liquidation" },
  { href: "/store-sync", label: "Connect & import", section: "Settings", icon: "SS", keywords: "shopify store sync connect connection reconnect import data upload csv refresh" },
  { href: "/import-stocky", label: "Import Stocky CSV", section: "Settings", icon: "CSV", keywords: "upload import csv stocky inventory file spreadsheet", searchOnly: true },
  { href: "/import-shipstation", label: "Import ShipStation CSV", section: "Settings", icon: "CSV", keywords: "upload import csv shipstation sales file spreadsheet", searchOnly: true },
  { href: "/lead-time-settings", label: "Lead times & stock rules", section: "Settings", icon: "IR", minTier: "growth", keywords: "lead time supplier vendor safety buffer coverage target inventory rule rules" },
  { href: "/billing", label: "Plan & billing", section: "Settings", icon: "BL", keywords: "price pricing payment card invoice subscription cancel upgrade plan" },
  { href: "/account", label: "Account", section: "Settings", icon: "AC", keywords: "workspace user profile team member preferences settings" },
  { href: "/privacy-requests", label: "Privacy requests", section: "Settings", icon: "PR", keywords: "delete customer personal data privacy export requests" },
  { href: "/feedback", label: "Help & feedback", section: "Settings", icon: "CF", keywords: "contact support help bug question problem feedback email" },
];

const normalize = (value: string) => value.toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
const fillerWords = new Set(["how", "do", "i", "a", "the", "to", "my", "in", "set", "up", "where", "can", "is"]);

export function findWorkspacePages(query: string, isAdmin: boolean): NavItem[] {
  const terms = normalize(query).split(/\s+/).filter(term => term && !fillerWords.has(term));
  return WORKSPACE_NAVIGATION.filter(item => {
    if (item.adminOnly && !isAdmin) return false;
    if (terms.length === 0) return !item.searchOnly;
    const text = normalize(`${item.label} ${item.keywords}`);
    return terms.every(term => text.includes(term));
  });
}

export function productDataPresent(summary: unknown): boolean | null {
  if (!summary || typeof summary !== "object" || !("product_count" in summary)) return null;
  const count = summary.product_count;
  return typeof count === "number" && Number.isSafeInteger(count) && count >= 0 ? count > 0 : null;
}
