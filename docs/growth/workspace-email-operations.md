# Google Workspace acquisition email

The owner's latest instruction selects the existing business Google Workspace
mailbox, **info@skubase.io**. Use its authenticated Chrome Gmail session. Never
use the personal Gmail connector or another signed-in account. EmailPal activation
is superseded; do not purchase a subscription or continue its setup work.

The internal browser send ledger enforces email ramp, merchant deduplication,
suppression and one-use authorization. It stores the complete subject, recipient,
body, source, campaign and Gmail receipt alongside other merchant interactions.
The existing receive-only mailbox bridge continues reply ingestion and opt-outs.
Operational email remains separate. Do not use the dormant dedicated-provider
`email-queue` path for Workspace messages.

For each relevant, individually reviewed first contact:

1. Read `email-status`, merchant history and fresh business inbox safety evidence.
   Verify the actual signed-in sender is info@skubase.io. Check current channel rules
   and the published business contact route. Do not use Google for unsolicited mass
   mail or bypass provider restrictions. A small ramp is not permission for spam.
2. Call `outreach-reserve` with the existing merchant/qualification/experiment
   fields, `channel=email`, `recipient`, `subject` and `email_source` containing
   the actual published business-contact URL. Include stable cohort labels.
   The required `facts` field is an array of objects, not an assessment ID,
   string, or dictionary. Reuse the verified public fact from the task:
   `"facts": [{"text": "<verified merchant fact>", "source": "<public URL supporting that fact>", "verified": true}]`.
   Keep the existing assessment; a payload-format correction does not require
   new merchant research. See the browser send payload fields in
   `executor-instructions.md` before constructing this request.
3. Use the returned `email` object exactly. It adds a separate Rainer signature, the configured business name,
   owner-supplied mailing address and reply-unsubscribe footer. Do not duplicate
   that footer in the proposed body. Keep one inventory question and no em dashes.
4. **Preserve the layout:** focus the Gmail message body and paste the returned
   `email.html_body` with `tab.paste(html, {format: "html"})`. Do not use
   `setValue` for Gmail's rich-text message body: it collapsed real line breaks in
   the Earth & City email. Subject/recipient inputs may still use `setValue`.
   If HTML paste is unavailable, enter each line with actual Return key events;
   use two Returns for paragraph gaps. Do not replace newlines with spaces.
   Inspect a screenshot of the actual draft before authorizing. It must show
   short separated paragraphs, the question on its own, a separate signature,
   address and opt-out line. An accessibility text dump alone does not prove layout.
   Verify sender, recipient, subject and complete body against the reserved text.
   Immediately before Send, call `outreach-authorize` with the reservation ID.
   Click once within its 30-second deadline. An expired authorization cannot be reused.
5. Open the actual Gmail Sent conversation and match recipient, subject and body.
   Complete with `outcome=sent` and its exact Gmail thread URL as `receipt`.
   A draft, generic inbox URL or success assumption is not a receipt. If uncertain,
   retain `outcome=uncertain`; never retry to determine whether it was sent.

Formatting correction applies to new unsent drafts. Preserve sent messages as
history; do not resend Earth & City merely to improve its formatting. Aim for
70-110 words before the signature/footer, one or two short sentences per paragraph,
one relevant benefit and one standalone question. Keep the required affiliation
and current Shopify review disclosure without a lengthy feature list.

The first real merchant send starts the persistent ramp. The initial ceiling is
five actual first-contact emails per Pacific day, increasing through 8, 12, 15 and
20 only with the existing elapsed-time and delivery/reply evidence requirements.
Internal diagnostics do not start the clock. Reaching the email ceiling does not
stop replies, research or other permitted channels. Do not manufacture warming.

Prioritize genuine replies in their existing Gmail conversation. Retain inbound
and outbound text, contact/message identity and receipt in the operator evidence.
Do not count engaged replies as new first contacts. Never send canned follow-ups
after a human reply. Read-only inbox monitoring and the existing receiving bridge
continue independently. Apply `email-suppress` immediately to the actual merchant
address for opt-outs, declines and verified hard bounces; never retry a failed
address or bypass suppression using another channel. When a delivery daemon sends
a failure, identify the failed recipient from the delivery report, not its sender.

Authentication was verified by an actual received internal diagnostic with SPF,
DKIM and DMARC passing (evidence 22221). Existing Google MX and operational records
remain intact. Unused EmailPal subdomain records are historical setup, not an active
sending transport. No additional provider subscription is enabled.

Selection is versioned in `strategic/email_transport`; footer identity reuses
the existing configured business information. Paid-provider API dispatch stays
disabled. The executor receives a bounded live email readiness/ramp snapshot on
each claimed task. No new scheduler or separate campaign tool is required.

Reference: [Google Workspace acceptable use policy](https://workspace.google.com/terms/use_policy/).

The executor defers pending first-contact tasks declaring `channel=email` until
the next Pacific-day reset when the email ramp is full. Include that explicit
channel field in send-task decisions. Deferral does not consume a model turn,
retry, reservation, or acquisition count. Genuine replies and existing receipt
recovery remain executable. Future-dated email work does not prevent the planner
from replenishing other permitted acquisition channels.
