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

  async function loadLatestSyncStatus(
    domainOverride?: string,
    signal?: AbortSignal
  ) {
    const normalizedDomain = (domainOverride ?? shopifyDomain).trim();
    if (!normalizedDomain) {
      setLatestSyncStatus(null);
      setErrorMessage(null);
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const status = await fetchLatestShopifySyncStatus(normalizedDomain, signal);
      setLatestSyncStatus(status);
    } catch (error) {
      if (signal?.aborted) {
        return;
      }

      setLatestSyncStatus(null);
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "The latest sync status could not be loaded."
      );
    } finally {
      if (!signal?.aborted) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    if (!shopifyDomain.trim()) {
      setLatestSyncStatus(null);
      setErrorMessage(null);
      return;
    }

    const controller = new AbortController();
    void loadLatestSyncStatus(shopifyDomain, controller.signal);
    return () => controller.abort();
  }, [shopifyDomain]);

  return {
    latestSyncStatus,
    isLoadingSyncStatus: isLoading,
    syncStatusError: errorMessage,
    reloadLatestSyncStatus: loadLatestSyncStatus
  };
}
