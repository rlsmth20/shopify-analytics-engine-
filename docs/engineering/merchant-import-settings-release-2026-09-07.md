# Merchant imports, settings and destination setup

This release prevents repeat CSV imports from inflating purchasing inputs and makes failed settings reads visible before merchants edit anything.

## Import behavior

- ShipStation imports commit sales and durable batch/row receipts together. Exact replay adds no sales; identified split shipments remain separate. Explicit Shopify rows are excluded and unidentified sources or ambiguous overlap are held for review. Results show newly imported, already recorded, held, Shopify-excluded and invalid rows separately.
- Stocky imports keep Shopify as the stock authority once a connection or native catalog exists. Only an unambiguous native variant can receive cost/lead-time enrichment. CSV-only imports preserve stock when quantity is absent, reject invalid quantities/prices without truncation, and distinguish missing costs from recorded zero.
- Import pages show row-level reasons, current-inventory/sales-history prerequisites and concrete next steps. A lost Stocky POST response is not automatically repeated through a second transport; the page tells the merchant to check the catalog before retrying.

See [shipment receipts and source rules](shipstation-import-safety-2026-09-07.md) and [Stocky stock ownership](stocky-import-inventory-source-2026-09-07.md). Existing historical imports and ambiguous CSV-to-Shopify product identities are preserved. This release does not infer or automatically merge historical variant mappings.

## Settings and alerts

Alert destinations, rules and activity load independently. A failed activity request cannot hide confirmed channels; an unavailable setup section displays unknown status and a targeted retry. Unconfirmed settings do not open an editable default form. Obsolete workspace responses are aborted and ignored.

Purchasing settings preserve independently loaded sections, block writes until rule reads are confirmed, and save only changed sections. Partial saves name their successful and unconfirmed sections and retain unsaved edits. Product lookup is optional. Demo settings perform no read/write requests against a merchant's saved settings.

Real stores now start with global 14-day lead time and seven-day safety buffer, with no example supplier/category overrides. Previously an unsaved store could inherit fixture overrides that disappeared on its first save, changing recommendations without a visible settings change. Saved customer overrides and explicit demo fixtures remain intact. The inactive sample-data checkbox is removed while its stored compatibility field is preserved.

Mobile purchasing tables scroll within labeled, keyboard-accessible regions; the page stays within a 390px viewport. Ask Skubase now lives in the header instead of covering Save with a floating launcher. Escape closes the chat and returns keyboard focus to its launcher.

Stockout alert text retains confidence and history limits. One day of sales cannot produce a precise 100% claim in the notification, while the existing risk threshold still controls which estimates are flagged.

Slack and generic webhook forms include a merchant destination guide, save/test/check/enable steps and a selectable synthetic JSON payload for receiver mapping. Slack uses merchant-created incoming webhooks; generic receivers accept the existing subject/body/emitted_at/source envelope. No OAuth connection, new provider account or live destination is implied by this UI change. The operator checked Slack in the browser and reached workspace sign-in; the intended live workspace/channel and webhook service remain required. No merchant Slack/webhook target was changed during verification.

## Verification

Synthetic browser-to-API verification imported a three-unit shipment once, then replayed the same file. The temporary database retained one batch, one receipt and unchanged 93-unit SKU history after replay (90 fixture units plus three newly imported). The browser displayed the no-op outcome. A Stocky upload in the same fixture reported one metadata update and zero new inventory records, with Shopify stock preservation explained. Notification transports in this fixture are replaced; no external test messages or merchant outreach are produced.

The combined suite passed 269 backend tests and 175 frontend tests, typecheck and production build. Mobile browser verification confirmed the page width equals its 390px viewport; Save persisted the actual settings through the real route. An intentionally blocked history request left both confirmed alert channels usable; retry restored activity after the block was removed. Network failures use plain recovery copy instead of internal API URLs. The final deployment build also checks the last mobile-layout and chat-placement adjustments. Deployment identifiers are recorded after rollout.

## Growth evidence

The afternoon research allowance ended at six primary pages, zero new qualified contacts and zero outbound messages (evidence 5330). Shopify Community notifications showed system onboarding/badges, not merchant replies (5332). Two exact Google Workspace setup notices were reviewed and reclassified from UNKNOWN to AUTOMATED, retaining raw messages and prior audit evidence (5333 and 5334). No outreach cohort or rolling-20 ceiling changed; advertising remains disabled.
