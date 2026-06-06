"use client";

import { useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import {
  authenticatedFetch,
  getEmbeddedShopifyContext,
  redirectToShopifyInstall,
} from "@/lib/shopify-embedded";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

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

  async function refresh() {
    try {
      const res = await authenticatedFetch(`${API_BASE}/auth/me`, {
        credentials: "include",
      });
      if (!res.ok) {
        setUser(null);
        return;
      }
      const data = (await res.json()) as AuthUser;
      setUser(data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
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
    const demo = detectDemo();
    const embedded = getEmbeddedShopifyContext() !== null;
    setIsEmbedded(embedded);

    if (demo && !embedded) {
      setUser(DEMO_USER);
      setIsDemo(true);
      setLoading(false);
      return;
    }

    authenticatedFetch(`${API_BASE}/auth/me`, { credentials: "include" })
      .then(async (res) => {
        if (res.ok) {
          const data = (await res.json()) as AuthUser;
          setUser(data);
          setIsDemo(false);
        } else if (embedded) {
          setUser(null);
          redirectToShopifyInstall();
        } else if (demo) {
          setUser(DEMO_USER);
          setIsDemo(true);
        } else {
          setUser(null);
        }
      })
      .catch(() => {
        if (embedded) {
          setUser(null);
          redirectToShopifyInstall();
        } else if (demo) {
          setUser(DEMO_USER);
          setIsDemo(true);
        } else {
          setUser(null);
        }
      })
      .finally(() => setLoading(false));
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
    return null;
  }

  return (
    <AuthContext.Provider value={{ user, loading, refresh, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
