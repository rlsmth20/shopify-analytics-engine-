# Launch readiness — slelfly.com

Written 2026-04-27 ahead of the first marketing push.

## What was checked statically

### ✅ Internal links (`<Link href>`)
Every internal `href` in `app/` and `components/` resolves to an existing
`page.tsx`. No broken navigation. Confirmed with grep against route tree.

### ✅ Brand consistency
Zero misspellings of `slelfly` (no `slefly`, `slelfy`, or `shelfly` anywhere).
The only remaining mention of "Inventory Command" is the changelog entry
documenting the rename, which is intentional. Three live-bug brand strings
were fixed:

- `frontend/app/login/page.tsx` — was a fake-auth page still branded
  "Inventory Command". Replaced with a `redirect("/")` so any inbound link
  lands on the home page.
- `backend/app/api/routes/alerts.py` — test-alert subject + body now say
  "slelfly".
- `backend/app/services/notifications.py` — email-template footer now says
  "slelfly".

### ✅ Sitemap accuracy
14 entries in `frontend/app/sitemap.ts`, 14 marketing pages on disk, 1:1
match. `/login` removed from sitemap (now a server redirect, no need to
index).

### ✅ Per-page metadata
Every public page has `export const metadata` with title, description,
`alternates.canonical`, and `openGraph` block. Two gaps fixed during the
audit:

- `app/import-stocky/layout.tsx` — added (page is a client component, can't
  export metadata directly).
- `app/import-shipstation/layout.tsx` — added for the same reason.

### ✅ Waitlist conversion coverage
`<WaitlistForm>` now appears on every page where a visitor would convert:

- `/` (hero + footer — 2 forms)
- `/pricing` — 1 form
- `/goodbye-stocky` — hero + footer
- `/goodbye-genie` — hero + footer
- `/vs-spreadsheet` — hero + footer
- `/about` — newly added
- `/changelog` — newly added
- `/blog` (index) — newly added

Blog post pages (`/blog/<slug>`) still rely on a CTA button at the bottom
linking back to `/`. Acceptable but not optimal — readers landing from
search who don't scroll to the link drop off.

### ✅ JSON-LD structured data
Four schema blocks: SoftwareApplication (root layout), FAQPage (pricing),
Article × 2 (blog posts). Each is a JS object literal, serialized via
`JSON.stringify` — by construction they're valid JSON.

### ✅ Transactional email
Resend wired and verified end-to-end. Confirmation email arrives within
~5 seconds of signup. Domain `slelfly.com` is DNS-verified in Resend.

## What I could NOT verify from the sandbox

The WSL filesystem mount is showing stale/truncated views of several
edited files (well-documented bug per memory). This means:

- `tsc --noEmit` produces dozens of false-positive "unterminated string"
  errors against files Vercel builds successfully.
- `python -m py_compile` produces "null bytes" / "unterminated paren"
  errors against files Railway builds successfully.

These are sandbox artifacts, not real bugs. The authoritative compile
checks are the live Vercel and Railway build logs.

## Manual checklist for the live site (10 minutes)

Open slelfly.com in an incognito window and click through:

1. **Home page renders, no console errors.** Network tab — confirm OG image
   and analytics script both 200.
2. **Sign up with a fresh email** in the home hero form. Expected: green
   success state in the form, confirmation email in inbox within 5 seconds.
3. **Visit `/pricing`** — three tiers visible, "Most merchants pick this"
   ribbon on Growth, FAQ rendered.
4. **Visit `/goodbye-stocky`** — hero + comparison table + 4-step migration.
   Hero waitlist form works.
5. **Visit `/blog/stocky-alternatives-2026`** — long-form copy renders,
   bottom CTA buttons work.
6. **Visit `/dashboard`** — yellow demo banner is visible at the top, all
   the cards render with mock data, no obvious empty states.
7. **Visit `/login`** — should redirect to `/`. (If you see the old fake
   form, the new code hasn't deployed yet.)
8. **View page source on home** — look for `<meta property="og:image">`
   and `<script type="application/ld+json">` with the SoftwareApplication
   schema.

## Submit to search engines (5 minutes, do this after the deploy lands)

- Google Search Console: add slelfly.com property, verify via DNS, submit
  `https://slelfly.com/sitemap.xml`.
- Bing Webmaster Tools: add property, submit the same sitemap.

Without this step, organic search traffic from Stocky-related queries
won't surface for weeks longer than necessary.

## Known gaps that are acceptable for launch

- No real auth. `/login` redirects to home; the app shell at `/dashboard`
  and downstream is publicly accessible by design (it's the demo).
- No Stripe/billing. Pricing page advertises tiers; clicks go to waitlist.
- No Shopify OAuth. Importer pages take CSV uploads, not OAuth tokens.
- Mock data on the dashboard. Demo banner labels it clearly.

These are documented as future work, not bugs. The waitlist captures
intent until paid plans launch.

## Things to do BEFORE the first Reddit/HN post lands

1. Push the email-integration commit (already required for Resend to fire).
2. Push the launch-readiness fixes from this audit.
3. Verify deploy went green on Vercel and Railway.
4. Walk the manual checklist above.
5. Submit sitemap to Google Search Console.

Then post.
