"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
const API_BASE = APP_API_BASE_URL;
const SHOPIFY_CLIENT_ID =
  process.env.NEXT_PUBLIC_SHOPIFY_CLIENT_ID || "2df2104b538d6705dcb0fdce43d0a0b9";
const EMBEDDED_CONTEXT_KEY = "skubase_shopify_embedded_context";
const AUTH_TIMEOUT_MS = 15_000;
let appBridgeLoading: Promise<void> | null = null;

function withAuthTimeout<T>(operation: Promise<T>, message: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(message)), AUTH_TIMEOUT_MS);
    operation.then(resolve, reject).finally(() => clearTimeout(timer));
  });
}

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
  const embeddedParam = params.get("embedded") === "1";
  const stored = readStoredEmbeddedContext();

  // A regular top-level browser tab is never embedded, even when ?shop=/?host=
  // linger in the URL (e.g. after a redirect out of Shopify admin) or a stale
  // context sits in sessionStorage from an earlier embedded visit. Treating
  // those tabs as embedded routed cookie-authenticated users down the App
  // Bridge path, where requests 401 and imports fail.
  if (!isFramed() && !embeddedParam) {
    return null;
  }

  if (shop || host || stored?.shop) {
    const context = { shop: shop ?? stored?.shop ?? "", host: host ?? stored?.host ?? null };
    try {
      sessionStorage.setItem(EMBEDDED_CONTEXT_KEY, JSON.stringify(context));
    } catch {
      // Storage is best-effort; the current URL still carries context.
    }
    debugEmbedded("embedded context detected", {
      hasShop: Boolean(shop),
      hasHost: Boolean(host),
      embeddedParam,
    });
    return context;
  }

  return stored ?? { shop: "", host: null };
}

function isFramed(): boolean {
  try {
    return window.top !== window.self;
  } catch {
    // Cross-origin access to window.top throws — which itself means we are framed.
    return true;
  }
}

export function isEmbeddedShopifyContext(): boolean {
  return getEmbeddedShopifyContext() !== null;
}

export function isDemoActive(): boolean {
  // Demo (sample-workspace) mode never applies inside the Shopify admin
  // iframe — embedded merchants must always see their own store, and a
  // stray demo flag would silently swap their data for fixtures.
  if (typeof window === "undefined") return false;
  if (isEmbeddedShopifyContext()) return false;
  try {
    return (
      sessionStorage.getItem("skubase_demo") === "1" ||
      new URLSearchParams(window.location.search).get("demo") === "1"
    );
  } catch {
    return false;
  }
}

export async function getShopifySessionToken(): Promise<string | null> {
  const context = getEmbeddedShopifyContext();
  if (!context) return null;
  await ensureShopifyAppBridge();
  if (!window.shopify?.idToken) {
    throw new Error("Shopify authentication is unavailable. Reopen skubase from Shopify Admin.");
  }
  const token = await withAuthTimeout(
    window.shopify.idToken(),
    "Shopify authentication took too long. Please try again.",
  );
  if (!token) throw new Error("Shopify did not return a session. Please try again.");
  return token;
}

export async function authHeaders(headers?: HeadersInit): Promise<Headers> {
  const merged = new Headers(headers);
  const token = await getShopifySessionToken();
  if (token) {
    merged.set("Authorization", `Bearer ${token}`);
    debugEmbedded("attached Shopify bearer token to API request", {
      hasAuthorization: true,
    });
  }
  return merged;
}

export async function authenticatedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const embedded = getEmbeddedShopifyContext() !== null;
  const method = (init.method || (typeof Request !== "undefined" && input instanceof Request ? input.method : "GET")).toUpperCase();
  const readOnly = method === "GET" || method === "HEAD";
  const callerSignal = init.signal || (typeof Request !== "undefined" && input instanceof Request ? input.signal : undefined);
  const deadline = readOnly ? AbortSignal.timeout(30_000) : undefined;
  const request = {
    ...init,
    cache: "no-store" as const,
    signal: deadline ? (callerSignal ? AbortSignal.any([callerSignal, deadline]) : deadline) : callerSignal,
    headers: await authHeaders(init.headers),
    credentials: embedded ? "omit" as const : init.credentials ?? "include",
  };
  const response = await fetch(input, request);
  // Only retry the read-only authentication handshake. No sync or other write
  // is replayed automatically, and a second rejection is surfaced to the UI.
  if (embedded && String(input).endsWith("/auth/me") && response.status === 401 &&
      response.headers.get("X-Shopify-Retry-Invalid-Session-Request") === "1") {
    return fetch(input, { ...request, headers: await authHeaders(init.headers) });
  }
  return response;
}

export function redirectTopLevel(url: string): void {
  // Shopify-hosted pages (billing confirmation, OAuth) refuse to render
  // inside the app iframe, so navigation must escape to the top window.
  try {
    if (window.top && window.top !== window.self) {
      window.top.location.href = url;
      return;
    }
  } catch {
    // Cross-origin top — fall through to same-window navigation.
  }
  window.location.href = url;
}

export async function reconnectShopify(shopDomain?: string): Promise<void> {
  const context = getEmbeddedShopifyContext();
  const shop = shopDomain || context?.shop;
  if (!shop) throw new Error("Reopen skubase from your Shopify Admin to connect this store.");
  const params = new URLSearchParams({ shop, format: "json" });
  if (context?.host) params.set("host", context.host);
  // Request JSON using the authenticated flow; navigating directly to this
  // endpoint can show raw JSON when the browser has a website session cookie.
  const response = await authenticatedFetch(`${API_BASE}/integrations/shopify/install?${params}`, {
    signal: AbortSignal.timeout(AUTH_TIMEOUT_MS),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok || typeof body?.authorize_url !== "string") {
    throw new Error(typeof body?.detail === "string" ? body.detail : "Could not reconnect Shopify. Please try again.");
  }
  redirectTopLevel(body.authorize_url);
}

export function redirectToShopifyInstall(): boolean {
  const context = getEmbeddedShopifyContext();
  if (!context?.shop) return false;
  const params = new URLSearchParams({ shop: context.shop });
  if (context.host) params.set("host", context.host);
  redirectTopLevel(`${API_BASE}/integrations/shopify/install?${params}`);
  return true;
}

async function ensureShopifyAppBridge(): Promise<void> {
  if (typeof window === "undefined" || window.shopify?.idToken) return;
  ensureApiKeyMeta();
  if (!appBridgeLoading) {
    appBridgeLoading = withAuthTimeout(loadAppBridgeScript(), "Could not load Shopify authentication. Please try again.")
      .catch((error) => {
        document.querySelector('script[src="https://cdn.shopify.com/shopifycloud/app-bridge.js"]')?.remove();
        appBridgeLoading = null;
        throw error;
      });
  }
  await appBridgeLoading;
  debugEmbedded("Shopify App Bridge script ready", {
    hasIdToken: Boolean(window.shopify?.idToken),
  });
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

function readStoredEmbeddedContext(): EmbeddedContext | null {
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

function debugEmbedded(message: string, meta?: Record<string, unknown>): void {
  if (process.env.NODE_ENV !== "development") return;
  // Never log the session token itself. These breadcrumbs only show the auth path.
  console.debug(`[skubase embedded] ${message}`, meta ?? {});
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
    script.dataset.skubaseAppBridge = "true";
    // Shopify's CDN loader rejects async/defer, even for recovery loads.
    script.async = false;
    script.onload = () => {
      script.dataset.loaded = "true";
      resolve();
    };
    script.onerror = () => reject(new Error("Could not load Shopify App Bridge."));
    document.head.appendChild(script);
  });
}
