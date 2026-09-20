# Reorder and purchase-order validation

## September 20 owner override: second cohort open

The owner explicitly requested: "Unpause it. Create a new 50 person cohort."
The active enrollment is now `reorder-po-validation-v2`: a separate batch of 50
new merchants using the same ICP, offer, CTA and `reorder_po_v1` message family.
Use the experiment ID and canonical labels in live `strategic/focused_validation`,
and use the active campaign in attribution URLs. The first cohort stays at 50,
under observation; its September 26 response window does not block this batch.
This is an owner-authorized continuation, not evidence the first batch succeeded.
Keep the 16-email Pacific-day allowance and all suppression, duplicate and
uncertain-contact protections. Review the new batch at 50; do not create unlimited
additional batches. The original experiment details below remain historical.

Owner direction, September 16, 2026. This supersedes volume-first acquisition and
generic inventory-health-check first-contact copy for this phase. Historical
messages and outcomes remain unchanged. The 171-contact baseline has one verified
substantive/positive response and no verified attributed customer or MRR. That is
weak performance, not proof of no demand. Anshul's response (evidence 35118)
specifically valued reorder recommendations with Excel PO export.

## Shopify review update, September 16

Shopify suspended review reference 116756 until September 30 because checkout used
the Billing API while App Pricing was enabled. Partner pricing now uses manual
Billing API pricing, matching the deployed checkout. The owned development store
reached Shopify's test-charge approval page (evidence 127124); no charge was
approved. The suspension still requires resubmission after its end date.

Use this concise current disclosure: "Skubase is not yet listed in the Shopify
App Store." Do not claim review is actively progressing. This handled review
incident is not a mailbox restriction and must not repeatedly create a global
channel hold. Keep the review evidence and resubmission obligation separate.

## Fixed experiment

- Campaign: `reorder-po-validation-v1`. Use the real ID in the live packet.
- ICP: Shopify merchants with meaningful physical inventory complexity. Multiple
  lines, variants, replenishable goods or purchasing requirements are sufficient
  signals. Optional unknowns are neutral. No deep research or public-pain gate.
- Offer: reorder recommendations plus exportable purchase orders.
- CTA: “Would you be interested in seeing what Skubase recommends for your store?”
- One message family: `reorder_po_v1`. Use the supplied `cohort_labels` verbatim.
- Primary channels: email and genuinely relevant Shopify Community answers.
- Keep first-contact enrollment bounded at 50 confirmed merchants. Uncertain,
  pending, failed and internal test messages never enter that denominator.

The send service freezes cohort labels. Industry, source, verified facts, exact
wording, confidence and CTA phrasing remain receipt metadata, not new cohort
dimensions. Channel separates the two cohorts. Do not rewrite the historical 138
groups or pretend their different offers were this experiment.

## Message and channel execution

Use one cheap verified fact, one direct description of reorder recommendations and
exportable purchase orders, then the single CTA. Short paragraphs. No em dashes,
invented pain, private-inventory claims, generic AI language, feature laundry
lists, meetings or needless negative caveats. Preserve required sender, postal,
opt-out and current verified Shopify review disclosures.

Example structure, personalize only the first sentence using verified evidence:

> Hi [Name], I noticed [one verified fact about Store's products].
>
> I work with Skubase. It recommends what to reorder and lets you export purchase
> orders, helping turn your next buying decision into an order you can send.
>
> Would you be interested in seeing what Skubase recommends for your store?

Use existing concise disclosures/footer, not another CTA. Public answers must
solve the actual question even with the Skubase reference removed. Mention the
offer only when directly relevant; disclose affiliation. Don't post to meet a quota.

Email remains subject to its live ramp and actual provider conditions. When email
is capped, discover and prepare email prospects, handle replies, or find useful
Shopify Community questions. Do not replace exhausted email capacity with a flood
of forms. Retain form opportunities and existing receipts; the form transport is
still available for later experiments. Existing conversations outrank enrollment.
Never retry uncertain contacts or rewrite an already authorized body.

## Attribution

When a Skubase link is included, link the product name using:

`https://www.skubase.io/?utm_source=CHANNEL&utm_medium=outreach&utm_campaign=reorder-po-validation-v1&utm_content=outreach-CONTACT_ID`

Use the actual contact ID from prospect assessment, `email` or `shopify_community`
as CHANNEL. No email/address in URLs. The product-name link is not a second CTA.
Email draft bodies are plain text: use a readable plain URL, never HTML anchor
markup. The Workspace transport handles the email formatting.
Use the same tags on relevant existing product/health-check paths in substantive
follow-up. First-party analytics already preserves tags through navigation.

The projection validates the campaign, channel and confirmed send before crediting
a tagged visit. Authenticated sessions can then associate verified product events
with that outreach. This is link attribution, not proof of the visitor's merchant
identity: public/forwarded links and scanners are limitations. Never merge prospect
identities based on a URL. Account-email matching remains available. Unrecoverable
historical attribution stays UNKNOWN. Payment still requires verified payment.

## Decision and continued execution

At 25 contacts inspect early signals; do not rewrite on a tiny sample. At 50 pause
only enrollment in this experiment, not the agent. Target at least 3 substantive
replies, 2 positive replies and 1 verified health-check request, Shopify connection
or strong activation. Genuine strong signals or severe negative delivery evidence
justify earlier review. Allow the last contact seven days to respond before
treating silence as negative; this does not require idle time or stop conversations.
The executor schedules a leased Gmail/retained-Reddit inbox check when the prior
check is three hours old, even with enrollment closed. Completed
checks require fresh browser evidence. Prepared first-contact tasks remain queued
and are excluded before the bounded work selection, so they cannot hide replies,
receipt reconciliation or discovery behind a full send backlog.

The persistent acquisition review and scheduled strategic review receive the
focused results. On the checkpoint, verify reply coverage/delivery, identify the
failed stage, and either extend a promising experiment by one bounded cohort or
change exactly one major variable (offer, ICP, channel or positioning) in a new
version. Preserve predecessor results and record rationale/evidence. Do not ask
the owner to interpret routine results or restart acquisition. Do not send hundreds
more of a 0–1-response proposition. Never invent a conversion to reach a threshold.

Report customers, MRR, substantive/positive replies, health checks/connections,
confirmed contacts, response rates, strongest channel/offer, bottleneck and next
decision. UNKNOWN means unavailable. Discovery and sends alone are not success.
