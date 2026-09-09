"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import { useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { invalidateEntitlementsCache } from "@/lib/entitlements";
import { announceSessionChange, SESSION_CHANGED_KEY } from "@/lib/browser-session";

import {
  authenticatedFetch,
  getEmbeddedShopifyContext,
  redirectToShopifyInstall,
} from "@/lib/shopify-embedded";

const API_BASE = APP_API_BASE_URL;

export type AuthUser = {
  id: number;
  email: string;
  shop_id: number;
  is_admin: boolean;
  trial_ends_at: string | null;
  in_trial: boolean;
};

const DEMO_USER: AuthUser = {
  id: 0,
  email: "demo@skubase.io",
  shop_id: 0,
  is_admin: false,
  trial_ends_at: null,
  in_trial: true,
};

function detectDemo(): boolean {
  if (typeof window === "undefined") return false;
  const param = new URLSearchParams(window.location.search).get("demo") === "1";
  if (param) {
    try {
      sessionStorage.setItem("skubase_demo", "1");
    } catch {
      // ignore
    }
    return true;
  }
  try {
    return sessionStorage.getItem("skubase_demo") === "1";
  } catch {
    return false;
  }
}

type AuthContextValue = {
  user: AuthUser;
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthGuard>");
  }
  return ctx;
}

