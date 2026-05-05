"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, fetchInventoryActions, type ActionDataSource, type InventoryAction } from "@/lib/api";
import { buildActionErrorMessage } from "@/lib/app-helpers";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export function useActionFeed() {
  const router = useRouter();
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

      if (error instanceof ApiError && error.status === 401) {
        const sessionState = await verifySession(signal);

        if (sessionState === "expired") {
          router.replace("/login");
          return;
        }

        setErrorStatus(error.status);
        setErrorMessage(
          "The action feed rejected the request, but your dashboard session is still active. Refresh the page or try again in a moment."
        );
        return;
      }

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

async function verifySession(signal?: AbortSignal): Promise<"active" | "expired" | "unknown"> {
  try {
    const response = await fetch(`${API_BASE}/auth/me`, {
      cache: "no-store",
      credentials: "include",
      signal
    });

    return response.ok ? "active" : "expired";
  } catch {
    return signal?.aborted ? "unknown" : "active";
  }
}
