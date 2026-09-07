"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import { useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { invalidateEntitlementsCache } from "@/lib/entitlements";

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

  async function refresh() {
    invalidateEntitlementsCache();
    setLoading(true);
    setAuthError(null);
    setNeedsInstall(false);
    try {
      const res = await authenticatedFetch(`${API_BASE}/auth/me`, {
        credentials: "include",
        signal: AbortSignal.timeout(15_000),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setNeedsInstall(res.status === 401 && body?.detail === "Shopify app is not installed for this shop.");
        setAuthError("We couldn't verify your Shopify connection. Please try again.");
        setUser(null);
        return;
      }
      const data = (await res.json()) as AuthUser;
      setUser(data);
    } catch {
      setAuthError("We couldn't reach Shopify or skubase. Please try again.");
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    invalidateEntitlementsCache();
    try {
      await authenticatedFetch(`${API_BASE}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } catch {
      // best-effort; clear locally regardless
    }
    try {
      sessionStorage.removeItem("skubase_demo");
    } catch {
      // ignore
    }
    setUser(null);
    setIsDemo(false);
    router.replace("/");
  }

  useEffect(() => {
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
        if (cancelled) return;
        if (res.ok) {
          const data = (await res.json()) as AuthUser;
          if (cancelled) return;
          setUser(data);
          setIsDemo(false);
          try {
            sessionStorage.removeItem("skubase_demo");
          } catch {
            // ignore
          }
        } else if (embedded) {
          const body = await res.json().catch(() => null);
          if (cancelled) return;
          setUser(null);
          setNeedsInstall(res.status === 401 && body?.detail === "Shopify app is not installed for this shop.");
          setAuthError("We couldn't verify your Shopify connection. Please try again.");
        } else if (demo) {
          setUser(DEMO_USER);
          setIsDemo(true);
        } else {
          setUser(null);
        }
      })
      .catch(() => {
        if (cancelled) return;
        if (embedded) {
          setUser(null);
          setAuthError("We couldn't reach Shopify or skubase. Please try again.");
        } else if (demo) {
          setUser(DEMO_USER);
          setIsDemo(true);
        } else {
          setUser(null);
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => {
      cancelled = true;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!loading && user === null && !isDemo && !isEmbedded) {
      router.replace("/login");
    }
  }, [loading, user, router, isDemo, isEmbedded]);

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
    if (isEmbedded) {
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
    <AuthContext.Provider value={{ user, loading, refresh, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
