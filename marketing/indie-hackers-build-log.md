# Indie Hackers — build log post

**Where:** indiehackers.com → "Building" or "Show IH" depending on the section that's most active that week.

---

## Title

Built a Shopify inventory tool because every existing one got acquired and got worse

## Body

I'm two months into building skubase, a Shopify-first inventory tool. I want to share why I started, because the "why" turned into a positioning thesis I didn't expect.

### The trigger

I started by surveying the 25 inventory tools Shopify merchants most commonly evaluate. The pattern that fell out: 8 of 25 had been acquired within the last 5 years, and customer sentiment for each had measurably degraded after the acquisition.

- Inventory Planner → Sage (2021): ~3× price hike, support regression
- Linnworks → Marlin (PE): 681% renewal hike per Trustpilot
- Veeqo → Amazon (2021): roadmap froze
- Skubana → Extensiv: forced platform migration
- Cin7 Core (rebrand from DEAR): price restructuring
- Sellbrite → GoDaddy: roadmap "frozen for years"
- Brightpearl → Sage (2022): support drops
- SKUVault → Linnworks (2022): same PE owner, buyers wary

That's a 32% acquisition rate in a 5-year window in a single niche. The mechanism is straightforward: PE has a 5-7 year hold horizon and IRR targets. The cheapest path to those targets in mature SaaS is renewal price hikes + support cost cuts. Customer-side this looks like "the tool I depend on got worse."

### The thesis

The category needs a tool that's structurally outside that pattern. Founder-led, independent, with the price commitment in the TOS. We're calling that "no PE squeeze" — and it's a position our acquired competitors literally cannot copy.

### What I actually built

Two months in, skubase has:
- Holt double-exponential forecasting + weekly seasonality + stockout probability (vs. competitors' moving averages)
- ABC × XYZ classification + service-level-segmented safety stock (vs. one buffer for everything)
- Supplier scorecards: on-time, fill rate, lead-time stability (23 of 25 competitors don't do this)
- Bundle/kit BOM-aware reordering
- Dead-stock plans: markdown / bundle / wholesale / write-off (24 of 25 don't do this either)
- Multi-channel rule engine alerts (email/SMS/Slack/webhook)
- Stocky CSV importer (Stocky shuts down Aug 31, 2026 — biggest time-boxed migration window in the market)
- ShipStation CSV importer (the most common forecasting data source for merchants who don't have proper inventory software)
- Published pricing $49/$149/$349 with a written price-lock clause in TOS

Stack: FastAPI + SQLAlchemy backend, Next.js 15 frontend, Railway + Vercel deploy. Plain Python forecasting (no ML dep).

### What's not built yet

- Real auth + Stripe — currently no signup flow
- Native Amazon/eBay write-back (we ingest history via ShipStation but don't manage cross-channel listings)
- Onboarding concierge program for the Stocky migration cohort

### What I'm asking IH

I'd love feedback on:

1. Does "founder-led, no PE squeeze" land as substantive or as hand-waving? If it lands, what would make it land harder?
2. The Stocky migration window is 4 months out. What would you do with that timeline?
3. What's the most overlooked early-stage marketing channel for a B2B SaaS in a niche full of acquired competitors?

skubase.io if you want to poke around. Two blog posts at /blog go deep on the math (Holt forecasting and why moving averages overstock). Pricing page has the price-lock language.

(Will reply to every comment.)
