# Google Workspace acquisition email

The owner's latest instruction selects the existing business Google Workspace
mailbox, **info@skubase.io**. Use its authenticated Chrome Gmail session. Never
use the personal Gmail connector or another signed-in account. EmailPal activation
is superseded; do not purchase a subscription or continue its setup work.

Open the retained business mailbox URL `https://mail.google.com/mail/u/4/`,
verified as info@skubase.io on September 13. The generic Gmail homepage and
`/u/0/` can open a personal account. If the wrong account appears, do not inspect
its messages or send from it: navigate to the retained business URL and verify
the visible account identity. If that index has changed, select info@skubase.io
from Google's account chooser. A wrong initial tab is recoverable within the
same task; only missing business access or an actual login barrier is a blocker.
Never rely on the numeric account index alone as sender verification.

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
   Include the assigned `contact_id` and preserve that contact's exact `identity`.
   Reservation lookup uses `identity`; changing an assessed email identity to a
   store domain can create a second contact and detach receipt recovery from the
   assigned task. Read the retained assessment/history to recover the exact
   identity. Do not create a new identity or reassess to work around an identity
   mismatch. Link verified aliases with `prospect-link` when needed.
3. Retain the successful `reservation_id` and `email` response. Do not repeat
   `outreach-reserve` to confirm success or retrieve the same response. Poll a
   running shell session using its returned session ID. A duplicate error from an
   accidental second call does not undo the first reservation. Check its current
   history before proceeding; only a still-valid, unattempted pending reservation
   can continue to composition. Uncertain or sent messages must never be retried.
   The CLI also saves the exact successful response to its returned `result_file`,
   `.growth-deploy/outreach-reservation-<reservation_id>.json`. If tool output seems
   missing, read that file with Get-Content -Raw and ConvertFrom-Json before giving
   up. It contains the exact email body and HTML; do not reconstruct them or reserve
   again. A saved response is not proof of current eligibility or of a send: current
   suppression, expiry, authorization and receipt checks still apply. If the file
   is absent, retain uncertainty rather than inventing its contents.
   Use the returned `email` object exactly. It adds a separate Rainer signature, the configured business name,
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
   The returned deadline field is `submit_before` (UTC Unix seconds). A successful
   response containing that field is a usable authorization; do not report it as
   missing. Run authorization as its own command, after recording the monitor,
   with a 30-second command wait. If the command returns a session ID, poll that
   same session promptly; do not issue another authorization. The CLI retains
   the exact result at `.growth-deploy/outreach-authorization-<reservation_id>.json`.
   If stdout is missing, read that exact file immediately, not a directory listing
   or prospect-history call. The input JSON is not the authorization result.
   Use the returned `submit_before` unchanged and click once before it expires;
   successful authorization is expected to mark the message `sending` before
   the click. That state alone is not evidence that an external send occurred.
   If the deadline expires before the click, record the actual no-click
   observation and let receipt recovery release the unused admission.
5. Open the actual Gmail Sent conversation and match recipient, subject and body.
   Complete with `outcome=sent` and its exact Gmail thread URL as `receipt`.
   A draft, generic inbox URL or success assumption is not a receipt. If uncertain,
   retain `outcome=uncertain`; never retry to determine whether it was sent.

Formatting correction applies to new unsent drafts. Preserve sent messages as
history; do not resend Earth & City merely to improve its formatting. Aim for
70-110 words before the signature/footer, one or two short sentences per paragraph,
one relevant benefit and one standalone question. Keep the required affiliation
and current Shopify review disclosure without a lengthy feature list.

The first real merchant send starts the persistent ramp. On September 16 the owner
set **16 actual first-contact emails per Pacific day**, replacing the earlier 8.
This current operating level can advance to 20 with healthy sending evidence,
elapsed time, authentication and fresh monitoring. Replies are not prerequisites.
One isolated bounce suppresses its recipient without freezing the mailbox ramp.
Meaningful aggregate deterioration and serious reputation signals still pause
increases. See `email-ramp.md` for the deterministic criteria.
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
Check the merchant's `prospect-history` before treating an old failure as new.
Once an invalid recipient is permanently suppressed, its retained bounce notice
does not block other merchants. Keep the negative delivery signal and the pause
on ramp increases. Distinguish `ramp.increase_paused` from transport `ready` and
`blockers`: a pause on raising volume is not a global send pause. Escalate actual
provider restrictions or systemic delivery deterioration; do not clear them.

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
