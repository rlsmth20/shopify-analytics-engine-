# Hacker News — Show HN

**Best time to post:** Tuesday-Thursday, 7-9am Pacific (when the EU is winding down and the US is starting). Avoid Mondays (high volume) and Fridays (low traffic).

**Frequency:** ONE shot. Don't repost.

---

## Title

Show HN: Slelfly – Shopify inventory forecasting that beats your spreadsheet

(HN auto-prefixes "Show HN:" but include it explicitly in the submission title field. Keep under 80 chars. Avoid emoji. Avoid hype words.)

## URL

https://slelfly.com

## First comment (post immediately after submission)

Hey HN. I've been studying why Shopify merchants forecast inventory with Google Sheets and a six-month moving average, and built a tool that does the math automatically.

The summary: most inventory tools in the Shopify ecosystem either (a) got acquired and got worse — Inventory Planner under Sage, Linnworks under Marlin, Veeqo under Amazon, Cin7 Core, Brightpearl under Sage — or (b) are quote-only enterprise products that aren't a fit for SMBs. The remaining tools mostly use trailing-average forecasting, treat vendors as contact records, and have no real plan for dead stock beyond a flag.

Slelfly does:

- Holt double-exponential smoothing with a weekly seasonality factor and a stockout probability on every SKU (instead of moving averages)
- ABC × XYZ classification and service-level-segmented safety stock (instead of one buffer for everything)
- Supplier scorecards: on-time delivery, fill rate, lead-time stability, preferred/acceptable/at-risk tiering (instead of vendors-as-contacts)
- Bundle/kit BOM-aware reordering so a PO never leaves a component short
- Dead-stock plans (markdown / bundle / wholesale / write-off) with dollar-impact estimates
- A real rule engine for alerts (email, SMS, Slack, webhook) instead of email-only
- An action-ranked dashboard ("what should I do today?") instead of a wall of charts

Stack: FastAPI + SQLAlchemy backend, Next.js 15 App Router frontend, deployed on Railway + Vercel. Forecast engine is plain Python (no GPU/ML dep — Holt-Winters and friends).

Pricing is published on the site ($49 / $149 / $349) with a written price-lock clause in the TOS — explicit response to the IP/Linnworks pattern of post-acquisition price hikes.

Honest stuff still missing: native Amazon/eBay write-back (we ingest history via ShipStation but don't yet manage cross-channel listings), proper auth/Stripe billing (we have a public dashboard but aren't charging anyone yet), and the Stocky CSV importer is the on-ramp for the largest concentrated migration window in this market (~Aug 2026 sunset).

Curious what holes HN finds. Especially curious about (a) whether the forecasting math is overengineered vs. just running an LSTM, and (b) whether the "founder-led, no PE squeeze" positioning reads as substantive or as hand-waving.

Code is closed for now but the architecture is straightforward; happy to walk through any piece. Twenty-five-competitor analysis I did before building this is in the about page if anyone wants the methodology.
