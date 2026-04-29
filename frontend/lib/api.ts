export type ActionableStatus = "urgent" | "optimize" | "dead";
export type UrgencyLevel = "critical" | "high" | "medium";
export type ActionDataSource = "db" | "mock";
export type DataQualityConfidence = "high" | "medium" | "low";
export type ShopifySyncStatus = "running" | "succeeded" | "failed";
export type LeadTimeSource =
  | "sku_override"
  | "vendor"
  | "category"
  | "global_default";
export type ProcessedCounts = {
  processed: number;
  inserted: number;
  updated: number;
  skipped: number;
};

export type ShopifyIngestionRequest = {
  shopify_domain: string;
  access_token: string;
};

export type ShopifyIngestionResponse = {
  shops: ProcessedCounts;
  products: ProcessedCounts;
  inventory_rows: ProcessedCounts;
  order_line_items: ProcessedCounts;
};

export type ShopifySyncRun = {
  id: number;
  shop_id: number;
  started_at: string;
  finished_at: string | null;
  status: ShopifySyncStatus;
  error_message: string | null;
  products_count: number;
  inventory_rows_count: number;
  order_line_items_count: number;
};

export type LatestShopifySyncStatusResponse = {
  shop_id: number | null;
  shopify_domain: string;
  latest_run: ShopifySyncRun | null;
};

export type ShopSettingsResponse = {
  shop_id: number | null;
  shopify_domain: string;
  global_default_lead_time_days: number;
  global_safety_buffer_days: number;
  allow_mock_fallback: boolean;
  is_persisted: boolean;
};

export type UpdateShopSettingsRequest = {
  shopify_domain: string;
  global_default_lead_time_days: number;
  global_safety_buffer_days: number;
  allow_mock_fallback: boolean;
};

export type VendorLeadTimeEntry = {
  vendor: string;
  lead_time_days: number;
};

export type CategoryLeadTimeEntry = {
  category: string;
  lead_time_days: number;
};

export type VendorLeadTimeSettingsResponse = {
  shop_id: number | null;
  shopify_domain: string;
  items: VendorLeadTimeEntry[];
};

export type CategoryLeadTimeSettingsResponse = {
  shop_id: number | null;
  shopify_domain: string;
  items: CategoryLeadTimeEntry[];
};

export type UpdateVendorLeadTimesRequest = {
  shopify_domain: string;
  items: VendorLeadTimeEntry[];
};

export type UpdateCategoryLeadTimesRequest = {
  shopify_domain: string;
  items: CategoryLeadTimeEntry[];
};

type BaseInventoryAction = {
  sku_id: string;
  name: string;
  status: ActionableStatus;
  recommended_action: string;
  explanation: string | null;
  days_of_inventory: number;
  lead_time_days_used: number;
  safety_buffer_days: number;
  lead_time_source: LeadTimeSource;
  target_coverage_days: number;
  priority_score: number;
  data_quality_confidence: DataQualityConfidence;
  data_quality_warnings: string[];
};

export type UrgentInventoryAction = BaseInventoryAction & {
  status: "urgent";
  urgency_level: UrgencyLevel;
  days_until_stockout: number;
  estimated_profit_impact: number;
};

export type OptimizeInventoryAction = BaseInventoryAction & {
  status: "optimize";
  excess_units: number;
  cash_tied_up: number;
};

export type DeadInventoryAction = BaseInventoryAction & {
  status: "dead";
  excess_units: number;
  cash_tied_up: number;
};

export type InventoryAction =
  | UrgentInventoryAction
  | OptimizeInventoryAction
  | DeadInventoryAction;

export type ActionFeedResponse = {
  data_source: ActionDataSource;
  actions: InventoryAction[];
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function isDemo(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return (
      sessionStorage.getItem("skubase_demo") === "1" ||
      new URLSearchParams(window.location.search).get("demo") === "1"
    );
  } catch {
    return false;
  }
}

export async function fetchInventoryActions(
  signal?: AbortSignal
): Promise<ActionFeedResponse> {
  if (isDemo()) {
    const { DEMO_ACTION_FEED } = await import("@/lib/demo-data");
    return DEMO_ACTION_FEED as ActionFeedResponse;
  }
  const response = await fetch(`${API_BASE_URL}/actions`, {
    method: "GET",
    headers: {
      Accept: "application/json"
    },
    cache: "no-store",
    signal
  });

  if (!response.ok) {
    throw new ApiError(
      (await readApiError(response)) ??
        `Action feed request failed with status ${response.status}.`,
      response.status
    );
  }

  return (await response.json()) as ActionFeedResponse;
}

