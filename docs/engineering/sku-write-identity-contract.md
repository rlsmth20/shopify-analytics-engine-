# SKU identity in merchant settings and saved orders

SKU text is a merchant-facing alias, not a product primary key. Settings and
purchase-order writes use the shop-scoped alias resolver before mutating rows.
One product with an inventory row (including zero on hand) takes precedence over
a retired CSV stub. Multiple eligible products require identity review. This
release does not merge products or rewrite historical SKU text.

## Lead-time overrides

`PUT /shop-settings/sku-lead-times` replaces overrides only on products that can
be resolved uniquely. An empty `items` list clears those editable overrides.
Overrides on ambiguous or superseded product records are retained, and both GET
and PUT return additive `warnings` explaining that they were retained. An empty
editable list therefore does not prove that every historical override was
deleted. Clients must display the warnings rather than reporting that all
overrides were removed.

An unchanged ambiguous alias/value may accompany an unrelated edit only when
every eligible product already has that exact value. A different value returns
HTTP 409 before any override is reset. Conflicting historical values remain in
storage and are not collapsed into one editable rule.

## Purchase orders and receipts

Saved lines expose derived `product_id`, `identity_ambiguous`, and
`identity_warning`; submitted identity flags are not trusted. Unchanged legacy
lines, text, costs, and receipt history remain available while unrelated safe
lines or order metadata are edited. Changing an ambiguous alias, or changing a
SKU shared by multiple saved lines, returns HTTP 409 before changing the order.

Receipts require one saved line per requested SKU and a nonambiguous catalog
alias. Duplicate request aliases, zero-only submissions, and quantities greater
than the remaining order quantity return HTTP 409 without a receipt or success
audit entry. All requested lines are checked before any are updated. The saved
line's received increment equals the receipt's recorded quantity; quantities
are never silently clamped. Receiving refreshes lines after locking the saved
order so a previously cached remaining count is not reused.

These guards apply to new writes. Historical records are preserved, including
any older receipt discrepancies; this release does not repair them automatically.
