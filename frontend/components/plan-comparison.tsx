import Link from "next/link";
import { Fragment } from "react";

import {
  FEATURE_CATALOG,
  TIER_COLUMNS,
  type CatalogFeature,
  type TierColumn,
} from "@/lib/feature-catalog";

function cell(feature: CatalogFeature, tier: TierColumn) {
  const value = feature[tier];
  if (value === "planned") {
    return <span className="plan-matrix-planned">Planned</span>;
  }
  if (value === "basic") {
    return <span className="plan-matrix-partial">Basic</span>;
  }
  if (value === "full") {
    return (
      <span className="plan-matrix-yes" aria-label="Included (full)">
        ✓
      </span>
    );
  }
  if (value) {
    return (
      <span className="plan-matrix-yes" aria-label="Included">
        ✓
      </span>
    );
  }
  return (
    <span className="plan-matrix-no" aria-label="Not included">
      —
    </span>
  );
}

/**
 * Full plan-by-plan feature matrix, generated from the same catalog the
 * /features page uses so pricing claims can't drift from reality.
 */
export function PlanComparison() {
  return (
    <section className="marketing-section" id="compare">
      <p className="marketing-section-kicker">Compare plans</p>
      <h2 className="marketing-section-title">Exactly what each plan includes.</h2>
      <p className="marketing-section-sub">
        Generated from the same feature catalog as the{" "}
        <Link href="/features">features page</Link> — if it&apos;s listed here, it&apos;s live
        (anything still in progress is marked planned).
      </p>
      <div className="plan-matrix-wrapper">
        <table className="plan-matrix">
          <thead>
            <tr>
              <th scope="col">Feature</th>
              {TIER_COLUMNS.map((tier) => (
                <th key={tier.key} scope="col" className="plan-matrix-tier">
                  {tier.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {FEATURE_CATALOG.map((group) => (
              <Fragment key={group.key}>
                <tr className="plan-matrix-group">
                  <th colSpan={TIER_COLUMNS.length + 1} scope="colgroup">
                    {group.title}
                  </th>
                </tr>
                {group.features.map((feature) => (
                  <tr key={feature.name}>
                    <td className="plan-matrix-feature">
                      <span className="plan-matrix-feature-name">{feature.name}</span>
                      {feature.detail ? (
                        <span className="plan-matrix-feature-detail">{feature.detail}</span>
                      ) : null}
                    </td>
                    {TIER_COLUMNS.map((tier) => (
                      <td key={tier.key} className="plan-matrix-cell">
                        {cell(feature, tier.key)}
                      </td>
                    ))}
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <p className="plan-matrix-footnote">
        Basic = report previews only; Growth unlocks filtering and Excel exports. Planned marks
        features not shipped yet. Every plan starts with a 14-day free trial.
      </p>
    </section>
  );
}
