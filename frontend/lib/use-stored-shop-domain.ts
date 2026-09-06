"use client";

import { useEffect, useState } from "react";

import { SHOPIFY_DOMAIN_STORAGE_KEY } from "@/lib/app-helpers";

export function useStoredShopDomain() {
  const [shopifyDomain, setShopifyDomain] = useState("");
  const [hasHydrated, setHasHydrated] = useState(false);

  useEffect(() => {
    try {
      const storedValue = window.localStorage.getItem(SHOPIFY_DOMAIN_STORAGE_KEY);
      if (storedValue) setShopifyDomain(storedValue);
    } catch {
      // Storage is optional in embedded/incognito sessions. The settings API
      // resolves the authenticated workspace even without a remembered domain.
    }
    setHasHydrated(true);
  }, []);

  useEffect(() => {
    if (!hasHydrated) {
      return;
    }

    try {
      const normalizedDomain = shopifyDomain.trim();
      if (!normalizedDomain) {
        window.localStorage.removeItem(SHOPIFY_DOMAIN_STORAGE_KEY);
        return;
      }
      window.localStorage.setItem(SHOPIFY_DOMAIN_STORAGE_KEY, normalizedDomain);
    } catch {
      // A blocked preference write must not prevent loading or saving rules.
    }
  }, [hasHydrated, shopifyDomain]);

  return {
    shopifyDomain,
    setShopifyDomain,
    hasHydrated
  };
}
