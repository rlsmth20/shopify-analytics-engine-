# Purchase-order receipt recovery

Every HTTP receipt submission requires a client-generated UUID `request_id`.
The browser must save the ID and exact submitted lines/date before sending,
scope that pending operation to the signed-in merchant and PO, and reuse it
after transport failure or reload. A genuinely separate delivery gets a new
ID, even when its quantities and date match another delivery. Receipts require
a saved PO; recovery must not resave a stale draft first.

The additive `purchase_order_receipt_submissions` table has a unique constraint
on `(shop_id, purchase_order_id, request_id)` and stores only a payload hash and
creation time. Existing receipt rows remain unchanged. The standard database
initializer creates the table on existing deployments; no external service or
time-limited provider key is involved. The ledger is retained with its PO and
deleted by tenant privacy cleanup.

The server locks the PO (or reserves a SQLite writer), checks a prior submission,
and validates all receipt lines before applying any units. Submission, quantity
increments, receipt rows and success audit commit in one database transaction.
An identical replay returns `{po, replayed: true, request_id}` with the current
saved PO and no new units, receipt rows or audit. Different details under a
committed key return 409. Line order, equivalent numeric cost notation and
equivalent timestamp offsets do not change the payload hash. An omitted date
stays an omitted-date marker in the hash; its initially recorded time does not
change on retry.

Missing IDs return an actionable 422 asking older clients to reload. Malformed
UUIDs and nonfinite costs are rejected during request validation. A protected
preflight failure with no prior submission returns 409 with
`detail: {message, receipt_status: "not_applied", request_id}`. Clients may allow
correction after this explicit result. Generic 409, 5xx, missing or malformed
responses and network failures do not prove that the receipt was not applied;
preserve the pending operation and retry its exact payload. Duplicate raw line
aliases are rejected before the submission lookup and carry no recovery claim.

Received counts are server-authoritative when editing POs: submitted read-only
counts do not increment them, new lines start at zero, and a line cannot be
removed or reduced below its recorded received count. When actual receipts
exist, saving a draft preserves the persisted receipt date and lifecycle state.
Explicit status changes retain their dedicated endpoint. No historical receipt
discrepancies are repaired or merged automatically.

Verification uses synthetic SQLite databases and local HTTP requests. Coverage
includes concurrent replay, competing deliveries, commit acknowledgement loss,
transaction rollback, payload conflicts, tenant isolation, existing-schema
initialization and privacy deletion. The internal legacy receiving helper remains
available for existing service callers; HTTP routes exclusively use the protected
submission service.
