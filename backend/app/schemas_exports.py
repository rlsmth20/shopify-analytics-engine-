"""Bounded, stateless spreadsheet inputs. No formulas or file uploads accepted."""
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Amount = Annotated[float, Field(ge=0, le=1e15)]
Balance = Annotated[float, Field(ge=-1e15, le=1e15)]


class ExportModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class HistoryPoint(ExportModel):
    date: date
    cost_value: Balance | None
    retail_value: Balance | None
    total_units: Balance | None


class HistoryExport(ExportModel):
    kind: Literal["inventory_history"]
    sample: bool = False
    points: list[HistoryPoint] = Field(min_length=1, max_length=365)

    @model_validator(mode="after")
    def unique_dates(self):
        if len({p.date for p in self.points}) != len(self.points):
            raise ValueError("Each snapshot must have a unique date")
        return self


class HealthSettings(ExportModel):
    salesDays: int = Field(ge=1, le=3650)
    defaultLeadDays: int = Field(ge=1, le=3650)
    targetCoverDays: int = Field(ge=1, le=3650)


class HealthRow(ExportModel):
    sku: str = Field(min_length=1, max_length=255)
    onHand: Amount
    unitsSold: Amount
    unitCost: Amount | None
    leadDays: Amount
    safetyStock: Amount
    dailySales: Amount
    daysCover: Amount | None
    reorderPoint: Amount
    excessUnits: Amount | None
    excessCost: Amount | None
    status: Literal["stockout_risk", "reorder_review", "excess_stock", "no_recent_sales", "within_range"]


class HealthExport(ExportModel):
    kind: Literal["inventory_health"]
    sample: bool = False
    currency: Literal["USD", "CAD", "GBP", "EUR", "AUD", "NZD"] = "USD"
    settings: HealthSettings
    rows: list[HealthRow] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def unique_skus(self):
        if len({r.sku.lower() for r in self.rows}) != len(self.rows):
            raise ValueError("Each SKU must be unique")
        return self


WorkbookExport = Annotated[HistoryExport | HealthExport, Field(discriminator="kind")]
