"use client";

import { useEffect, useState } from "react";

import {
  fetchLatestShopifySyncStatus,
  type LatestShopifySyncStatusResponse
} from "@/lib/api";

export function useSyncStatus(shopifyDomain: string) {
  const [latestSyncStatus, setLatestSyncStatus] =
    useState<LatestShopifySyncStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function loadLatestSyncStatus(domainOverride?: string) {
    const normalizedDomain = (domainOverride ?? shopifyDomain).trim();
    if (!normalizedDomain) {
      setLatestSyncStatus(null);
      setErrorMessage(null);
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const status = await fetchLatestShopifySyncStatus(normalizedDomain);
      setLatestSyncStatus(status);
    } catch (error) {
      setLatestSyncStatus(null);
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "The latest sync status could not be loaded."
      );
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (!shopifyDomain.trim()) {
      setLatestSyncStatus(null);
      setErrorMessage(null);
      return;
    }

    void loadLatestSyncStatus(shopifyDomain);
  }, [shopifyDomain]);

  return {
    latestSyncStatus,
    isLoadingSyncStatus: isLoading,
    syncStatusError: errorMessage,
    reloadLatestSyncStatus: loadLatestSyncStatus
  };
}
