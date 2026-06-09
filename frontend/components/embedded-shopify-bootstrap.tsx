"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import { authenticatedFetch, getEmbeddedShopifyContext } from "@/lib/shopify-embedded";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

const API_BASE = APP_API_BASE_URL;

export function EmbeddedShopifyBootstrap() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const context = getEmbeddedShopifyContext();
    if (!context) return;

    void authenticatedFetch(`${API_BASE}/auth/me`, {
      credentials: "include",
      cache: "no-store",
    }).catch(() => {
      // AuthGuard handles install redirects for protected pages. This call exists
      // to initialize App Bridge session-token auth as soon as Shopify opens us.
    });

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
