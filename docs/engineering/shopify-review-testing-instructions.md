# Partner Dashboard testing instructions (review 116756)

Paste the block below into Partner Dashboard → Skubase → Distribution → App
Store listing → Testing instructions. It answers requirements 4.5.4/4.5.5:
Skubase has no separate login, so the instructions must say so explicitly
rather than leaving the credentials field empty.

---

LOGIN / CREDENTIALS
No credentials are required. Skubase has no separate account, username or
password. It authenticates automatically through Shopify (App Bridge session
tokens) when opened from Shopify Admin, and every feature is available to the
installing store. There is nothing to sign up for.

HOW TO TEST
1. Install Skubase on your test store and approve the requested scopes. The
   app opens embedded in Shopify Admin and syncs products, inventory and
   orders (a few seconds to a few minutes depending on store size).
2. FULL FEATURE ACCESS: open "Plan & billing" (Settings section of the app
   navigation) and choose Scale. Development stores receive a test charge, so
   nothing is billed, and every plan includes a 14-day free trial. Scale
   unlocks every feature, including Forecast, Purchase orders, Suppliers and
   Stock transfers.
3. Decline/approve: on Shopify's approval page you can decline to return to
   the app with no plan, then choose a plan again at any time. Approve to
   activate it.
4. Dashboard, Action Queue, Inventory health, Forecast and Purchase orders
   show data once the first sync finishes; an empty store shows empty states.
5. Reinstall: uninstall and reinstall the app, then open Plan & billing.
   The app re-verifies billing with Shopify and you can request plan approval
   again. If Shopify billing is temporarily unreachable the page still lists
   every plan with a "Retry billing check" button, so approval can always be
   requested.

Support: support@skubase.io
