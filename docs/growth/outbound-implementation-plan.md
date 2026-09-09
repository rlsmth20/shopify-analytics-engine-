# Dedicated acquisition email implementation

Reuse the existing growth contacts, experiments, messages, first-contact receipt ledger,
durable work queue, evidence and versioned memory. Keep operational Resend email separate.

1. Verify provider terms and sending/inbound APIs against the actual unsolicited B2B
   use case. Do not interpret marketing examples as overriding acceptable-use terms.
2. Finish evidence-backed merchant identity links and the owner's nullable daily ceiling.
   Keep uncertain contacts fenced from retries independently of confirmed-send counts.
3. Add a provider-independent outreach service with persistent send intent, suppression,
   signed unsubscribe, campaign limits, safe test routing and deliverability protection.
4. Connect authenticated provider events and replies to the same merchant/campaign
   history. Schedule restrained follow-ups and prioritize inbound work in the existing worker.
5. Verify replay, failure, concurrency, opt-out, cross-channel identity and safe-test paths.
   Expose readiness and campaign outcomes through owner status and dashboard contracts.
6. Configure a separate outreach subdomain through available DNS access. Preserve primary
   MX and operational mail. Require actual provider approval, owner-approved cost and a
   genuine business postal address before live cold email. Run a limited pilot only after
   those prerequisites and provider test delivery are verified.

No daily contact ceiling is imposed by the owner. Provider rate limits and a separately
configured, explicitly activated pilot remain transport safeguards, not a campaign quota.
Routine deduplication, scheduling, events, metrics and eligibility checks use application
code. The model handles message drafting and genuinely ambiguous replies.
