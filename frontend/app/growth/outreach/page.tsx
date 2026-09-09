"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { API_BASE_URL } from "@/lib/api-base";
import { authenticatedFetch } from "@/lib/shopify-embedded";
import { growthTime } from "@/lib/growth-dashboard";
import styles from "./page.module.css";

type Outreach = {
  id: string; contact: string; identity: string | null; email: string | null;
  method: string; status: string; sent_at: number | null; reserved_at: number;
  timestamp_basis: string | null; message: string | null; subject: string | null;
  message_basis: string | null;
  source_url: string | null; receipt: string | null; receipt_urls: string[];
  experiment_id: string; message_version: string | number | null; suppressed: boolean | null;
};
type Result = { items: Outreach[]; next_cursor: string | null };
const methods: Record<string, string> = { contact_form: "Business contact form", email: "Email", reddit: "Reddit", shopify_community: "Shopify Community" };
const statuses: Record<string, string> = { sent: "Confirmed sent", uncertain: "Uncertain submission", reserved: "Prepared · not confirmed sent", failed: "Failed", not_sent: "Confirmed not sent" };
function safeLink(value: string) {
  try { const url = new URL(value); return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? value : null; }
  catch { return null; }
}
function EvidenceLink({ url, children }: { url: string; children: React.ReactNode }) {
  const href = safeLink(url);
  return href ? <a href={href} target="_blank" rel="noopener noreferrer">{children} ↗</a> : null;
}

export default function OutreachHistoryPage() {
  const [result, setResult] = useState<Result | null>(null);
  const [status, setStatus] = useState("sent");
  const [method, setMethod] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const active = useRef<AbortController | null>(null);
  const load = useCallback(async (cursor?: string) => {
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setBusy(true); setError("");
    if (!cursor) setResult(null);
    try {
      const params = new URLSearchParams({ status, search });
      if (method) params.set("method", method);
      if (cursor) params.set("before", cursor);
      const response = await authenticatedFetch(`${API_BASE_URL}/growth/outreach-history?${params}`, { credentials: "include", cache: "no-store", signal: controller.signal });
      if (controller.signal.aborted) return;
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          setResult(null);
          throw new Error("Sign in with your Skubase owner account to view messages.");
        }
        throw new Error("Outreach history could not be loaded. Please try again.");
      }
      const next = await response.json() as Result;
      if (!controller.signal.aborted) setResult(previous => ({ ...next, items: cursor && previous ? [...previous.items, ...next.items.filter(item => !previous.items.some(old => old.id === item.id))] : next.items }));
    } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Could not load outreach."); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }, [status, method, search]);
  useEffect(() => { void load(); return () => active.current?.abort(); }, [load]);

  return <main className={styles.page}>
    <header className={styles.header}><Link href="/growth">← Growth dashboard</Link><button disabled={busy} onClick={() => void load()}>Refresh</button></header>
    <h1>Outreach history</h1>
    <p className={styles.intro}>See who we contacted, what we said, and the evidence behind each message.</p>
    <form className={styles.filters} onSubmit={event => { event.preventDefault(); setSearch(searchInput); }}>
      <label>Find a merchant<input type="search" value={searchInput} maxLength={150} onChange={event => setSearchInput(event.target.value)} placeholder="Merchant name, username or email" /></label>
      <button type="submit">Search</button>
      <label>Contact method<select value={method} onChange={event => setMethod(event.target.value)}><option value="">All methods</option>{Object.entries(methods).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label>
      <label>Send status<select value={status} onChange={event => setStatus(event.target.value)}>{Object.entries(statuses).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label>
    </form>
    <p className={styles.note}>{status === "sent" ? "Confirmed first-contact messages, newest records first. Confirmation means submitted or provider-accepted; it does not prove the merchant read it." : "These records are separate from confirmed outreach. Uncertain contacts remain protected from duplicate attempts."} Times use your browser’s local timezone.</p>
    {error && <div role="alert" className={styles.notice}>{error} <button onClick={() => void load(result?.next_cursor || undefined)}>Try again</button></div>}
    {busy && <p role="status">Loading outreach history…</p>}
    {result && !result.items.length && <p className={styles.notice}>No outreach matches these filters.</p>}
    <div className={styles.list}>{result?.items.map(item => <article key={item.id} className={styles.card}>
      <div className={styles.cardHeader}><div><h2>{item.contact === "Unknown" ? item.identity || "Historical merchant" : item.contact}</h2><p>{item.identity}{item.email && item.email !== item.identity ? ` · ${item.email}` : ""}</p></div><span className={styles.badge}>{statuses[item.status] || item.status}</span></div>
      <dl className={styles.meta}><div><dt>Contact method</dt><dd>{item.method === "reddit" ? item.receipt_urls.some(url => /\/(chat|room)\//.test(url)) ? "Reddit direct message" : "Reddit reply" : methods[item.method] || item.method}</dd></div><div><dt>{item.sent_at ? item.timestamp_basis ? "Recorded send time" : "Sent" : "Prepared"}</dt><dd>{growthTime(item.sent_at || item.reserved_at)}</dd></div></dl>
      {item.timestamp_basis && <p className={styles.note}>{item.timestamp_basis}</p>}
      <div className={styles.links}>{item.source_url && <EvidenceLink url={item.source_url}>{["reddit", "shopify_community"].includes(item.method) ? "Original post / source" : "Merchant / source page"}</EvidenceLink>}{item.receipt_urls.map((url, index) => <EvidenceLink key={url} url={url}>{index ? `Additional evidence ${index + 1}` : item.method === "contact_form" ? "Submission page" : "Sent message / receipt"}</EvidenceLink>)}</div>
      <h3>{item.status === "sent" ? "Message sent" : "Prepared message"}</h3>
      {item.subject && <p><strong>Subject:</strong> {item.subject}</p>}
      {item.message ? <blockquote className={styles.message}>{item.message}</blockquote> : <p className={styles.notice}>Exact message text was not retained or could not be verified against this record.</p>}
      {item.message && item.message_basis && <p className={styles.note}>{item.message_basis}</p>}
      <details><summary>View receipt and campaign details</summary><dl className={styles.details}><dt>Receipt</dt><dd>{item.receipt || "No confirmed receipt recorded"}</dd><dt>Message version</dt><dd>{item.message_version ?? "Not recorded"}</dd><dt>Experiment</dt><dd>{item.experiment_id}</dd><dt>Record</dt><dd>{item.id}</dd>{item.suppressed && <><dt>Contact protection</dt><dd>Suppressed from further outreach</dd></>}</dl><p className={styles.note}>Some forms return a temporary confirmation page. The retained receipt remains available here even if that page later changes.</p></details>
    </article>)}</div>
    {result?.next_cursor && <button disabled={busy} onClick={() => void load(result.next_cursor!)}>Load older messages</button>}
  </main>;
}
