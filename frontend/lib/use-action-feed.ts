"use client";

import { useEffect, useState } from "react";

import { ApiError, fetchInventoryActions, type ActionDataSource, type InventoryAction } from "@/lib/api";
import { buildActionErrorMessage } from "@/lib/app-helpers";

export function useActionFeed() {
  const [actions, setActions] = useState<InventoryAction[]>([]);
  const [dataSource, setDataSource] = useState<ActionDataSource | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);

  async function loadActions(signal?: AbortSignal) {
    setIsLoading(true);
    setErrorMessage(null);
    setErrorStatus(null);

    try {
      const response = await fetchInventoryActions(signal);
      setActions(response.actions);
      setDataSource(response.data_source);
    } catch (error) {
      if (signal?.aborted) {
        return;
      }

      setActions([]);
      setDataSource(null);
      setErrorStatus(error instanceof ApiError ? error.status : null);
      setErrorMessage(buildActionErrorMessage(error));
    } finally {
      if (!signal?.aborted) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    void loadActions(controller.signal);
    return () => controller.abort();
  }, []);

  return {
    actions,
    dataSource,
    isLoading,
    errorMessage,
    errorStatus,
    reloadActions: loadActions
  };
}
