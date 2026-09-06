"use client";

import { getEmbeddedShopifyContext } from "@/lib/shopify-embedded";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

export function EmbeddedShopifyBootstrap() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const context = getEmbeddedShopifyContext();
    if (!context) return;

    if (pathname === "/") {
      const params = new URLSearchParams(searchParams.toString());
      params.set("embedded", "1");
      if (context.shop && !params.get("shop")) params.set("shop", context.shop);
      if (context.host && !params.get("host")) params.set("host", context.host);
      router.replace(`/dashboard?${params.toString()}`);
    }
  }, [pathname, router, searchParams]);

  return null;
}
