# Skubase outreach messaging — revision 2

Owner direction, September 7, 2026: make it clear that Skubase is an app, explain how it can remedy the merchant's specific inventory issue, and offer to work with the merchant on unmet needs. Continue outreach beyond the completed first ten-contact batch.

## Message process

1. Identify Skubase as an inventory-planning app for Shopify merchants early in the message.
2. Cite one verified merchant fact or public problem. If the problem is inferred from a storefront, frame it conditionally.
3. Explain one relevant app capability and its practical benefit. A useful diagnostic can introduce the app, but should not obscure why Skubase is contacting them.
4. Where a feature is missing or unverified, say: "If your workflow needs something Skubase doesn't yet support, we can work with you to understand the gap and explore a practical solution." This offers collaboration, not guaranteed custom development or a delivery date. Record the requirement as product feedback.
5. State: "Skubase is currently in Shopify's review process and is not yet listed in the Shopify App Store."
6. Ask one concrete, low-friction question: offer a free check on 5–10 products, or ask for the workflow detail that determines fit. Keep ongoing subscriptions separate from the free check.
7. Use Skubase and info@skubase.io where the channel permits contact details. Do not invent a human identity or claim private store access. Keep affiliation clear. No unsolicited follow-up to recipients promised none.

## Verified capability boundaries

Reviewed `backend/app/services/inventory_engine.py` on September 7:

- Uses recent sales and stock on hand to estimate days of inventory, and lead-time/safety-stock inputs for reorder priorities. Describe how this supports purchasing decisions; do not guarantee elimination of stockouts or accurate seasonal forecasting.
- Flags potential overstock and dead inventory and estimates excess units/cash exposure when input data supports it. Incomplete sales history limits those conclusions.
- Produces prioritized actions and explanations. The merchant retains purchasing control.
- Native Shopify PO-screen changes, partial-receipt repair, inbound-PO reconciliation, supplier-file export and bespoke integrations are not verified by this capability review. Offer to examine the workflow instead of claiming these are already fixed.
- Repository evidence confirms implemented logic, not installation eligibility or performance on a particular merchant's data. Review status must remain explicit.

## Example for a merchant reporting slow stock

"Skubase is an inventory-planning app for Shopify merchants. It uses sales and stock data to flag potential slow/dead stock and estimate how much inventory may be tying up cash, helping you decide what to review before buying more. If your workflow needs something Skubase doesn't yet support, we can work with you to understand the gap and explore a practical solution. Skubase is currently in Shopify's review process and is not yet listed in the Shopify App Store. Would a free check on 5–10 products be useful?"

Adapt the example to the actual evidence and channel. General app offers belong in Shopify Community's Ask & Offer area; responses elsewhere must address the discussion and follow current rules. Do not paste this example repeatedly into threads.

## Experiment and continuation

Revision 2 is an owner-directed message change, not a proven conversion winner. Preserve the first ten contacts and their original messages as revision 1 and keep batch2 separately attributed. The latest [continuous-operation policy](continuous-operation.md) replaces lifetime contact caps with a hard ceiling of twenty new merchants per rolling 24 hours, not a target. At most three new contacts and six decision-focused source reads per wake; prefer stored opportunities to repeated searches. Replies and three available free-check slots take priority. Reserve durable capacity before each new contact. Preserve $0 advertising and existing channel restrictions. Record revision, evidence, exact sent message, receipt and response for every action. Broader segment changes confound comparisons, so do not claim causal uplift from raw response rates or rewrite positioning after a handful of sends.
