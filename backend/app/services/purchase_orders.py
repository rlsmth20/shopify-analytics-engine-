"""Purchase order draft generator.

Groups reorder suggestions by vendor and produces draft POs ready for review.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from app.schemas_v2 import (
    PurchaseOrderDraft,
    PurchaseOrderLine,
    ReorderSuggestion,
)


def build_purchase_order_drafts(
    suggestions: list[ReorderSuggestion],
    vendor_lead_times: dict[str, int] | None = None,
    shipping_cost_per_po: float = 35.0,
) -> list[PurchaseOrderDraft]:
    vendor_lead_times = vendor_lead_times or {}
    shipping_cost_per_po = max(shipping_cost_per_po, 0.0)
    by_vendor: dict[str, list[ReorderSuggestion]] = {}
    for s in suggestions:
        if s.identity_ambiguous or s.recommended_order_qty <= 0:
            continue
        by_vendor.setdefault(s.vendor, []).append(s)

    drafts: list[PurchaseOrderDraft] = []
    now = datetime.now(timezone.utc)
    for vendor, items in by_vendor.items():
        lines = [
            PurchaseOrderLine(
                sku_id=item.sku_id,
                product_id=item.product_id,
                name=item.name,
                qty=item.recommended_order_qty,
                unit_cost=item.unit_cost,
                extended_cost=item.extended_cost,
                cost_source=item.cost_source,
                financial_values_known=item.financial_values_known,
            )
            for item in items
        ]
        subtotal = round(sum(line.extended_cost for line in lines), 2)
        shipping_cost = round(shipping_cost_per_po if any(line.qty > 0 for line in lines) else 0.0, 2)
        total = round(subtotal + shipping_cost, 2)
        costs_known = all(item.financial_values_known for item in items)
        lead_time = vendor_lead_times.get(vendor) or max(
            (item.lead_time_days for item in items), default=14
        )
        expected_arrival = (date.today() + timedelta(days=lead_time)).isoformat()

        drafts.append(
            PurchaseOrderDraft(
                po_id=f"PO-{uuid.uuid4().hex[:8].upper()}",
                vendor=vendor,
                created_at=now,
                status="draft",
                lines=lines,
                subtotal_cost=subtotal,
                shipping_cost=shipping_cost,
                total_cost=total,
                financial_values_known=costs_known,
                expected_arrival_date=expected_arrival,
                rationale=(
                    f"Consolidated {len(lines)} SKU"
                    f"{'s' if len(lines) != 1 else ''} from {vendor}. "
                    f"Expected arrival ~{expected_arrival} at current lead time. "
                    f"Includes estimated ${shipping_cost:.0f} shipping/freight."
                    + (" Add unit costs before approving purchasing costs." if not costs_known else "")
                ),
            )
        )

    drafts.sort(key=lambda d: (d.financial_values_known, d.total_cost if d.financial_values_known else 0), reverse=True)
    return drafts
