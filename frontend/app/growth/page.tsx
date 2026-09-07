"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE_URL } from "@/lib/api-base";
import { authenticatedFetch } from "@/lib/shopify-embedded";
import styles from "./page.module.css";

type Belief = { key: string; claim: string; sample_size: number; confidence: number; confidence_meaning?: string; contradictory_evidence: number[]; credible_interval_95: number[] };
type Snapshot = {
  mission: { qualified_users: number; target: number; qualified_definition: string };
  today: Record<string, number>; funnel: Record<string, number>;
  pipeline: { prospects: number; qualified_prospects: number; active_conversations: number; high_intent_prospects: number;
    contacts: { id: string; organization: string; status: string; source: string; contact_basis: string }[] };
  experiments: { counts: Record<string, number>; items: { id: string; status: string; specification: { hypothesis: string; primary_metric: string }; result: { confidence?: string; sample_size?: number; interpretation?: string; next_action?: string } }[] };
  learning: { beliefs: Belief[]; recent_changes: string[]; contradictions: unknown[] };
  strategy: { icp: string; positioning: string; next_action: string; biggest_uncertainty: string; priorities: string[];
    bottleneck: { stage: string; observation: string; recommended_action: string }; acquisition_hold: Record<string, unknown> };
  economics: { mrr: number | null; customers: number | null; model_api_spend: number; unresolved_cost_reservations: number;
    acquisition_spend: number; advertising_spend: number; cac: number | null; limitations: string };
  agent: { activity: string; next_action: string; last_wake: number; model: string | null; health: string; paused: boolean; daily_budget_usd: number;
    errors: { id: string; kind: string; error: string; at: number }[] };
  recent_actions: { id: number; kind: string; at: number; source: string }[];
};

const label = (value: string) => value.toLowerCase().replaceAll("_", " ");
const money = (value: number | null) => value === null ? "Unknown" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: value < 1 ? 4 : 2 }).format(value);
const time = (value: number) => value ? new Date(value * 1000).toLocaleString() : "Not yet";

function Metric({ name, value }: { name: string; value: string | number }) {
  return <div className={styles.metric}><span>{name}</span><strong>{value}</strong></div>;
}

