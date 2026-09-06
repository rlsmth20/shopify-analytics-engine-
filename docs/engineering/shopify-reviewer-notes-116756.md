# Reviewer notes for paused submission 116756

Prepared for the Shopify review form. These notes have not yet been submitted.

We corrected the installation and store-sync issues reported for SKUbase under reference 116756.

The embedded app now authenticates using Shopify session tokens and token exchange, and loads the current Shopify App Bridge CDN script before application scripts. Installation and reinstall return directly to the embedded dashboard. Store identity comes from Shopify, and browser storage is optional.

Store sync now follows all product, variant, order, and order-line pages, handles Shopify throttling, and reports incomplete imports clearly. Current planning inventory excludes archived, draft, untracked, and gift-card variants. Repeated syncs remove stale inventory without duplicating imported order lines. Empty paid-order history is clearly distinguished from a failed sync.

In our development-store verification, uninstall/reinstall reached the dashboard without the prior OAuth loop. Repeated production syncs completed with 17 products, 26 scanned variants, and 19 eligible planning variants. The seven excluded variants were identified in the receipt. Existing test orders were outside the currently granted 60-day history window, which the app now explains without requesting a reconnect.

To review: install SKUbase on your development store, open Store Sync, select Sync Store, and review the receipt before opening Dashboard, Action Queue, and Analytics. A store with recent paid orders will provide demand history; stores without sufficient history receive explicit low-confidence monitoring recommendations. The app reads Shopify inventory and orders; it does not place supplier orders or change storefront inventory automatically.

We also implemented scoped privacy redaction and customer data access exports, and corrected annual pricing displays. Please continue review of the repaired installation and sync flow.

Before using these notes, record the pending fresh paid-order sync test and Shopify automated-check results in the verification document. Add its verified result here without implying any unperformed test passed.
