# Prepared reviewer notes for submission 116756

These notes were prepared for a potential reviewer response and were **not sent**.
Shopify accepted the fixes at approximately 15:37 Pacific on September 6, 2026,
and now shows **Submitted**, awaiting reviewer assignment. No reviewer-note entry
form appeared during submission. The app has not been approved.

We corrected the installation and store-sync issues reported for SKUbase under reference 116756.

The embedded app now authenticates using Shopify session tokens and token exchange, and loads the current Shopify App Bridge CDN script before application scripts. Installation and reinstall return directly to the embedded dashboard. Store identity comes from Shopify, and browser storage is optional.

Store sync now follows all product, variant, order, and order-line pages, handles Shopify throttling, and reports incomplete imports clearly. Current planning inventory excludes archived, draft, untracked, and gift-card variants. Repeated syncs remove stale inventory without duplicating imported order lines. Empty paid-order history is clearly distinguished from a failed sync.

In our development-store verification, uninstall/reinstall reached the dashboard without the prior OAuth loop. Repeated production syncs completed with 17 products, 26 scanned variants, and 19 eligible planning variants. The seven excluded variants were identified in the receipt. Existing test orders were outside the currently granted 60-day history window, which the app now explains without requesting a reconnect.

We then created a current paid development order (#1409) containing one Liquid Snowboard. The deployed app successfully scanned the order and imported its one line, with zero unmatched items. A second live sync recognized that same line as already imported, added zero new lines, and completed without errors or unmatched items. The test used a manual paid status on a development store; it did not charge a card, attach a customer, or send an invoice or email.

The live dashboard then showed the $749.95 sale as $750 after rounding in both 30-day revenue and Liquid Snowboard's top-mover entry. The dashboard contained 19 current SKUs and rendered its 30-point revenue chart without errors. The Liquid Snowboard also appeared in the Action Queue.

Shopify's automated common-error checks now pass. Embedded checks and AI self-review are complete. The latest release also preserves the app session during internal navigation and reduces unnecessary dashboard computation.

To review: install SKUbase on your development store, open Store Sync, select Sync Store, and review the receipt before opening Dashboard, Action Queue, and Analytics. A store with recent paid orders will provide demand history; stores without sufficient history receive explicit low-confidence monitoring recommendations. The app reads Shopify inventory and orders; it does not place supplier orders or change storefront inventory automatically.

We also implemented scoped privacy redaction and customer data access exports, and corrected annual pricing displays. Please continue review of the repaired installation and sync flow.

Installation, paid-order import, repeat-sync idempotence, and dashboard/action display are verified. Submission is complete and awaiting Shopify review; this prepared note itself was not sent.
