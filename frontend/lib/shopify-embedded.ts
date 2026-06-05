"use client";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const SHOPIFY_CLIENT_ID = process.env.NEXT_PUBLIC_SHOPIFY_CLIENT_ID || "";
const EMBEDDED_CONTEXT_KEY = "skubase_shopify_embedded_context";

type EmbeddedContext = {
  shop: string;
  host: string | null;
};

type ShopifyGlobal = {
  idToken?: () => Promise<string>;
};

declare global {
  interface Window {
    shopify?: ShopifyGlobal;
  }
}

export function getEmbeddedShopifyContext(): EmbeddedContext | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  const shop = params.get("shop");
  const host = params.get("host");
  if (shop) {
    const context = { shop, host };
    try {
      sessionStorage.setItem(EMBEDDED_CONTEXT_KEY, JSON.stringify(context));
    } catch {
      // Storage is best-effort; the current URL still carries context.
    }
    return context;
  }

  if (window.top === window.self) {
    return null;
  }

  try {
    const raw = sessionStorage.getItem(EMBEDDED_CONTEXT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<EmbeddedContext>;
    return typeof parsed.shop === "string" && parsed.shop
      ? { shop: parsed.shop, host: typeof parsed.host === "string" ? parsed.host : null }
      : null;
  } catch {
    return null;
  }
}

export function isEmbeddedShopifyContext(): boolean {
  return getEmbeddedShopifyContext() !== null;
}

export async function getShopifySessionToken(): Promise<string | null> {
  const context = getEmbeddedShopifyContext();
  if (!context) return null;
  await ensureShopifyAppBridge();
  try {
    return (await window.shopify?.idToken?.()) || null;
  } catch {
    return null;
  }
}

export async function authHeaders(headers?: HeadersInit): Promise<Headers> {
  const merged = new Headers(headers);
  const token = await getShopifySessionToken();
  if (token) {
    merged.set("Authorization", `Bearer ${token}`);
  }
  return merged;
}

export async function authenticatedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  return fetch(input, {
    ...init,
    headers: await authHeaders(init.headers),
    credentials: init.credentials ?? "include",
  });
}

export function redirectToShopifyInstall(): boolean {
  const context = getEmbeddedShopifyContext();
  if (!context) return false;
  const params = new URLSearchParams({ shop: context.shop });
  if (context.host) params.set("host", context.host);
  const installUrl = `${API_BASE}/integrations/shopify/install?${params}`;

  try {
    if (window.top && window.top !== window.self) {
      window.top.location.href = installUrl;
    } else {
      window.location.href = installUrl;
    }
  } catch {
    window.location.href = installUrl;
  }
  return true;
}

async function ensureShopifyAppBridge(): Promise<void> {
  if (typeof window === "undefined" || window.shopify?.idToken) return;
  ensureApiKeyMeta();
  await loadAppBridgeScript();
}

function ensureApiKeyMeta(): void {
  if (!SHOPIFY_CLIENT_ID || document.querySelector('meta[name="shopify-api-key"]')) {
    return;
  }
  const meta = document.createElement("meta");
  meta.name = "shopify-api-key";
  meta.content = SHOPIFY_CLIENT_ID;
  document.head.appendChild(meta);
}

function loadAppBridgeScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      'script[src="https://cdn.shopify.com/shopifycloud/app-bridge.js"]',
    );
    if (existing) {
      if (existing.dataset.loaded === "true" || window.shopify?.idToken) {
        resolve();
        return;
      }
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("Could not load Shopify App Bridge.")), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.src = "https://cdn.shopify.com/shopifycloud/app-bridge.js";
    script.async = true;
    script.onload = () => {
      script.dataset.loaded = "true";
      resolve();
    };
    script.onerror = () => reject(new Error("Could not load Shopify App Bridge."));
    document.head.appendChild(script);
  });
}
