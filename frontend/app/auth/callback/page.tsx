"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

const API_BASE = APP_API_BASE_URL;

function CallbackInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [status, setStatus] = useState<"verifying" | "error">("verifying");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [errorCode, setErrorCode] = useState<string | null>(null);

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setStatus("error");
      setErrorCode("invalid_token");
      setErrorMessage("This sign-in link is missing its token. Request a new one.");
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/magic-link/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
          credentials: "include",
        });
        if (!res.ok) {
          const detail = parseAuthError(await res.json().catch(() => ({})));
          if (cancelled) return;
          setStatus("error");
          setErrorCode(detail.code);
          setErrorMessage(detail.message);
          return;
        }

        const sessionReady = await confirmSession();
        if (cancelled) return;
        if (!sessionReady) {
          setStatus("error");
          setErrorCode("session_cookie_failed");
          setErrorMessage(
            "Your link verified, but your browser did not store the Skubase session cookie. Please request a fresh sign-in link. If this keeps happening, open the newest link in an incognito/private window or another browser."
          );
          return;
        }

        router.replace("/dashboard");
      } catch {
        if (cancelled) return;
        setStatus("error");
        setErrorCode("unknown_error");
        setErrorMessage("Network error - try the link again in a moment.");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [params, router]);

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <Link href="/" className="auth-brand">
          <span className="auth-brand-mark">sb</span>
          <span className="auth-brand-name">skubase</span>
        </Link>
        {status === "verifying" ? (
          <>
            <h1 className="auth-title">Signing you in...</h1>
            <p className="auth-copy">One moment - verifying your link.</p>
          </>
        ) : (
          <>
            <h1 className="auth-title">That link didn&apos;t work.</h1>
            {errorCode ? <p className="auth-error">Error: {errorCode}</p> : null}
            <p className="auth-copy">{errorMessage}</p>
            <div className="auth-action-stack">
              <Link href="/login" className="button button-primary button-full">
                Request a new sign-in link
              </Link>
              <Link href="/login" className="button button-ghost button-full">
                Back to login
              </Link>
              <Link href="/contact" className="auth-link">
                Contact support
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function parseAuthError(body: unknown): { code: string; message: string } {
  const fallback = {
    code: "unknown_error",
    message:
      "This sign-in link is expired or has already been used. Please request a fresh sign-in link. If you keep getting sent back here, try opening the newest link in an incognito/private window or another browser.",
  };
  if (!body || typeof body !== "object" || !("detail" in body)) return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") {
    return { code: "unknown_error", message: detail };
  }
  if (!detail || typeof detail !== "object") return fallback;
  const code =
    "code" in detail && typeof detail.code === "string"
      ? detail.code
      : fallback.code;
  const message =
    "message" in detail && typeof detail.message === "string"
      ? detail.message
      : fallback.message;
  return { code, message };
}

async function confirmSession(): Promise<boolean> {
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const response = await fetch(`${API_BASE}/auth/me`, {
      credentials: "include",
      cache: "no-store",
    }).catch(() => null);
    if (response?.ok) return true;
    await new Promise((resolve) => setTimeout(resolve, 250 * (attempt + 1)));
  }
  return false;
}

export default function CallbackPage() {
  return (
    <Suspense fallback={null}>
      <CallbackInner />
    </Suspense>
  );
}
