from dataclasses import dataclass


@dataclass(frozen=True)
class LeadTimeConfig:
    global_default_lead_time_days: int
    global_safety_buffer_days: int
    allow_mock_fallback: bool
    vendor_lead_times: dict[str, int]
    category_lead_times: dict[str, int]


def build_lead_time_config(
    *,
    global_default_lead_time_days: int | None = None,
    global_safety_buffer_days: int | None = None,
    allow_mock_fallback: bool | None = None,
    vendor_lead_times: dict[str, int] | None = None,
    category_lead_times: dict[str, int] | None = None,
    base_config: LeadTimeConfig | None = None,
) -> LeadTimeConfig:
    source = base_config or MOCK_LEAD_TIME_CONFIG
    return LeadTimeConfig(
        global_default_lead_time_days=(
            global_default_lead_time_days
            if global_default_lead_time_days is not None
            else source.global_default_lead_time_days
        ),
        global_safety_buffer_days=(
            global_safety_buffer_days
            if global_safety_buffer_days is not None
            else source.global_safety_buffer_days
        ),
        allow_mock_fallback=(
            allow_mock_fallback
            if allow_mock_fallback is not None
            else source.allow_mock_fallback
        ),
        vendor_lead_times=(
            dict(vendor_lead_times)
            if vendor_lead_times is not None
            else dict(source.vendor_lead_times)
        ),
        category_lead_times=(
            dict(category_lead_times)
            if category_lead_times is not None
            else dict(source.category_lead_times)
        ),
    )


MOCK_LEAD_TIME_CONFIG = LeadTimeConfig(
    global_default_lead_time_days=14,
    global_safety_buffer_days=7,
    allow_mock_fallback=True,
    vendor_lead_times={
        "Northstar Apparel": 16,
        "Summit Sportswear": 19,
        "Harbor Goods": 11,
        "Trailhead Accessories": 22,
    },
    category_lead_times={
        "tops": 12,
        "outerwear": 18,
        "bottoms": 15,
        "accessories": 10,
    },
)