export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [isDemo, setIsDemo] = useState(false);
  const [isEmbedded, setIsEmbedded] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [needsInstall, setNeedsInstall] = useState(false);
  const requestGeneration = useRef(0);

  async function refresh() {
    const generation = ++requestGeneration.current;
    invalidateEntitlementsCache();
    setLoading(true);
    setIsDemo(false);
    setAuthError(null);
    setNeedsInstall(false);
    try {
      const res = await authenticatedFetch(`${API_BASE}/auth/me`, {
        credentials: "include",
        signal: AbortSignal.timeout(15_000),
      });
      if (generation !== requestGeneration.current) return;
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        if (generation !== requestGeneration.current) return;
        setNeedsInstall(res.status === 401 && body?.detail === "Shopify app is not installed for this shop.");
        setAuthError(res.status === 401 && !isEmbedded ? null : "We couldn't verify your session. Please try again.");
        setUser(null);
        return;
      }
      const data = (await res.json()) as AuthUser;
      if (!validAuthUser(data)) throw new Error("Invalid session response");
      if (generation !== requestGeneration.current) return;
      setUser(data);
      try { sessionStorage.removeItem("skubase_demo"); } catch { /* Optional storage. */ }
    } catch {
      if (generation !== requestGeneration.current) return;
      setAuthError("We couldn't reach Skubase. Check your connection and try again.");
      setUser(null);
    } finally {
      if (generation === requestGeneration.current) setLoading(false);
    }
  }

  async function logout() {
    ++requestGeneration.current;
    setLoading(true);
    invalidateEntitlementsCache();
    try {
      const response = await authenticatedFetch(`${API_BASE}/auth/logout`, {
        method: "POST",
        credentials: "include",
        signal: AbortSignal.timeout(15_000),
      });
      if (!response.ok) throw new Error("Sign out not confirmed");
    } catch {
      setAuthError("Sign-out couldn't be confirmed. Check your connection and try signing out again.");
      setLoading(false);
      return;
    }
    try {
      sessionStorage.removeItem("skubase_demo");
    } catch {
      // ignore
    }
    setUser(null);
    setIsDemo(false);
    setLoading(false);
    setAuthError(null);
    announceSessionChange();
    router.replace("/");
  }

  useEffect(() => {
    const generation = ++requestGeneration.current;
    invalidateEntitlementsCache();
    const demo = detectDemo();
    const embedded = getEmbeddedShopifyContext() !== null;
    setIsEmbedded(embedded);

    // An explicit ?demo=1 in the URL is an intentional request for the
    // sample workspace — honor it even for signed-in users (it has no plan
    // gates, so it doubles as the full product tour).
    const explicitDemo =
      new URLSearchParams(window.location.search).get("demo") === "1";
    if (explicitDemo && !embedded) {
      setUser(DEMO_USER);
      setIsDemo(true);
      setLoading(false);
      return;
    }

    // The *sticky* demo flag is different: a real session beats it —
    // otherwise one "View demo" click leaves signed-in merchants looking at
    // sample data for the rest of the browser session.
    let cancelled = false;
    const controller = new AbortController();
    authenticatedFetch(`${API_BASE}/auth/me`, {
      credentials: "include",
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15_000)]),
    })
      .then(async (res) => {
        if (cancelled || generation !== requestGeneration.current) return;
        if (res.ok) {
          const data = (await res.json()) as AuthUser;
          if (!validAuthUser(data)) throw new Error("Invalid session response");
          if (cancelled || generation !== requestGeneration.current) return;
          setUser(data);
          setIsDemo(false);
          try {
            sessionStorage.removeItem("skubase_demo");
          } catch {
            // ignore
          }
        } else if (embedded) {
          const body = await res.json().catch(() => null);
          if (cancelled || generation !== requestGeneration.current) return;
          setUser(null);
          setNeedsInstall(res.status === 401 && body?.detail === "Shopify app is not installed for this shop.");
          setAuthError("We couldn't verify your Shopify connection. Please try again.");
        } else if (res.status !== 401) {
          setUser(null);
          setAuthError("We couldn't verify your session. Please try again.");
        } else if (demo) {
          setUser(DEMO_USER);
          setIsDemo(true);
        } else {
          setUser(null);
        }
      })
      .catch(() => {
        if (cancelled || generation !== requestGeneration.current) return;
        if (embedded) {
          setUser(null);
          setAuthError("We couldn't reach Shopify or skubase. Please try again.");
        } else {
          setUser(null);
          setAuthError("We couldn't reach Skubase. Check your connection and try again.");
        }
      })
      .finally(() => { if (!cancelled && generation === requestGeneration.current) setLoading(false); });
    return () => {
      cancelled = true;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const changed = (event: StorageEvent) => { if (event.key === SESSION_CHANGED_KEY) void refresh(); };
    const restored = (event: PageTransitionEvent) => { if (event.persisted) void refresh(); };
    window.addEventListener("storage", changed);
    window.addEventListener("pageshow", restored);
    return () => {
      window.removeEventListener("storage", changed);
      window.removeEventListener("pageshow", restored);
    };
    // Handlers use the current embedding mode; the session is fetched afresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEmbedded]);

  useEffect(() => {
    if (!loading && user === null && !isDemo && !isEmbedded && !authError) {
      router.replace("/login");
    }
  }, [loading, user, router, isDemo, isEmbedded, authError]);

  if (loading) {
    return (
      <div className="auth-loading">
        <div className="auth-loading-spinner" aria-hidden />
        <p className="auth-loading-text">
          {isEmbedded ? "Opening skubase inside Shopify..." : "Loading skubase..."}
        </p>
      </div>
    );
  }

  if (user === null) {
    if (isEmbedded || authError) {
      return (
        <div className="auth-loading">
          <p className="auth-loading-text" role="alert">
            {authError || "Please reopen skubase from Shopify Admin."}
          </p>
          <div className="button-row">
            <button type="button" className="button button-primary" onClick={() => void refresh()}>
              Try again
            </button>
            {needsInstall ? (
              <button type="button" className="button button-ghost" onClick={() => {
                if (!redirectToShopifyInstall()) setAuthError("Reopen skubase from your Shopify Admin to finish connecting.");
              }}>
                Connect Shopify
              </button>
            ) : null}
          </div>
        </div>
      );
    }
    return null;
  }

  return (
    <AuthContext.Provider key={`${user.id}:${user.shop_id}`} value={{ user, loading, refresh, logout }}>
      {authError ? <p role="alert" className="auth-error">{authError}</p> : null}
      {children}
    </AuthContext.Provider>
  );
}

function validAuthUser(value: AuthUser): boolean {
  return Boolean(value && Number.isSafeInteger(value.id) && value.id > 0 &&
    Number.isSafeInteger(value.shop_id) && value.shop_id > 0 && typeof value.email === "string" &&
    typeof value.is_admin === "boolean" && typeof value.in_trial === "boolean");
}
