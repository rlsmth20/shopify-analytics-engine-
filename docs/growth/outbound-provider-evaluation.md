# Outbound provider evaluation

Reviewed 2026-09-09. This is a provider-selection record, not evidence of an approved account, a completed integration, or a successful live send.

## Decision

**EmailPal is the best technical candidate examined, conditional on written confirmation of Skubase's contact-sourcing workflow and account verification.** Build its documented adapter in safe test mode; do not mark production cold sending approved yet. Its acceptable-use policy explicitly permits targeted unsolicited B2B email, but prohibits website/directory/social-network harvested lists. Skubase discovers merchant contact details from public websites, so that sourcing condition must be resolved honestly with the provider. A marketing claim that cold email is allowed does not override a sourcing restriction. [EmailPal acceptable use](https://www.emailpal.io/legal/acceptable-use)

EmailPal manually verifies accounts before sending. Use only a Skubase-owned sending subdomain, with a monitored mailbox and accurate business identity; avoid leased/recycled inboxes, whose addresses can later pass to other customers. Provider approval does not replace recipient-jurisdiction requirements. [EmailPal terms](https://www.emailpal.io/legal/terms)

The advertised Starter plan is **$69/month**, including 50 mailboxes, API access, bring-your-own domains, and 500 instant verification checks daily. Additional warming/overage can cost more. No purchase has been authorized or made; the earlier OpenAI budget is unrelated. Check the actual account quote before purchase. [EmailPal pricing](https://www.emailpal.io/#pricing)

## Alternatives examined

| Provider | Terms and API finding | Decision |
| --- | --- | --- |
| Mailreef | Terms §27.1 require express permission from recipients, despite cold-email marketing. | Reject for unsolicited acquisition under the public terms. [Terms](https://www.mailreef.com/terms-of-service) |
| Mailreef | Actual HTTP send endpoint exists; public pricing is $249/month plus $0.001/send for monthly service, or $240/month with a 12-month commitment. | Poor startup cost even if a written contract exception were obtained. [Pricing](https://www.mailreef.com/pricing), [send API](https://mailreef.readme.io/reference/send-an-email) |
| Mailforge | §3.4.1 explicitly permits lawful unsolicited B2B, but the same section later reserves termination for mail to recipients who did not ask. | Written clarification needed; do not silently resolve the contradiction in our favor. [Terms](https://www.mailforge.ai/terms) |
| Mailforge | $3/mailbox/month with a minimum of 10 slots: $30/month inferred minimum before extras/tax. Its public API provisions infrastructure; it is not the campaign sender. | Conditional SMTP/IMAP fallback only, not a verified HTTP sending API. [Pricing](https://www.mailforge.ai/pricing), [official API guide](https://www.mailforge.ai/blog/mailforge-api) |
| Infraforge | Same internal sending-policy contradiction as Mailforge. | Written clarification needed. [Terms](https://www.infraforge.ai/terms) |
| Infraforge | Minimum 10 slots at $4/mailbox/month with quarterly billing; its published API manages mailboxes/domains, not sends, and has no public webhook contract. | Higher cost and extra transport work. [Pricing](https://www.infraforge.ai/pricing), [API guide](https://www.infraforge.ai/blog/infraforge-api), [Swagger](https://api.infraforge.ai/public/swagger/index.html) |
| SMTPmart | Current terms require permission-based sending; endpoint documentation is available only after account setup. | Reject for this unsolicited use case. [Terms](https://smtpmart.com/legal/terms), [developer documentation](https://smtpmart.com/docs) |
| SMTP2B | No verifiable official email-provider documentation located in the bounded search. | Unverified; do not invent an adapter or provider approval. |

Earlier project evaluation also rejected Resend, Mailgun, SendGrid and SMTP2GO for opt-in restrictions. AgentMail's cold-outreach examples conflict with its prohibition on unsolicited messaging; it is not an approved fallback.

## EmailPal adapter contract

Source of truth: [official OpenAPI schema](https://www.emailpal.io/api/public/v1/openapi.json).

- Base: `https://www.emailpal.io/api/public/v1`; `Authorization: Bearer <secret>`.
- `POST /inbox/send`: `Idempotency-Key`; JSON `mailbox_id`, `to` array, `subject`, `body`. Optional `reply_to_id`, or `in_reply_to` plus `references` for externally known threads.
- `202` returns `id`, `job_id`, `poll`. This acknowledges queueing, not sending.
- `GET /inbox/send/{id}`: `status`, `sent_at`, `rfc_message_id`, separate `delivery_status`, `bounce_type`, `smtp_code`, `delivery_at`.
- `GET /inbox/{id}`: sender, `message_id`, `in_reply_to`, `thread_key`, `body.text`; may initially return `202` while fetching.
- `GET /suppressions?address=...` checks address and domain suppression. `POST /suppressions` accepts either `address` or `domain`, plus `reason`.
- `POST /domains`: `mode: connect`, `domains: [outreach.skubase.io]`, `dns_method: manual`. Read issued records from `GET /domains/{id}`; request `verify_dns` afterwards. Subdomain acceptance still needs live verification.
- `POST /verify`: `email`; do not override unsafe/suppressed results.

### Events and receipts

Register `POST /webhooks` with HTTPS `url`, explicit events and a description. Store the returned secret directly in secret infrastructure. Verify `EmailPal-Signature` using the hex HMAC-SHA256 of the timestamp, a period, and the original raw body. Check timestamps within five minutes and compare signatures in constant time. Persist event IDs before acknowledging; event delivery is at least once. Relevant events are `message.received`, `message.delivery_updated`, `job.succeeded` and `job.failed`. Inbound events contain metadata and previews; fetch bodies through the inbox API. A succeeded send job means the provider MTA accepted the message, not that it reached the recipient. Delivery events report the later outcome. [Official API documentation](https://www.emailpal.io/docs)

## Activation blockers and next step

Complete local safe-mode tests and the internal queue, suppression, reply, follow-up and audit integration without waiting for credentials. Keep production cold sending disabled until all of these have concrete evidence:

1. Provider confirms whether individually researched merchant business addresses published on their own sites are permitted, including AI-assisted collection. Do not relabel scraping as manual sourcing to bypass the rule.
2. Provider account passes its review; price/charge is approved and credentials exist.
3. Owner supplies the real business postal address, unless a verified one is found in existing configuration.
4. Provider-issued records for the Skubase-owned subdomain are installed and verified without changing primary-domain MX records.
5. Approved-address safe tests, inbound replies and provider receipts pass before a limited live pilot.

Do not fabricate DKIM values or use a generic example as a production DNS record. Do not create leased addresses, purchase extra mailboxes, enable paid warming, or increase volume because an API endpoint allows it.

## Follow-up: alternative after EmailPal onboarding failures

The integration operator reported a bounced message to EmailPal's published support address and a failed Google sign-in. Therefore EmailPal remains an unactivated candidate; its public documentation alone does not prove operational readiness.

**Inframail has the clearest compatible sending terms among the additional alternatives examined.** Its AUP explicitly accommodates unsolicited communications when they identify the company, provide an opt-out, are relevant to the recipient, and use business rather than personal addresses. Its terms prohibit unlawful spam rather than requiring universal opt-in. [Inframail AUP](https://www.inframail.io/aup), [terms](https://www.inframail.io/tos)

There is a concrete domain limitation: **Inframail does not support bringing subdomains.** It could serve Skubase only on a separate Skubase-owned root domain, unless the provider supplies a supported exception. Do not migrate the operational `skubase.io` domain to work around this limitation. Direct .com registration is advertised at $16.44/year. [Domain eligibility](https://help.inframail.io/domains-you-can-buy-or-migrate-to-inframail-pmqdd)

The advertised entry plan is $147/month. The terms specify a 28-day billing cycle, or 13 invoices per year, so treat the price as $147 per cycle pending the checkout quote. Bringing an existing root domain adds $5 once. This is materially more than a small startup mailbox needs; request a smaller pilot quote before purchasing. [Current plans](https://www.inframail.io/), [billing terms](https://www.inframail.io/tos)

The documented transport is standard TLS SMTP/IMAP, compatible with a Skubase-operated sending service; no third-party campaign SaaS is required. Read the issued host/port/password from the account export, rather than guessing Office 365 settings from a blog. The public API documentation covers mailbox provisioning, not message sending or signed delivery webhooks. A Skubase adapter would need SMTP acceptance receipts, IMAP reply/bounce polling, and durable uncertainty handling. [Transport compatibility](https://help.inframail.io/what-email-platforms-work-with-inframail-7w793), [API scope](https://help.inframail.io/how-to-find-and-access-inframail-s-api-documentation-afb0b)

The public signup route is [app.inframail.io](https://app.inframail.io/); published support is `support@inframail.io`, with an Intercom support route. This research did not create an account, test support delivery, buy anything, or verify sending. Request confirmation of public-business-address sourcing, the smallest pilot quote, root-domain ownership and the actual transport before activation. [Support information](https://help.inframail.io/frequently-asked-questions-faq-about-inframail-hzp72)

Maildoso's [official targeted B2B guidance](https://intercom.help/maildoso/en/articles/16440085-what-are-the-guidelines-for-sending-targeted-automated-b2b-cold-emails-using-maildoso) allows automated outreach to verified relevant corporate addresses with unsubscribes. However, its [terms](https://maildoso.ai/resources/terms-of-service) contain broad nonconsensual-data-harvesting language, and owned subdomain support was not established. Its SMTP starting plan is advertised at $75/month; `help@realmaildoso.com` and website chat are documented contact routes. [Maildoso product/pricing](https://maildoso.ai/)

ColdMail was excluded from this follow-up because its infrastructure is Google Workspace mailboxes, contrary to the requested dedicated non-Gmail unsolicited transport. [ColdMail product](https://www.coldmail.app/)
# Live setup findings — September 9, 2026

A setup inquiry sent from the approved business mailbox to EmailPal's published
support@emailpal.io address was accepted by Gmail, then bounced with “Address not
found.” No merchant was contacted. Google sign-in with info@skubase.io returned
`login?error=oauth` with “Google sign-in did not complete.” No paid subscription,
provider API credential, verified sending domain or successful support ticket was
created. These additional reliability blockers mean EmailPal remains a conditional
adapter, not an approved production provider. Do not purchase or activate it until
the sourcing-policy and account-access questions are resolved.
