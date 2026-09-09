# Email ramp and mailbox audit

## Implementation plan

Reuse the existing durable Message/FirstContact ledger, dispatch transaction lock,
provider event processing and versioned memory. Add a deterministic sender-scoped
ramp at the final email send boundary. It counts confirmed first contacts only;
drafts, uncertainty, test sends, replies and non-email channels are separate.
Persist stage changes and observe actual deliveries before increasing. Defer a
capacity-limited draft until the next permitted day without consuming retries.
Keep provider setup and the limited initial pilot prerequisites intact.

## September 9 mailbox inspection

Inspected the signed-in **info@skubase.io** business Gmail directly. The connector
is linked to a personal mailbox and was not used to read mail.

- All-mail search (`in:anywhere`) returned 11 conversations, including spam/trash.
- Sent view returned 7 conversations: September 6 (2), September 7 (1),
  September 8 (3), September 9 (1). Six are internal application/setup checks;
  one is the EmailPal support inquiry. Conversation counts are not campaign sends.
- September 6 welcome and Workspace subscription messages support a recent setup
  date. Exact account creation time remains unknown without Admin access.
- The provider support inquiry bounced with address-not-found. Preserve permanent
  suppression for support@emailpal.io and the existing handled support ticket.
- No genuine merchant email conversation, opt-out, or account restriction warning
  was visible in this bounded complete mailbox search. This is not proof of inbox
  placement, absence of all spam signals, or established sending reputation.
- The September 6 internal self-send's original headers have no receiving
  Authentication-Results. Do not claim it proves SPF/DKIM/DMARC passed externally.
- Google Admin's authenticate-email page requires fresh password verification.
  No credentials were guessed and no authentication status was fabricated.
- The existing Resend receiving copy of the September 6 test confirms SPF and
  DKIM passed externally, with DMARC absent at that time. A single clearly labeled
  technical diagnostic sent from info to info after the DNS repair was received
  by the existing external copy route at 20:28:26 UTC on September 9. Its receipt
  `1da4d0d8-13d5-4a83-904c-9ca389290886` reports **SPF PASS, DKIM PASS, DMARC PASS**
  at both Google and the external receiving server. No merchant was messaged, no
  reply was requested, and this test is excluded from ramp and acquisition counts.
  This verifies working signing without requiring access to the Admin setting.

## DNS change and verification

Vercel DNS inventory and authoritative/public DNS were inspected before mutation.
Existing root SPF is `v=spf1 include:_spf.google.com ~all`; existing Google DKIM
selector is `google._domainkey` with a published RSA key. Root MX remains
`smtp.google.com`. Existing application/Resend records remain intact.

Added only this missing TXT record, Vercel ID `rec_f1f2b09a47378d8ccfc591d0`:

| Name | Type | Value |
| --- | --- | --- |
| `_dmarc.skubase.io` | TXT | `v=DMARC1; p=none; rua=mailto:info@skubase.io; adkim=r; aspf=r` |

Verified the exact value via the authoritative Vercel nameserver and 1.1.1.1.
`p=none` collects aggregate reporting without changing delivery enforcement.
This repairs the missing DNS policy; it does not itself prove outgoing alignment.
The subsequent received-message diagnostic above independently verified alignment.
Rollback removes only this newly added record by ID if required.

## Operating policy

The earliest healthy schedule is 5/day on days 1-3, 8/day on days 4-6,
12/day on days 7-10, 15/day on days 11-14 and 20/day thereafter, in Pacific time.
The clock begins with actual live first contact, not deployment or safe tests.
Idle days alone cannot establish reputation. Each increase also needs real send
and delivery/reply evidence and a recent inbox check. Negative signals freeze
increases; serious deliverability incidents retain the existing sending hold.
Each stage requires at least three confirmed messages spread over two days, one
delivery or reply, and an inbox check within 24 hours. Negative observations freeze
increases for seven days; unresolved serious provider restrictions keep sending
paused. These evidence thresholds do not instruct the agent to manufacture traffic.
Use stronger eligible prospects first; never send merely to satisfy a minimum.

No fake replies, recipient accounts, engagement networks, meaningless warming
messages, or account/domain rotation. No paid mailbox warming is enabled.
Mail-server acceptance is not inbox placement; unknown spam measurements stay
unknown. Preserve hard-bounce suppression across campaigns and linked identities.

The owner selected Google Workspace info@skubase.io. Follow
[Workspace operations](workspace-email-operations.md). Its actual received
authentication diagnostic passed SPF, DKIM and DMARC (evidence 22221).
The ramp starts with its first real merchant email; the diagnostic does not count.
EmailPal activation is superseded. Existing operational mail and DNS are preserved.

References: [Google sender guidance](https://support.google.com/mail/answer/81126),
[Vercel DNS management](https://vercel.com/docs/cli/dns).
