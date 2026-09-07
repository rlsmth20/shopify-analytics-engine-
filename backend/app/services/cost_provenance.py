"""Keep a numeric compatibility estimate separate from recorded unit cost."""
from decimal import Decimal
import math


MISSING_COST_WARNING = "Unit cost is missing. Add a recorded cost before relying on profit, capital, or purchasing-cost estimates."


def unit_cost_details(product):
    if product.cost is not None and math.isfinite(float(product.cost)) and product.cost >= 0:
        return float(product.cost), "recorded"
    if product.price is not None and math.isfinite(float(product.price)) and product.price > 0:
        # Retained only for legacy API fields, never a verified financial value.
        estimate = Decimal(str(product.price)) * Decimal("0.40")
        return float(estimate.quantize(Decimal("0.01"))), "estimated_from_price"
    return 0.0, "missing"


def cost_known(sku):
    return sku.cost_source == "recorded"


def financial_projection(known, **values):
    return {"financial_values_known": known,
            "financial_values": {key: value if known else None for key, value in values.items()}}
