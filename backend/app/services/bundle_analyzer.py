"""Bundle/kit analyzer.

Shopify merchants frequently run bundles (gift sets, multi-packs, starter kits)
where a bundle SKU is only sellable if *every* component has sufficient stock.
A single weak component silently strands cash in the other components.

This service computes:
* max_bundles_sellable — floor(component_inventory / qty_per_bundle) across all components
* limiting_component — the component driving the ceiling
* component_value_at_risk — the cash tied up in components that can't ship because one is out
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.schemas import SkuDetail
from app.schemas_v2 import BundleComponent, BundleHealth


@dataclass(frozen=True)
class BundleDefinition:
    bundle_sku_id: str
    bundle_name: str
    components: list[BundleComponent]


def analyze_bundles(
    bundles: list[BundleDefinition],
    skus: list[SkuDetail],
) -> list[BundleHealth]:
    sku_index = {s.sku_id: s for s in skus}
    results: list[BundleHealth] = []

    for bundle in bundles:
        per_component_bundles: list[tuple[BundleComponent, int, SkuDetail]] = []
        missing = False
        for comp in bundle.components:
            sku = sku_index.get(comp.component_sku_id)
            if sku is None:
                missing = True
                break
            per_bundle = math.floor(sku.inventory / max(comp.qty_per_bundle, 1))
            per_component_bundles.append((comp, per_bundle, sku))

        if missing or not per_component_bundles:
            results.append(
                BundleHealth(
                    bundle_sku_id=bundle.bundle_sku_id,
                    bundle_name=bundle.bundle_name,
                    max_bundles_sellable=0,
                    limiting_component_sku_id="",
                    limiting_component_name="(component missing from catalog)",
                    component_status=[
                        "One or more components not found in catalog."
                    ],
                    total_component_value_at_risk=0.0,
                    recommended_action="Map all component SKUs before relying on bundle analytics.",
                )
            )
            continue

        # Value at risk = other components that are "stuck" because we can't assemble
        # more bundles than the limiting component allows.
        stuck_capital = 0.0
        status_lines: list[str] = []
        max_bundles_sellable = min(pair[1] for pair in per_component_bundles)
        for comp, per_bundle, sku in per_component_bundles:
            units_used = max_bundles_sellable * comp.qty_per_bundle
            units_stranded = max(sku.inventory - units_used, 0)
            if per_bundle > max_bundles_sellable:
                stuck_capital += units_stranded * sku.cost
                status_lines.append(
                    f"{sku.name}: {sku.inventory} on-hand, {units_used} needed, "
                    f"{units_stranded} stranded"
                )
            else:
                status_lines.append(
                    f"{sku.name}: {sku.inventory} on-hand — bottleneck component"
                )

        limiting_component_sku = min(per_component_bundles, key=lambda p: p[1])[2]
        results.append(
            BundleHealth(
                bundle_sku_id=bundle.bundle_sku_id,
                bundle_name=bundle.bundle_name,
                max_bundles_sellable=max_bundles_sellable,
                limiting_component_sku_id=limiting_component_sku.sku_id,
                limiting_component_name=limiting_component_sku.name,
                component_status=status_lines,
                total_component_value_at_risk=round(stuck_capital, 2),
                recommended_action=_recommend(
                    max_bundles_sellable, limiting_component_sku, stuck_capital
                ),
            )
        )

    return results


def _recommend(
    max_bundles: int, limiting_sku: SkuDetail, stuck_capital: float
) -> str:
    if max_bundles == 0:
        return (
            f"Bundle is currently unsellable — reorder {limiting_sku.name} "
            "immediately to unlock the other components."
        )
    if stuck_capital > 500:
        return (
            f"${stuck_capital:,.0f} in component inventory is stranded behind "
            f"{limiting_sku.name}. Prioritize replenishing this component."
        )
    return (
        f"{limiting_sku.name} is the bottleneck — watch its velocity closely to "
        "avoid unexpected bundle stockouts."
    )


# Sample bundle catalog used for MVP/demo until the real Shopify bundle metafield is wired up
DEMO_BUNDLES: list[BundleDefinition] = [
    BundleDefinition(
        bundle_sku_id="bundle_athletic-starter",
        bundle_name="Athletic Starter Kit",
        components=[
            BundleComponent(component_sku_id="sku_athletic-tee-black-m", qty_per_bundle=1),
            BundleComponent(component_sku_id="sku_mesh-short-navy-l", qty_per_bundle=1),
            BundleComponent(component_sku_id="sku_wool-beanie-rust", qty_per_bundle=1),
        ],
    ),
    BundleDefinition(
        bundle_sku_id="bundle_heritage-layering",
        bundle_name="Heritage Layering Set",
        components=[
            BundleComponent(component_sku_id="sku_heritage-hoodie-charcoal-l", qty_per_bundle=1),
            BundleComponent(component_sku_id="sku_fleece-jogger-stone-m", qty_per_bundle=1),
            BundleComponent(component_sku_id="sku_ribbed-tank-ivory-s", qty_per_bundle=1),
        ],
    ),
    BundleDefinition(
        bundle_sku_id="bundle_accessory-trio",
        bundle_name="Everyday Accessory Trio",
        components=[
            BundleComponent(component_sku_id="sku_canvas-tote-olive", qty_per_bundle=1),
            BundleComponent(component_sku_id="sku_vintage-cap-forest", qty_per_bundle=1),
            BundleComponent(component_sku_id="sku_wool-beanie-rust", qty_per_bundle=1),
        ],
    ),
]
