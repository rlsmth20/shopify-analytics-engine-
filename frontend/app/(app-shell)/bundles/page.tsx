"use client";

import { useEffect, useState } from "react";

import { currency, fetchBundles, type BundleHealth } from "@/lib/api-v2";

export default function BundlesPage() {
  const [bundles, setBundles] = useState<BundleHealth[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchBundles(controller.signal)
      .then((r) => setBundles(r.bundles))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  if (loading && bundles.length === 0) {
    return <div className="page-loading">Analyzing bundle health…</div>;
  }
  if (error) return <p className="page-error-copy">{error}</p>;

  return (
    <div className="bundles-page">
      {bundles.map((b) => (
        <div
          key={b.bundle_sku_id}
          className={`bundle-card${
            b.max_bundles_sellable === 0 ? " bundle-card-broken" : ""
          }`}
        >
          <div className="bundle-head">
            <div>
              <h4 className="bundle-name">{b.bundle_name}</h4>
              <p className="muted small">{b.bundle_sku_id}</p>
            </div>
            <div className="bundle-capacity">
              <p className="bundle-capacity-value">{b.max_bundles_sellable}</p>
              <p className="bundle-capacity-label">sellable now</p>
            </div>
          </div>

          <div className="bundle-limiting">
            <span className="muted small">Bottleneck component</span>
            <p>{b.limiting_component_name}</p>
          </div>

          <ul className="bundle-components">
            {b.component_status.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>

          {b.total_component_value_at_risk > 0 ? (
            <p className="bundle-risk">
              {currency(b.total_component_value_at_risk)} in component inventory is
              stranded behind this bottleneck.
            </p>
          ) : null}

          <p className="bundle-recommendation">{b.recommended_action}</p>
        </div>
      ))}
    </div>
  );
}
