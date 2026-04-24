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
) -> list[PurchaseOrderDraft]:
    vendor_lead_times = vendor_lead_times or {}
    by_vendor: dict[str, list[ReorderSuggestion]] = {}
    for s in suggestions:
        if s.recommended_order_qty <= 0:
            continue
        by_vendor.setdefault(s.vendor, []).append(s)

    drafts: list[PurchaseOrderDraft] = []
    now = datetime.now(timezone.utc)
    for vendor, items in by_vendor.items():
        lines = [
            PurchaseOrderLine(
                sku_id=item.sku_id,
                name=item.name,
                qty=item.recommended_order_qty,
                unit_cost=item.unit_cost,
                extended_cost=item.extended_cost,
            )
            for item in items
        ]
        total = round(sum(line.extended_cost for line in lines), 2)
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
                total_cost=total,
                expected_arrival_date=expected_arrival,
                rationale=(
                    f"Consolidated {len(lines)} SKU"
                    f"{'s' if len(lines) != 1 else ''} from {vendor}. "
                    f"Expected arrival ~{expected_arrival} at current lead time."
                ),
            )
        )

    drafts.sort(key=lambda d: d.total_cost, reverse=True)
    return drafts
