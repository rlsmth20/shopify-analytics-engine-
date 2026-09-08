# Skubase outreach messaging — revision 4

Current qualification policy: **market_discovery_v1** supersedes all older
public-pain/perfect-ICP requirements below. A basic eligible Shopify merchant can
be contacted with unknown inventory pain, SKU count and revenue. Cite a verified
store/product fact, describe a supported benefit and ask whether inventory or
reordering is currently a problem. Do not imply it is known. Copy remains revision
4; retain qualification_policy=market_discovery_v1 in immutable cohort attribution.
MEDIUM fit/confidence is sufficient. Keep suppression, relevance and channel rules.

Owner direction, September 8, 2026: remove unnecessary negative caveats from
advertising. Lead with the merchant's verified issue, the relevant Skubase
capability and its benefit, then one concise offer. Do not add statements such as
"it cannot predict every sudden demand spike" to an introductory pitch. Accuracy
comes from making supported claims; it does not require listing everything the
app cannot do. Explain a limitation when answering a specific requirement or when
omitting it would make the actual offer misleading. Keep the owner-requested
Shopify review / not-yet-listed disclosure and avoid guaranteeing outcomes or
unbuilt functionality.

Use revision 4 for future messages. Preserve all already-sent text, receipts and
revision 3 cohorts. This is an owner-directed copy adjustment, not a measured
conversion improvement. Keep the offer and qualification standards stable; new
admissions must retain the new message version and separate experiment attribution.
Earlier directions below remain applicable except where this update supersedes
their copy-version instructions. Capability boundaries below guide claim checking;
they are not a checklist of disclaimers to insert into advertising.

Owner direction, September 8, 2026: make the promotional purpose unmistakable
and respond to relevant participants throughout a discussion, not only its
original poster. Retain previously published messages and their attribution.

Open with a brief disclosure such as **"Skubase promotion:"**, then explain the
specific app capability that addresses the participant's own stated workflow.
Do not bury the commercial purpose in a footer or disguise an app offer as
independent advice. Keep the reply useful and contextual; disclosure does not
permit generic advertisements, prohibited links or thread hijacking.

A comment describing the participant's own store, desired inventory capability
or purchasing problem may support a first contact. A store URL or merchant badge
is not mandatory for a low-friction public reply. Do not exclude someone merely
because they are not the original poster or have mostly posted replies. Record
their verified public statement, label unknown business details UNKNOWN, and
distinguish an outreach prospect from an acquired qualified user. Disclosed
vendors, unrelated advice and unsupported fit remain exclusions. Every new
participant still requires admission, duplicate/suppression checks and counts
against the shared rolling cap.

Use revision 3 and separate cohort attribution for future messages. The owner
requested both clearer promotion and broader participant consideration; this is
not evidence of conversion uplift and cannot isolate either change's effect.
The September 7 direction below remains part of the current message process;
revision 3 adds explicit promotional disclosure and broader participant coverage.

Owner direction, September 7, 2026: make it clear that Skubase is an app, explain how it can remedy the merchant's specific inventory issue, and offer to work with the merchant on unmet needs. Continue outreach beyond the completed first ten-contact batch.

## Message process

1. Start with explicit promotional disclosure and identify Skubase as an inventory-planning app for Shopify merchants.
2. Cite one verified merchant fact or public problem. If the problem is inferred from a storefront, frame it conditionally.
3. Explain one relevant app capability and its practical benefit. A useful diagnostic can introduce the app, but should not obscure why Skubase is contacting them.
4. Where a feature is missing or unverified, say: "If your workflow needs something Skubase doesn't yet support, we can work with you to understand the gap and explore a practical solution." This offers collaboration, not guaranteed custom development or a delivery date. Record the requirement as product feedback.
5. State: "Skubase is currently in Shopify's review process and is not yet listed in the Shopify App Store."
6. Ask one concrete, low-friction question: offer a free check on 5–10 products, or ask for the workflow detail that determines fit. Keep ongoing subscriptions separate from the free check.
7. Use Skubase and info@skubase.io where the channel permits contact details. Shopify Community replies must not include email/contact details or external promotional links; keep the initial conversation public. Do not invent a human identity or claim private store access. No unsolicited follow-up to recipients promised none.

## Verified capability boundaries

Reviewed `backend/app/services/inventory_engine.py` on September 7:

- Uses recent sales and stock on hand to estimate days of inventory, and lead-time/safety-stock inputs for reorder priorities. Describe how this supports purchasing decisions; do not guarantee elimination of stockouts or accurate seasonal forecasting.
- Flags potential overstock and dead inventory and estimates excess units/cash exposure when input data supports it. Incomplete sales history limits those conclusions.
- Produces prioritized actions and explanations. The merchant retains purchasing control.
- Native Shopify PO-screen changes, partial-receipt repair, inbound-PO reconciliation, supplier-file export and bespoke integrations are not verified by this capability review. Offer to examine the workflow instead of claiming these are already fixed.
- Repository evidence confirms implemented logic, not installation eligibility or performance on a particular merchant's data. Review status must remain explicit.

## Example for a merchant reporting slow stock

"Skubase promotion: our inventory-planning app for Shopify merchants uses sales and stock data to flag potential slow/dead stock and estimate how much inventory may be tying up cash. That helps you decide what to review before buying more. If your workflow needs something Skubase doesn't yet support, we can work with you to understand the gap and explore a practical solution. Skubase is currently in Shopify's review process and is not yet listed in the Shopify App Store. Would a free check on five regularly restocked products be useful? No purchase obligation; ongoing app subscriptions are separate."

Adapt the example to the actual evidence and channel. General app offers belong in Shopify Community's Ask & Offer area; responses elsewhere must address the discussion and follow current rules. Do not paste this example repeatedly into threads.

## Experiment and continuation

Revision 3 is an owner-directed change, not a proven conversion winner. Preserve the first ten contacts and their original messages as revision 1, batch2 as revision 2, and the [September 8 cohort](campaign-2026-09-08.md) as revision 3. The latest [continuous-operation policy](continuous-operation.md) replaces lifetime contact caps with a hard ceiling of twenty new merchants per rolling 24 hours, not a target. At most three new contacts and six decision-focused source reads per wake; prefer stored opportunities to repeated searches. Replies and three available free-check slots take priority. Reserve durable capacity before each new contact. Preserve $0 advertising and existing channel restrictions. Record revision, evidence, exact sent message, receipt and response for every action. Broader segment changes confound comparisons, so do not claim causal uplift from raw response rates or rewrite positioning after a handful of sends.
