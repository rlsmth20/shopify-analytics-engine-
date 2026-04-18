"use client";

import { useEffect, useState } from "react";

import { SHOPIFY_DOMAIN_STORAGE_KEY } from "@/lib/app-helpers";

export function useStoredShopDomain() {
  const [shopifyDomain, setShopifyDomain] = useState("");
  const [hasHydrated, setHasHydrated] = useState(false);

  useEffect(() => {
    const storedValue = window.localStorage.getItem(SHOPIFY_DOMAIN_STORAGE_KEY);
    if (storedValue) {
      setShopifyDomain(storedValue);
    }
    setHasHydrated(true);
  }, []);

  useEffect(() => {
    if (!hasHydrated) {
      return;
    }

    const normalizedDomain = shopifyDomain.trim();
    if (!normalizedDomain) {
      window.localStorage.removeItem(SHOPIFY_DOMAIN_STORAGE_KEY);
      return;
    }

    window.localStorage.setItem(SHOPIFY_DOMAIN_STORAGE_KEY, normalizedDomain);
  }, [hasHydrated, shopifyDomain]);

  return {
    shopifyDomain,
    setShopifyDomain,
    hasHydrated
  };
}
