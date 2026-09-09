# Login and CSV import recovery

New sign-ins now report an email-provider failure instead of claiming a link was
sent. The request response still treats new and existing addresses identically;
success confirms provider acceptance, not final inbox delivery. Login errors are
rendered as text, and browser authentication requests have bounded timeouts.

Import destinations travel in the emailed callback URL, using an explicit
allowlist. Opening the email in another tab or browser returns to the selected
import screen without depending on session storage. Existing scanner-tolerant,
15-minute token validity is preserved, and email copy matches that behavior.

New email-authenticated accounts receive isolated workspaces. A client-supplied
Shopify domain cannot grant membership in another workspace; verified Shopify
installation remains a separate path. Existing accounts and ownership records
are unchanged.

Re-importing a Stocky file with product names but no SKUs reuses its existing CSV
product identity. A name collision with a different variant is skipped with a
request for a unique SKU. Stock quantities remain snapshots, and Shopify stock
ownership rules remain in effect. Upload reads stop at the existing 25 MB limit.

Verification: 64 backend tests plus 38 subtests passed across actual cookie auth,
new-account CSV imports, Stocky re-import, ShipStation replay, logout, workspace
isolation, and Shopify sync/install regressions. Seventeen frontend checks and
typecheck passed. A loopback-only browser fixture verified requesting an email,
opening it in a separate tab, confirming the session, and returning to Stocky
import. A simulated provider failure displayed a retry message instead of inbox
success. No external mail or customer inventory was used by this fixture.

Chrome's file-picker automation was blocked by extension file-access settings;
the CSV uploads and database assertions were verified through the real multipart
API routes in an isolated database. This is not a claim of a completed browser
file upload. Production delivery and build verification are recorded separately
after rollout.