export default function GrowthPage() {
  const [data, setData] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/growth/dashboard`, { credentials: "include", signal });
      if (!response.ok) throw new Error(response.status === 401 || response.status === 403 ? "Sign in with a Skubase owner account to view growth operations." : "Growth data is temporarily unavailable.");
      setData(await response.json() as Snapshot);
      setError("");
    } catch (e) {
      if (!signal?.aborted) setError(e instanceof Error ? e.message : "Could not refresh growth data.");
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    const timer = setInterval(() => { if (!document.hidden) void load(controller.signal); }, 30000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [load]);

  async function toggle() {
    if (!data) return;
    setBusy(true);
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/growth/control`, { method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ paused: !data.agent.paused }) });
      if (!response.ok) throw new Error("Could not update operator status.");
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Status update failed."); }
    finally { setBusy(false); }
  }

  return <main className={styles.page}>
    <header className={styles.header}>
      <Link href="/dashboard" className={styles.brand}>skubase<span> / growth</span></Link>
      <div className={styles.headerActions}><span className={styles.pill}>Organic · $0 advertising</span>
        {data && <button onClick={() => void toggle()} disabled={busy}>{data.agent.paused ? "Resume operator" : "Pause operator"}</button>}
      </div>
    </header>
    <div className={styles.intro}><div><p className={styles.eyebrow}>THE FIRST TEN CUSTOMERS START HERE</p><h1>A business built on evidence.</h1>
      <p>Qualified merchants, useful conversations, and the next step toward revenue.</p></div>
      {data && <div className={styles.progress}><strong>{data.mission.qualified_users}<span> / {data.mission.target}</span></strong><p>qualified users</p><progress max={10} value={data.mission.qualified_users} aria-label="Qualified user milestone" /></div>}
    </div>
    {error && <div className={styles.notice} role="alert">{error} <Link href="/login">Sign in</Link> <button onClick={() => void load()}>Retry</button></div>}
    {!data && !error && <p role="status">Loading the operator’s latest evidence…</p>}
    {data && <>
      <section className={styles.hero}><div><p className={styles.eyebrow}>HIGHEST-VALUE NEXT MOVE</p><h2>{label(data.agent.next_action || data.strategy.next_action)}</h2>
        <p>{data.strategy.bottleneck.recommended_action}</p></div>
        <div className={styles.health}><span className={styles.dot} />{label(data.agent.health || "not started")}<small>Last wake {time(data.agent.last_wake)}</small><small>Model: {data.agent.model || "No model running"}</small></div>
      </section>
      <section className={styles.section}><h2>Today</h2><div className={styles.metrics}>{Object.entries(data.today).map(([key, value]) => <Metric key={key} name={label(key)} value={value} />)}</div></section>
      <div className={styles.columns}>
        <section className={styles.card}><h2>From interest to value</h2><p className={styles.muted}>Distinct identities at each stage. Client activity cannot verify payment.</p>
          {Object.entries(data.funnel).map(([key, value], i) => <div className={styles.funnelRow} key={key}><span className={styles.step}>{i + 1}</span><span>{label(key === "INVENTORY_ANALYSIS_VIEWED" ? "ACTIVATED" : key)}</span><strong>{value}</strong></div>)}
          <div className={styles.callout}><strong>Current bottleneck</strong><p>{data.strategy.bottleneck.observation}</p></div>
        </section>
        <section className={styles.card}><h2>The current strategy</h2><dl className={styles.strategy}>
          <dt>Who we’re learning about</dt><dd>{data.strategy.icp}</dd><dt>The offer hypothesis</dt><dd>{data.strategy.positioning}</dd>
          <dt>Acquisition priorities</dt><dd>{data.strategy.priorities?.join(" → ")}</dd><dt>Biggest uncertainty</dt><dd>{data.strategy.biggest_uncertainty}</dd>
        </dl></section>
      </div>
      <section className={styles.section}><h2>Merchant pipeline</h2><div className={styles.metrics}>
        <Metric name="Prospects" value={data.pipeline.prospects} /><Metric name="Qualified prospects" value={data.pipeline.qualified_prospects} />
        <Metric name="Active conversations" value={data.pipeline.active_conversations} /><Metric name="High intent" value={data.pipeline.high_intent_prospects} /></div>
        {data.pipeline.contacts.length > 0 && <div className={styles.tableWrap}><table><thead><tr><th>Merchant / source</th><th>Stage</th><th>Contact basis</th></tr></thead><tbody>
          {data.pipeline.contacts.map(c => <tr key={c.id}><td>{c.source.startsWith("https://") ? <a href={c.source} target="_blank" rel="noreferrer">{c.organization === "Unknown" ? "Public merchant conversation" : c.organization}</a> : c.organization}</td><td>{label(c.status)}</td><td>{label(c.contact_basis)}</td></tr>)}
        </tbody></table></div>}
      </section>
      <div className={styles.columns}><section className={styles.card}><h2>Experiments</h2><p className={styles.muted}>{Object.entries(data.experiments.counts).map(([key, value]) => `${value} ${key}`).join(" · ") || "No experiments yet"}</p>
        {data.experiments.items.map(e => <article key={e.id} className={styles.item}><span className={styles.tag}>{e.status}</span><h3>{e.specification.hypothesis}</h3><p>Primary outcome: {e.specification.primary_metric}</p><p>{e.result.interpretation || "Waiting for market evidence. No result claimed."}</p><small>{e.result.sample_size || 0} observed contacts · confidence {e.result.confidence || "unknown"}</small></article>)}
      </section><section className={styles.card}><h2>What we’re learning</h2><p className={styles.muted}>{data.learning.recent_changes.length} recently changed beliefs · {data.learning.contradictions.length} beliefs with contradictions</p>
        {data.learning.beliefs.length ? data.learning.beliefs.map(b => <article key={b.key} className={styles.item}><h3>{b.claim}</h3><p>{b.sample_size} observations · {b.key.startsWith("response:") ? "estimated response" : "provisional confidence"} {Math.round(b.confidence * 100)}%</p><small>{b.confidence_meaning} {b.key.startsWith("response:") && <>95% interval {b.credible_interval_95?.map(v => `${Math.round(v * 100)}%`).join("–")}. </>}{b.contradictory_evidence?.length || 0} contradictory records</small></article>) : <p>No established beliefs yet. The earlier Reddit membership request is preserved as one historical observation.</p>}
      </section></div>
      <section className={styles.section}><h2>Economics</h2><div className={styles.metrics}>
        <Metric name="MRR" value={money(data.economics.mrr)} /><Metric name="Verified paying customers" value={data.economics.customers ?? "Unknown"} /><Metric name="Model / API spend" value={money(data.economics.model_api_spend)} />
        <Metric name="Unresolved reservations" value={money(data.economics.unresolved_cost_reservations)} /><Metric name="Acquisition spend" value={money(data.economics.acquisition_spend)} /><Metric name="CAC" value={money(data.economics.cac)} />
      </div><p className={styles.muted}>{data.economics.limitations} Runtime ceiling: {money(data.agent.daily_budget_usd)}/day.</p></section>
      <div className={styles.columns}><section className={styles.card}><h2>Needs attention</h2>{data.agent.errors.length ? data.agent.errors.map(e => <article key={e.id} className={styles.item}><h3>{label(e.kind)}</h3><p>{e.error}</p><small>{time(e.at)}</small></article>) : <p>No current execution errors.</p>}</section>
      <section className={styles.card}><h2>Recent activity</h2>{data.recent_actions.map(a => <div key={a.id} className={styles.activity}><span>{label(a.kind)}</span><small>{time(a.at)}</small></div>)}</section></div>
      <footer className={styles.footer}>{data.mission.qualified_definition} Refreshes every 30 seconds while visible.</footer>
    </>}
  </main>;
}
