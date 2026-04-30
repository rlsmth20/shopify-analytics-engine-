"use client";

import { useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export type AuthUser = {
  id: number;
  email: string;
  shop_id: number;
  is_admin: boolean;
  trial_ends_at: string | null;
  in_trial: boolean;
};

/** Synthetic read-only user injected when ?demo=1 is in the URL. */
const DEMO_USER: AuthUser = {
  id: 0,
  email: "demo@skubase.io",
  shop_id: 0,
  is_admin: false,
  trial_ends_at: null,
  in_trial: true,
};

/**
 * Returns true if the current browser session is in demo mode.
 * Entering via ?demo=1 sets a sessionStorage flag so subsequent in-app
 * navigation (which drops query params) stays in demo mode.
 */
function detectDemo(): boolean {
  if (typeof window === "undefined") return false;
  const param = new URLSearchParams(window.location.search).get("demo") === "1";
  if (param) {
    try { sessionStorage.setItem("skubase_demo", "1"); } catch { /* ignore */ }
    return true;
  }
  try { return sessionStorage.getItem("skubase_demo") === "1"; } catch { return false; }
}

type AuthContextValue = {
  // Non-null inside the provider — AuthGuard only renders children when the
  // user is loaded. Consumers can safely access user.email without a guard.
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

  async function refresh() {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
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
      await fetch(`${API_BASE}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } catch {
      // best-effort; clear locally regardless
    }
    // Clear demo session too.
    try { sessionStorage.removeItem("skubase_demo"); } catch { /* ignore */ }
    setUser(null);
    setIsDemo(false);
    router.replace("/");
  }

  useEffect(() => {
    if (detectDemo()) {
      setIsDemo(true);
      setUser(DEMO_USER);
      setLoading(false);
      return;
    }
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!loading && user === null && !isDemo) {
      router.replace("/login");
    }
  }, [loading, user, router, isDemo]);

  if (loading) {
    return (
      <div className="auth-loading">
        <div className="auth-loading-spinner" aria-hidden />
        <p className="auth-loading-text">Loading skubase…</p>
      </div>
    );
  }

  if (user === null) {
    // Redirect is in flight via useEffect above; render nothing.
    return null;
  }

  return (
    <AuthContext.Provider value={{ user, loading, refresh, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