export async function triggerShopifyIngestion(
  payload: ShopifyIngestionRequest,
  signal?: AbortSignal
): Promise<ShopifyIngestionResponse> {
  const response = await fetch(`${API_BASE_URL}/integrations/shopify/ingest`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload),
    cache: "no-store",
    signal
  });

  if (!response.ok) {
    throw new ApiError(
      (await readApiError(response)) ??
        `Shopify ingestion failed with status ${response.status}.`,
      response.status
    );
  }

  return (await response.json()) as ShopifyIngestionResponse;
}

export async function fetchShopSettings(
  _shopifyDomain: string,
  signal?: AbortSignal
): Promise<ShopSettingsResponse> {
  // Backend now derives the shop from the authenticated user's session.
  // The shopifyDomain argument is kept for backwards compatibility with
  // existing callers but is ignored.
  const response = await fetch(`${API_BASE_URL}/shop-settings`, {
    method: "GET",
    headers: {
      Accept: "application/json"
    },
    cache: "no-store",
    credentials: "include",
    signal
  });

  if (!response.ok) {
    throw new ApiError(
      (await readApiError(response)) ??
        `Shop settings request failed with status ${response.status}.`,
      response.status
    );
  }

  return (await response.json()) as ShopSettingsResponse;
}

export async function fetchLatestShopifySyncStatus(
  shopifyDomain: string,
  signal?: AbortSignal
): Promise<LatestShopifySyncStatusResponse> {
  const query = new URLSearchParams({ shopify_domain: shopifyDomain }).toString();
  const response = await fetch(
    `${API_BASE_URL}/integrations/shopify/sync-status?${query}`,
    {
      method: "GET",
      headers: {
        Accept: "application/json"
      },
      cache: "no-store",
      signal
    }
  );

  if (!response.ok) {
    throw new ApiError(
      (await readApiError(response)) ??
        `Shopify sync status request failed with status ${response.status}.`,
      response.status
    );
  }

  return (await response.json()) as LatestShopifySyncStatusResponse;
}

export async function saveShopSettings(
  payload: UpdateShopSettingsRequest,
  signal?: AbortSignal
): Promise<ShopSettingsResponse> {
  const response = await fetch(`${API_BASE_URL}/shop-settings`, {
    method: "PUT",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload),
    cache: "no-store",
    credentials: "include",
    signal
  });

  if (!response.ok) {
    throw new ApiError(
      (await readApiError(response)) ??
        `Shop settings save failed with status ${response.status}.`,
      response.status
    );
  }

  return (await response.json()) as ShopSettingsResponse;
}

export async function fetchVendorLeadTimes(
  _shopifyDomain: string,
  signal?: AbortSignal
): Promise<VendorLeadTimeSettingsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/shop-settings/vendor-lead-times`,
    {
      method: "GET",
      headers: {
        Accept: "application/json"
      },
      cache: "no-store",
      credentials: "include",
      signal
    }
  );

  if (!response.ok) {
    throw new ApiError(
      (await readApiError(response)) ??
        `Vendor lead times request failed with status ${response.status}.`,
      response.status
    );
  }

  return (await response.json()) as VendorLeadTimeSettingsResponse;
}

export async function saveVendorLeadTimes(
  payload: UpdateVendorLeadTimesRequest,
  signal?: AbortSignal
): Promise<VendorLeadTimeSettingsResponse> {
  const response = await fetch(`${API_BASE_URL}/shop-settings/vendor-lead-times`, {
    method: "PUT",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload),
    cache: "no-store",
    credentials: "include",
    signal
  });

  if (!response.ok) {
    throw new ApiError(
      (await readApiError(response)) ??
        `Vendor lead times save failed with status ${response.status}.`,
      response.status
    );
  }

  return (await response.json()) as VendorLeadTimeSettingsResponse;
}

export async function fetchCategoryLeadTimes(
  _shopifyDomain: string,
  signal?: AbortSignal
): Promise<CategoryLeadTimeSettingsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/shop-settings/category-lead-times`,
    {
      method: "GET",
      headers: {
        Accept: "application/json"
      },
      cache: "no-store",
      credentials: "include",
      signal
    }
  );

  if (!response.ok) {
    throw new ApiError(
      (await readApiError(response)) ??
        `Category lead times request failed with status ${response.status}.`,
      response.status
    );
  }

  return (await response.json()) as CategoryLeadTimeSettingsResponse;
}

export async function saveCategoryLeadTimes(
  payload: UpdateCategoryLeadTimesRequest,
  signal?: AbortSignal
): Promise<CategoryLeadTimeSettingsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/shop-settings/category-lead-times`,
    {
      method: "PUT",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload),
      cache: "no-store",
      credentials: "include",
      signal
    }
  );

  if (!response.ok) {
    throw new ApiError(
      (await readApiError(response)) ??
        `Category lead times save failed with status ${response.status}.`,
      response.status
    );
  }

  return (await response.json()) as CategoryLeadTimeSettingsResponse;
}

async function readApiError(response: Response): Promise<string | null> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
  } catch {
    return null;
  }

  return null;
}
