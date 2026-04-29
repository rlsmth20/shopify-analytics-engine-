"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function BannerInner() {
  const params = useSearchParams();
  if (params.get("trial_expired") !== "1") return null;

  return (
    <div className="trial-expired-banner" role="alert">
      <span className="trial-expired-icon" aria-hidden>◈</span>
      <div className="trial-expired-body">
        <strong>Your 14-day trial has ended.</strong>{" "}
        Pick a plan below to keep access to your data, recommendations, and
        supplier scorecards. Prices are published — no sales call required.
      </div>
      <Link href="/login" className="trial-expired-link">
        Already subscribed? Sign in →
      </Link>
    </div>
  );
}

export function TrialExpiredBanner() {
  return (
    <Suspense fallback={null}>
      <BannerInner />
    </Suspense>
  );
}
