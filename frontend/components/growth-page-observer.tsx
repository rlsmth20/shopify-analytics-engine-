"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { trackGrowthEvent } from "@/lib/analytics";

export function GrowthPageObserver() {
  const pathname = usePathname();
  useEffect(() => {
    if (!pathname || pathname.startsWith("/growth")) return;
    void trackGrowthEvent("VISITOR");
    if (pathname === "/pricing" || pathname === "/billing") void trackGrowthEvent("PRICING_VIEWED");
  }, [pathname]);
  return null;
}
