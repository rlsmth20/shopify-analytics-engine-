"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

function CallbackInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [status, setStatus] = useState<"verifying" | "error">("verifying");
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setStatus("error");
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
          const body = await res.json().catch(() => ({}));
          if (cancelled) return;
          setStatus("error");
          setErrorMessage(
            body?.detail ||
              "This sign-in link is invalid or expired. Request a new one."
          );
          return;
        }
        if (cancelled) return;
        // Small delay so the success state is perceptible.
        router.replace("/dashboard");
      } catch {
        if (cancelled) return;
        setStatus("error");
        setErrorMessage("Network error — try the link again in a moment.");
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
            <p className="auth-copy">One moment — verifying your link.</p>
          </>
        ) : (
          <>
            <h1 className="auth-title">That link didn&apos;t work.</h1>
            <p className="auth-copy">{errorMessage}</p>
            <Link href="/login" className="button button-primary button-full">
              Request a new sign-in link
            </Link>
          </>
        )}
      </div>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <Suspense fallback={null}>
      <CallbackInner />
    </Suspense>
  );
}
