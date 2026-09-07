# Continuous growth and first-contact ceiling

Owner policy, September 7, 2026: operate persistently with a **hard ceiling of 20 new merchants per rolling 24 hours**, never a volume target. This replaces the old ten/twenty lifetime campaign caps and the temporary overnight stop. Apply the shared ceiling conservatively across email, business forms and individually addressed public replies. A public broadcast is not twenty contacts. Legitimate replies to engaged merchants and narrowly requested services do not consume first-contact capacity.

The Railway worker continuously handles inexpensive observation, inbox ingestion, classification, delivery failures, requested service, experiments and funnel work. The Codex operator wakes every two hours for bounded qualified outreach and obligations; it performs the deeper executive review once per day after 9 a.m. Pacific. Desktop/Codex availability is necessary for browser actions. Reaching capacity never pauses the worker or the operator's independent work.

Priority: substantive replies and requested health checks → suppression/delivery failures → product/funnel problems → experiment evaluation → qualified prospect preparation and permitted organic acquisition. Respect existing no-follow-up promises. No silent-prospect follow-up automation. Suppress declines, opt-outs, bounces and channel restrictions immediately. Advertising remains $0 and no new paid services are authorized. The current Resend integration remains requested-service-only; this limit does not authorize prohibited cold email or bypass via Gmail.

## Required admission before every new merchant contact

Use `scripts/growth-review.ps1 -Action outreach-status` for the current rolling count. Historical sent contacts are imported once with `-Action outreach-backfill`; receipt import timestamps conservatively determine their initial window. This is a database ledger shared with the runtime, not a per-wake counter.

Before clicking any first-contact Submit/Reply/Send, prepare an exact JSON payload in ignored `.growth-deploy/` and run `scripts/growth-review.ps1 -Action outreach-reserve -File <absolute JSON path>`. Required shape:

```json
{
  "identity": "shopify-community:actual-merchant-name",
  "organization": "Verified merchant organization",
  "source": "https://community.shopify.com/t/observed-topic/12345",
  "action_key": "unique-first-contact-key",
  "channel": "shopify_community",
  "channel_rules_source": "URL and concise reviewed rule permitting this specific reply",
  "qualified": true,
  "relevance_evidence": "Verified merchant need, current relevance and supported Skubase capability",
  "facts": [{"text": "One verified public fact", "source": "https://observed-source", "verified": true}],
  "experiment_id": "existing-active-experiment-id",
  "cohort": {"icp": "stable segment label", "offer": "free_inventory_health_check", "message_version": 2},
  "body": "Exact final submitted message"
}
```

Check existing identities, organizations, email aliases and source history first; reuse the merchant's canonical identity across channels. Storefront fit alone does not establish a strong inventory prospect. Do not claim unobserved pain or private data access. Use [messaging revision 2](outreach-messaging.md), one sourced fact, one question/offer, honest feature limits and the Shopify App Store review disclosure. Keep messages concise.

A successful reservation supplies an ID and a ten-minute submit-before timestamp. **Only that invocation may submit that exact message once.** A retry or duplicate reservation does not permit another submission. If blocked by capacity or eligibility, do other work. If the deadline passes before submission, do not send: retain it for reconciliation. Never bypass the gate because a script or database is unavailable.

After verified submission, run `-Action outreach-complete -File <JSON path>` with `reservation_id`, `outcome: "sent"` and the exact provider/publication/form receipt in `receipt`. For an uncertain result use `outcome: "uncertain"`; never retry the external send. Record the full message and evidence in the campaign ledger too. Form success means form accepted, not delivered email or readership. Unresolved reservations retain capacity even after 24 hours until explicitly reconciled; there is deliberately no automatic timeout release. Previously contacted merchant identities remain blocked permanently for first contact.

Do not use the old ledger importers for new sends: they record after the action and cannot reserve capacity. They are historical import tools only. Successful sends release rolling capacity 24 hours after their recorded send time; an unresolved intent keeps its slot. A lower internal research/send-per-wake bound is allowed; never increase the hard ceiling automatically.

For a verified failure before any external effect, retain an `OUTREACH_NOT_SENT_VERIFIED` evidence record from `owner_operator`, subject equal to the reservation ID, with `no_external_effect: true` and the concrete verified reason. Then `outreach-reconcile` accepts a JSON containing `reservation_id` and `evidence_id`. It releases that slot with an audit record and invalidates the old reservation. An uncertain outcome, timeout or accepted/delivered message cannot use this path. A bounce still counts as an attempted first contact and suppresses the recipient.

## Learning and cohort stability

Keep the two existing campaign cohorts and original messages. Every new admission snapshots experiment, ICP segment, offer, message version, qualification and fact sources. Do not change positioning after a handful of sends or mix versions without attribution. Requested-service comparisons require at least ten contacts per arm with seven days of observation and posterior superiority of at least 0.95 before changing future allocation. Strong negative evidence can justify an earlier stop, never an automatic increase in send volume.

Before recommending a higher ceiling, report delivered/bounced denominators, substantive reply rate, positive interest, signup, Shopify connection, activation and paid conversion separately by segment and offer/version. Keep missing or unlinked outcomes UNKNOWN. Preserve delivery status separately from public publication/form acceptance. A recommendation requires a mature cohort and reliable outcome linkage; the cap can only change after explicit owner authorization and an audited implementation change.

When an experiment ends, evaluate its observation window and open obligations. Continue research and existing conversations. A subsequent experiment may use the same stable offer/ICP; create new attribution when a variable changes. Neither a cohort boundary nor the 20-contact ceiling is an instruction to stop the persistent mission.
