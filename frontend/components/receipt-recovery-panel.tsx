import type { PendingReceipt } from "@/lib/receipt-submission";

export function ReceiptRecoveryPanel({ entries, error, busyPo, onRetry, onReview, onCorrect }: {
  entries: PendingReceipt[]; error: string | null; busyPo: string | null;
  onRetry: (entry: PendingReceipt) => void; onReview: (poId: string) => void;
  onCorrect: (entry: PendingReceipt) => void;
}) {
  if (error) return <aside className="sync-safety-note identity-review-note" role="alert"><strong>Receipt recovery is unavailable</strong><p>{error}</p><p>New receipts are paused. Restore browser storage, then reload this page before trying again.</p></aside>;
  if (!entries.length) return null;
  return <section className="section-card" aria-label="Receipts awaiting confirmation">
    <h2 className="section-title section-title-small">Check unconfirmed receipts</h2>
    <p className="section-copy">These deliveries need confirmation or correction. Retry an unconfirmed submission to check or finish it safely. The same submission cannot count received units twice. Do not enter it as a new delivery.</p>
    {entries.map(entry => <article key={entry.payload.request_id} className="sync-safety-note identity-review-note" style={{ minWidth: 0, overflowWrap: "anywhere" }}>
      <strong>PO {entry.po_id} · {entry.payload.lines.reduce((sum, line) => sum + line.received_qty, 0)} units</strong>
      <p className="section-copy">Receipt date: {new Date(entry.payload.received_at).toLocaleDateString()}</p>
      <ul className="section-copy">{entry.payload.lines.map(line => <li key={line.sku_id}>SKU {line.sku_id}: {line.received_qty} units at ${line.received_unit_cost?.toFixed(2)} each</li>)}</ul>
      {entry.rejection ? <p className="section-copy"><strong>Not recorded.</strong> {entry.rejection}</p> : null}
      <div className="button-row">{entry.rejection ? <button type="button" className="button button-primary" disabled={busyPo === entry.po_id} onClick={() => onCorrect(entry)}>Correct rejected receipt</button> : <button type="button" className="button button-primary" disabled={busyPo === entry.po_id} onClick={() => onRetry(entry)}>{busyPo === entry.po_id ? "Checking receipt…" : "Retry same receipt"}</button>}<button type="button" className="button button-secondary" onClick={() => onReview(entry.po_id)}>Review PO history</button></div>
    </article>)}
  </section>;
}
