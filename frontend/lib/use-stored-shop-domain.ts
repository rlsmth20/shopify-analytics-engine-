"use client";

import { useEffect, useState } from "react";

import { SHOPIFY_DOMAIN_STORAGE_KEY } from "@/lib/app-helpers";
import { useAuth } from "@/components/auth-guard";
import { workspaceStorageKey } from "@/lib/browser-session";

export function useStoredShopDomain() {
  const { user } = useAuth();
  const storageKey = workspaceStorageKey(SHOPIFY_DOMAIN_STORAGE_KEY, user);
  const [shopifyDomain, setShopifyDomain] = useState("");
  const [hydratedKey, setHydratedKey] = useState<string | null>(null);
  const hasHydrated = hydratedKey === storageKey;

  useEffect(() => {
    try {
      const storedValue = window.localStorage.getItem(storageKey);
      setShopifyDomain(storedValue || "");
    } catch {
      setShopifyDomain("");
      // Storage is optional in embedded/incognito sessions. The settings API
      // resolves the authenticated workspace even without a remembered domain.
    }
    setHydratedKey(storageKey);
  }, [storageKey]);

  useEffect(() => {
    if (!hasHydrated) {
      return;
    }

    try {
      const normalizedDomain = shopifyDomain.trim();
      if (!normalizedDomain) {
        window.localStorage.removeItem(storageKey);
        return;
      }
      window.localStorage.setItem(storageKey, normalizedDomain);
    } catch {
      // A blocked preference write must not prevent loading or saving rules.
    }
  }, [hasHydrated, shopifyDomain, storageKey]);

  return {
    shopifyDomain,
    setShopifyDomain,
    hasHydrated
  };
}
