# Buying calendar: existing purchase orders

The calendar still plans one upcoming buying cycle per SKU and shows open saved purchase orders separately. New recommendations now subtract outstanding units already scheduled to cover that cycle. For example, a 37-unit need at $10 per unit with a sent 37-unit PO arriving tomorrow now shows the existing $370 PO without recommending another $370 purchase.

An inbound line can reduce a recommendation only when:

- Its PO is `sent` or `partially_received`, with a recorded sent or receipt date no later than today.
- Its ETA is valid, is not overdue, and does not predate that recorded activity.
- It matches the SKU and has unreceived units. Received quantities cannot reduce the balance below zero or inflate it when malformed.
- It arrives by the next buying cycle's expected arrival date and before projected stock becomes negative. Earlier timely arrivals can extend the runway for later arrivals.

Arrivals are treated as available at the start of the recorded date. The PO schema has no supplier acknowledgement field: sent dates and ETAs are planning evidence, not a guarantee of arrival. An undated or overdue shipment remains visible but needs a revised ETA before it offsets demand. Draft, ready, and approved orders also remain visible without reducing a new buy; received and cancelled orders are excluded from open orders.

Saved PO units show the unreceived balance. Their cost remains the original PO total, not an inferred unpaid balance; this is stated in the event rationale. Netting does not change, send, receive, or cancel any purchase order. It also does not simulate every later replenishment cycle in the horizon.

Cost-derived displays use the additive `financial_values` and `financial_values_known` fields. Unknown supplier costs remain unknown, and do not drive economic order quantity calculations. Legacy numeric fields remain for API compatibility.

The purchase-order screen also honors these cost fields in totals, line values, filters, and supplier drafts. Generated estimates do not prefill the editable supplier cost. Every line needs an explicitly valid cost before saving or issuing the PO; blank is not zero, and invalid lines cannot silently disappear from a saved order. Existing entered prices remain valid.

Opening a vendor email draft now only opens the compose window. It does not mark the PO sent, because a `mailto:` action cannot establish that an email was delivered or even sent. Merchants use the separate **Mark as sent** action after sending the purchase order to the supplier. This is a merchant acknowledgement, not an email-provider delivery receipt. Existing historical sent statuses cannot retrospectively prove whether an email was sent.

Verification: `python -m unittest tests.test_buying_calendar` from `backend/` covers the duplicate purchase, partial receipts, lifecycle states, malformed and overdue dates, stockout and cycle boundaries, interacting arrivals, unknown costs, and input immutability.

Frontend verification: `node --test tests/purchase-order-finance.test.cjs` covers unknown costs, explicit zero costs, invalid lines, incomplete totals, action eligibility, and separate email-draft versus sent-status behavior.
