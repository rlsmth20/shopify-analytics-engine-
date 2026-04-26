# TESTING — pre-launch readiness checklist

Run through this every time before driving traffic to slelfly.com.

## Public marketing pages (Vercel)

Each of these should return 200 and render without console errors:

- [ ] https://slelfly.com — landing page with waitlist form
- [ ] https://slelfly.com/pricing — three tiers + price-lock card + waitlist form anchor
- [ ] https://slelfly.com/about — independence positioning
- [ ] https://slelfly.com/changelog — release entries
- [ ] https://slelfly.com/blog — blog index
- [ ] https://slelfly.com/blog/stocky-alternatives-2026 — first post
- [ ] https://slelfly.com/blog/why-six-month-moving-average-overstocks-you — second post
- [ ] https://slelfly.com/goodbye-stocky — Stocky migration lander with waitlist
- [ ] https://slelfly.com/goodbye-genie — Genie migration lander with waitlist
- [ ] https://slelfly.com/vs-spreadsheet — spreadsheet-killer with waitlist
- [ ] https://slelfly.com/import-stocky — Stocky CSV uploader (anonymous-accessible for now)
- [ ] https://slelfly.com/import-shipstation — ShipStation CSV uploader
- [ ] https://slelfly.com/privacy — privacy policy
- [ ] https://slelfly.com/terms — TOS including price-lock clause
- [ ] https://slelfly.com/sitemap.xml — XML with ~15 URLs
- [ ] https://slelfly.com/robots.txt — text body referencing the sitemap
- [ ] https://slelfly.com/login — login page (auth not wired, button still routes to /dashboard)

## OG card

- [ ] Paste https://slelfly.com into https://www.opengraph.xyz/ — should render the slelfly gradient card with tagline
- [ ] Paste https://slelfly.com/pricing — same card, "Pricing — slelfly" title

## Demo dashboard

- [ ] https://slelfly.com/dashboard renders **with the yellow demo banner** at the top saying "Demo mode."
- [ ] Sidebar nav loads and every link routes
- [ ] Action queue shows mock SKUs without errors
- [ ] /forecast shows the explainability "Why this number?" toggle

## Backend health (Railway)

- [ ] `curl https://<railway-domain>/health` returns 200
- [ ] `curl -X POST https://<railway-domain>/integrations/stocky/import` returns 422 (missing form fields, not 500 — confirms python-multipart loaded)
- [ ] `curl https://<railway-domain>/waitlist/count` returns `{"count": <n>}`

## Waitlist signup

End-to-end test from the live site:

- [ ] Open https://slelfly.com → enter test email + shopify domain → click "Get early access"
- [ ] Form shows green success state ("You're on the list")
- [ ] Backend log shows the POST landed
- [ ] Re-submit same email → still shows success (idempotent), `already_signed_up: true` in response
- [ ] Submit invalid email → form shows error inline

## Stocky CSV importer

- [ ] Drop `marketing/test-data/stocky-sample.csv` into /import-stocky with shop domain `test.myshopify.com`
- [ ] Result card shows: 5 products processed, 5 inserted, 5 inventory rows, 0 skipped
- [ ] Click "Open my dashboard" — lands on dashboard

## ShipStation CSV importer

- [ ] Drop `marketing/test-data/shipstation-sample.csv` into /import-shipstation with shop domain `test.myshopify.com`
- [ ] Result shows: 12 line items inserted, 5 distinct SKUs, top-5 velocity table with SHIRT-RED-S at the top
- [ ] Date window shows 2026-01-12 → 2026-04-20

## Database initialization (one-time, on first deploy)

If the alerts or waitlist endpoints return 500 on first request, run on Railway:

```
python -m app.db.init_db
```

This creates `alert_rules`, `notification_channels`, and `waitlist_signups` tables.

## SEO / search engines

- [ ] Submit https://slelfly.com/sitemap.xml to https://search.google.com/search-console
- [ ] Same to https://www.bing.com/webmasters/
- [ ] Test JSON-LD: paste https://slelfly.com/pricing into https://search.google.com/test/rich-results — FAQPage schema should validate
- [ ] Same for https://slelfly.com/ — SoftwareApplication schema should validate

## Mobile responsiveness

Open the homepage at 375px viewport (Chrome DevTools mobile mode):

- [ ] Hero text wraps cleanly
- [ ] Migration cards stack vertically
- [ ] Waitlist form inputs stack vertically
- [ ] No horizontal scroll
- [ ] Footer links wrap

## Known gaps (NOT blockers for waitlist launch)

- Real authentication is not wired — `/login` button routes to `/dashboard` regardless
- Stripe billing not wired — pricing page CTAs go to waitlist
- Shopify OAuth not wired — `/store-sync` requires manual access token paste
- Email transactional service not wired — waitlist signups land in DB but no confirmation email is sent yet
- /alerts UI persists rules but no real notifications fire

## Launch gate

You can drive Reddit/HN traffic when:
- All checkboxes above are green
- The demo banner is visible to anonymous /dashboard visitors
- The waitlist form has been tested end-to-end at least 3 times
- Privacy and Terms pages exist and load

If any box fails, don&apos;t post yet. The first impression matters.
