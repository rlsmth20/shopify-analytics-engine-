"use client";

import Link from "next/link";

import { trackEvent } from "@/lib/analytics";

export function InventoryRiskSnapshotCtas() {
  function focusForm() {
    trackEvent("inventory_snapshot_cta_click", { cta: "hero_primary" });
    const form = document.getElementById("snapshot-form");
    form?.scrollIntoView({ behavior: "smooth", block: "start" });
    window.setTimeout(() => {
      const input = form?.querySelector("input");
      input?.focus();
    }, 450);
  }

  return (
    <div className="marketing-hero-ctas">
      <button type="button" className="button button-primary button-lg" onClick={focusForm}>
        Request free snapshot
      </button>
      <Link
        href="/sample-inventory-risk-snapshot"
        className="button button-secondary button-lg"
        onClick={() => trackEvent("inventory_snapshot_cta_click", { cta: "sample_snapshot" })}
      >
        View sample snapshot
      </Link>
    </div>
  );
}

export function SampleSnapshotCta({ cta }: { cta: string }) {
  return (
    <Link
      href="/inventory-risk-snapshot"
      className="button button-primary button-lg"
      onClick={() => trackEvent("sample_snapshot_cta_click", { cta })}
    >
      Request free snapshot
    </Link>
  );
}

export function SampleDemoCta({ cta }: { cta: string }) {
  return (
    <Link
      href="/dashboard?demo=1"
      className="button button-secondary button-lg"
      onClick={() => trackEvent("sample_snapshot_cta_click", { cta })}
    >
      View demo
    </Link>
  );
}
