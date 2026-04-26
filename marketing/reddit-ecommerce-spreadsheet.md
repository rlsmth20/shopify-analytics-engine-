# r/ecommerce — spreadsheet forecasting post

**Subreddit:** r/ecommerce
**Best time to post:** Tuesday/Wednesday morning, or Sunday evening for the weekly read
**Flair:** Discussion / Strategy

---

## Title

If your forecasting is a Google Sheet with a 6-month moving average, here's why it's overstocking you

## Body

A merchant told me their reorder workflow last week and I think it's the most common one in DTC: export ShipStation shipments → paste into a Google Sheet → trailing 6-month average → reorder when cover drops below 6 months.

It works. It also overstocks every fast mover and misses every seasonal ramp. Here's why, in plain math:

**1. A 6-month rule is a 99th-percentile-or-higher safety policy applied to every SKU.**

When you reorder anything that drops below 6 months of cover, you're effectively saying you want to survive 6 months of average demand without restocking. For a stable, fast-moving A-item that's a fortune in parked working capital. For a lumpy 12-week-lead-time C-item it might still be too thin. The honest version of this rule is "I don't want to think about it, so I apply the worst-case buffer to everything."

**2. Moving averages weight April equally with September.**

If you're forecasting October from April-through-September data, your average is dominated by summer demand — which has nothing to do with what your customers buy in November. Exponential smoothing (Holt-Winters or just Holt double-exponential) weights recent observations more heavily and decomposes the signal into level, trend, and seasonal components. The math has been around since the 1950s; the spreadsheet just doesn't do it.

**3. ABC × XYZ matters.**

Different SKUs deserve different service levels. Your A-items (top 80% of revenue) probably want 99% (z ≈ 2.33). Your lumpy C-items might be fine at 90% or even 85%. A flat "6 months" applies the same z to everything. You're either overstocking C-items or understocking A-items. Usually both.

**Worked example:** A-item shipping 150/wk with σ=20, lead time 30 days.
- 6-month rule: 150 × 26 = **3,900 units of cover**. At $25 unit cost = $97,500 parked.
- Service-level-segmented at 99%: ROP ≈ 753, plus cycle stock ≈ 900 total. At $25 = **$22,500**.

Same 99% service level, $75,000 less working capital tied up in one SKU. Multiply across a hundred A-items and the number gets significant fast.

---

Disclosure: I'm building a tool that does this math automatically (slelfly — Shopify-first inventory forecasting, Holt + ABC×XYZ + supplier scorecards, $49/mo published pricing locked at renewal). Long-form math post here: https://slelfly.com/blog/why-six-month-moving-average-overstocks-you

But the math is the math regardless of which tool you use, including a fancier spreadsheet. If you want to keep the Sheet, at minimum:

1. Tag your top 20 SKUs and check whether they're really sitting on 6 months of cover. If yes, you're probably overstocking them.
2. Pull your supplier on-time history. If a vendor missed lead times by 20%+ on the last three POs, widen *their* buffer specifically — don't blanket-pad everything.
3. Use exponential smoothing (Excel has =FORECAST.ETS) instead of trailing average for any SKU with seasonality. It's a one-cell change.

Curious what other DTC operators do. Are you all on the spreadsheet, or has someone moved to something better and lived to tell about it?
