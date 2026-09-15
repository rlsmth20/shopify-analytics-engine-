"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { API_BASE_URL } from "@/lib/api-base";
import { authenticatedFetch } from "@/lib/shopify-embedded";
import { confirmedOutreach, chartWidth, FUNNEL_STAGES, growthLabel as label, growthMoney as money, growthNumber as number,
  growthPercent as percent, growthTime as time, growthInboxView, outcomeLabel, type GrowthActivityDay, type GrowthCohort,
  type GrowthInboxTransport, type GrowthSnapshot, type GrowthOutcomes, type GrowthOutcomePeriod,
  ACQUISITION_FUNNEL_STAGES, outcomeMetric, growthText } from "@/lib/growth-dashboard";
import styles from "./page.module.css";

function Metric({ name, value, detail }: { name: string; value: string | number; detail?: string }) {
  return <div className={styles.metric}><span>{name}</span><strong data-unknown={value === "UNKNOWN" || undefined}>{value}</strong>{detail && <small>{detail}</small>}</div>;
}

function OutcomesSummary({ outcomes, period, onPeriod, experimentNames = {} }: {
  outcomes?: GrowthOutcomes; period: GrowthOutcomePeriod; onPeriod: (value: GrowthOutcomePeriod) => void;
  experimentNames?: Record<string, string>;
}) {
  const block = outcomes?.periods[period];
  const checkpoint = outcomes?.next_decision_point;
  const periods = [["today", "Today"], ["last_7_days", "Last 7 days"], ["all_time", "All time"]] as const;
  const metrics = [["paying_customers", "Paying customers"], ["mrr", "MRR"], ["trials", "Trials"],
    ["shopify_connections", "Shopify connections"], ["positive_responses", "Positive responses"],
    ["substantive_responses", "Substantive responses"], ["confirmed_contacts", "Confirmed contacts"]] as const;
  const accounting = [["email_contacts", "Email contacts"], ["delivered_emails", "Delivered emails"],
    ["bounced_emails", "Bounced emails"], ["form_submissions", "Confirmed forms"], ["reddit_contacts", "Reddit contacts"],
    ["community_contacts", "Community contacts"], ["other_contacts", "Other contacts"],
    ["uncertain_submissions", "Uncertain submissions"], ["failed_attempts", "Failed attempts"]] as const;
  return <section className={styles.section} aria-labelledby="outcomes-title">
    <div className={styles.sectionHeading}><div><p className={styles.eyebrow}>CUSTOMERS AND VALIDATED DEMAND</p><h2 id="outcomes-title">Is acquisition creating customers?</h2></div>
      <div className={styles.segmented} role="group" aria-label="Acquisition reporting period">{periods.map(([key, title]) =>
        <button key={key} aria-pressed={period === key} onClick={() => onPeriod(key)}>{title}</button>)}</div>
    </div>
    <div className={styles.outcomeMetrics}>{metrics.map(([key, title]) => <Metric key={key} name={title}
      value={outcomeMetric(block?.metrics[key], key === "mrr" ? "money" : "number")}
      detail={key === "confirmed_contacts" ? "Input to learning" : key === "mrr" ? "Attributed recurring revenue" : "Evidence-linked acquisition"} />)}</div>
    <p className={styles.caption}>Pacific calendar days. Product outcomes require a reliable prospect link. UNKNOWN means evidence is unavailable or incomplete; zero is shown only when observed. Contact volume alone does not establish demand.</p>
    {!outcomes && <p className={styles.empty}>Customer outcome reporting is not available in this snapshot. Existing activity and message receipts remain available below.</p>}
    <div className={styles.columns}>
      <section className={styles.card} aria-labelledby="outcome-funnel-title"><h2 id="outcome-funnel-title">The acquisition funnel</h2>
        <ol className={styles.outcomeFunnel}>{ACQUISITION_FUNNEL_STAGES.map(([key, title]) => <li key={key}>
          <span>{title}</span><strong>{outcomeMetric(block?.funnel[key])}</strong></li>)}</ol>
        <p className={styles.caption}>Recorded stages are independent evidence. A later stage does not fill in missing earlier stages. Channels expose different delivery and visit signals.</p>
      </section>
      <section className={styles.card} aria-labelledby="learning-decision-title"><h2 id="learning-decision-title">What the evidence changes</h2>
        <div className={styles.decision}><span className={styles.eyebrow}>CURRENT BOTTLENECK</span><h3>{outcomes?.bottleneck ? label(outcomes.bottleneck.stage) : "UNKNOWN"}</h3>
          <p>{outcomes?.bottleneck.observation || "No supported diagnosis yet."}</p><strong>Next action</strong><p>{outcomes?.bottleneck.recommended_action || "Gather attributable merchant outcomes."}</p></div>
        <dl className={styles.strategy}>
          <dt>Best signal</dt><dd>{outcomes?.best_signal?.interpretation || "UNKNOWN"}</dd>
          <dt>Current experiment</dt><dd>{outcomes?.current_experiment ? experimentNames[outcomes.current_experiment] || `Experiment ${outcomes.current_experiment.slice(0, 8)}` : "UNKNOWN"}</dd>
          <dt>Next decision point</dt><dd>{checkpoint ? `${number(checkpoint.confirmed_contacts)} confirmed contacts · review at ${number(checkpoint.target)} · ${number(checkpoint.remaining)} remaining` : "UNKNOWN"}</dd>
        </dl><p className={styles.caption}>{checkpoint?.guidance || "Review around 100 confirmed relevant contacts, or earlier when strong positive or negative evidence appears."}</p>
        <dl className={styles.operations}>{[["channel", "Best channel"], ["icp_segment", "Best ICP segment"], ["offer", "Best offer"], ["message", "Best message / positioning"]].map(([key, title]) => {
          const value = outcomes?.best[key as keyof GrowthOutcomes["best"]];
          return <div key={key} className={styles.definitionRow}><dt>{title}</dt><dd>{value == null ? "UNKNOWN" : key === "channel" ? label(growthText(value)) : typeof value === "number" ? `Variant ${value}` : growthText(value)}</dd></div>;
        })}</dl>
        <p className={styles.caption}>A leading channel or offer needs downstream evidence. Early sample sizes are learning guidelines, not statistical certainty.</p>
      </section>
    </div>
    <div className={styles.outcomeCosts}>{[["model_api_cost", "Model / API cost"], ["cost_per_confirmed_contact", "Cost per confirmed contact"],
      ["cost_per_positive_response", "Cost per positive response"], ["cost_per_customer", "Cost per customer"]].map(([key, title]) =>
      <Metric key={key} name={title} value={outcomeMetric(block?.costs[key], "money")} />)}</div>
    <details className={styles.details}><summary>Contact accounting and conversion rates for this period</summary>
      <div className={styles.columns}><dl className={styles.operations}>{accounting.map(([key, title]) => <div key={key} className={styles.definitionRow}><dt>{title}</dt><dd>{outcomeMetric(block?.accounting[key])}</dd></div>)}</dl>
        <dl className={styles.operations}>{Object.entries(block?.rates || {}).map(([key, value]) => <div key={key} className={styles.definitionRow}><dt>{label(key)}</dt><dd>{outcomeMetric(value, "percent")}</dd></div>)}</dl></div>
      <p className={styles.caption}>Uncertain submissions and failed attempts never count as confirmed contacts. Delivery is separate from provider acceptance. Internal email tests are excluded. Period rates compare events in the selected window; use original contact cohorts for conversion decisions.</p>
      <dl className={styles.operations}>{[["cost_per_discovered_merchant", "Model/API cost per discovered merchant"], ["cost_per_substantive_response", "Model/API cost per substantive response"],
        ["cost_per_connected_shopify_store", "Model/API cost per connected store"], ["cac", "Full customer acquisition cost"], ["arpu", "ARPU"], ["churn", "Churn"]].map(([key, title]) =>
          <div className={styles.definitionRow} key={key}><dt>{title}</dt><dd>{outcomeMetric(block?.costs[key], key === "churn" ? "percent" : "money")}</dd></div>)}</dl>
    </details>
    <details className={styles.details}><summary>Compare offers and merchant cohorts · all time</summary>
      {outcomes?.cohorts?.length ? <div className={styles.tableWrap} tabIndex={0} role="region" aria-label="Acquisition cohort outcomes, scroll horizontally"><table className={styles.cohortTable}>
        <caption>Each original experiment, channel, merchant segment, offer, positioning and CTA stays separate. Thresholds are review guidelines; allow time for responses.</caption>
        <thead><tr><th scope="col">Cohort hypothesis</th><th scope="col">Learning window</th><th scope="col">Contacts</th><th scope="col">Substantive</th><th scope="col">Positive</th><th scope="col">Connected</th><th scope="col">Paid</th><th scope="col">MRR</th></tr></thead>
        <tbody>{outcomes.cohorts.map(cohort => <tr key={cohort.id}><th scope="row"><strong>{label(cohort.channel)} · {growthText(cohort.icp_segment, "Unknown segment")}</strong>
          <small>{growthText(cohort.offer, "Unknown offer")} · variant {growthText(cohort.message)}</small><small>{growthText(cohort.positioning, "Positioning unknown")}</small><small>CTA: {growthText(cohort.cta)}</small>
          <small>Experiment {growthText(cohort.experiment_id).slice(0, 8)} · cohort {growthText(cohort.id).slice(0, 8)}</small></th>
          <td>{label(cohort.maturity)}<small>{number(cohort.mature_contacts)} contacts aged 7+ days</small></td>
          {["confirmed_contacts", "substantive_responses", "positive_responses", "shopify_connections", "paying_customers", "mrr"].map(key => <td key={key}>{outcomeMetric(cohort.metrics[key], key === "mrr" ? "money" : "number")}</td>)}</tr>)}</tbody>
      </table></div> : <p className={styles.empty}>No acquisition cohorts are available yet.</p>}
    </details>
    <details className={styles.details}><summary>Compare channels by customer outcomes · all time</summary>
      {outcomes?.channels?.length ? <div className={styles.tableWrap} tabIndex={0} role="region" aria-label="Channel outcomes, scroll horizontally">
        <table><caption>Confirmed contacts supply the sample. Responses, connected stores and customers supply the result.</caption>
          <thead><tr><th scope="col">Channel</th><th scope="col">Contacts</th><th scope="col">Substantive responses</th><th scope="col">Positive responses</th><th scope="col">Connected</th><th scope="col">Paid</th><th scope="col">MRR</th></tr></thead>
          <tbody>{outcomes.channels.map((channel, index) => <tr key={channel.id || channel.channel || index}><th scope="row">{label(channel.channel || channel.dimensions?.channel || channel.id)}</th>
            {["confirmed_contacts", "substantive_responses", "positive_responses", "shopify_connections", "paying_customers", "mrr"].map(key =>
              <td key={key}>{outcomeMetric(channel.metrics[key], key === "mrr" ? "money" : "number")}</td>)}</tr>)}</tbody>
        </table></div> : <p className={styles.empty}>No channel comparison is available yet.</p>}
    </details>
  </section>;
}

function InboxMonitoring({ transport }: { transport?: GrowthInboxTransport | null }) {
  const inbox = growthInboxView(transport);
  const recordedTime = (value: number | null) => value === null ? "Unknown — not recorded" : time(value);
  return <section className={styles.item} aria-labelledby="inbox-monitoring-title">
    <h3 id="inbox-monitoring-title">Business inbox · info@skubase.io</h3>
    <p><strong className={inbox.warning ? styles.warningText : undefined}>{inbox.label}</strong></p>
    <p>{inbox.explanation}</p>
    <dl className={styles.operations}>
      <dt>Last inbox check</dt><dd>{recordedTime(inbox.lastPollAt)} · {inbox.lastPollResult}</dd>
      <dt>Last successful check</dt><dd>{recordedTime(inbox.lastSuccessfulPollAt)}</dd>
      <dt>Replies ingested on latest check</dt><dd>{number(inbox.latestReplies)}</dd>
      <dt>Last copied receipt arrived</dt><dd>{recordedTime(inbox.lastReceiptAt)}</dd>
      <dt>Copy last observed by agent</dt><dd>{recordedTime(inbox.receiptObservedAt)}</dd>
      <dt>Last verified reply delivery</dt><dd>{recordedTime(inbox.verifiedAt)}</dd>
    </dl>
    <p className={styles.caption}>An empty successful check is normal. It does not prove that Gmail is forwarding replies to the agent. Copied receipts and internal delivery checks are separate from merchant reply metrics.</p>
    {inbox.verificationWindowDays !== null && <p className={styles.caption}>Delivery verification is considered old after {number(inbox.verificationWindowDays)} days. Old verification calls for another check; it does not establish that delivery has failed.</p>}
  </section>;
}

function ActivityChart({ days }: { days: GrowthActivityDay[] }) {
  const max = Math.max(1, ...days.flatMap(day => [day.first_contacts, day.substantive_replies]));
  const total = days.reduce((sum, day) => sum + day.first_contacts + day.substantive_replies, 0);
  return <>
    <div className={styles.legend}><span><i className={styles.contactSwatch} />First contacts</span><span><i className={styles.replySwatch} />Merchants with substantive replies</span></div>
    {total > 0 ? <div className={styles.activityChart} role="img" aria-label={`Seven days of activity: ${days.map(d => `${d.day}: ${d.first_contacts} first contacts and ${d.substantive_replies} merchants with substantive replies`).join("; ")}.`}>
      {days.map(day => <div key={day.day} className={styles.chartDay} aria-hidden="true"><div className={styles.barPair}>
        <div className={styles.barColumn}><span>{day.first_contacts}</span><i className={styles.contactBar} style={{ height: `${chartWidth(day.first_contacts, max)}%` }} /></div>
        <div className={styles.barColumn}><span>{day.substantive_replies}</span><i className={styles.replyBar} style={{ height: `${chartWidth(day.substantive_replies, max)}%` }} /></div>
      </div><small>{new Date(`${day.day}T12:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" })}</small></div>)}
    </div> : <div className={styles.empty}><strong>No outreach or substantive replies recorded in this window.</strong><p>New first contacts and substantive replies will appear here as they are recorded.</p></div>}
    <p className={styles.caption}>UTC calendar days · today is partial. Each merchant counts once per day in each series. Automated messages are excluded.</p>
  </>;
}

function CohortOutcome({ cohort, stage }: { cohort: GrowthCohort; stage: string }) {
  const observed = cohort.outcomes[stage] ?? 0;
  return <><strong className={styles.tableNumber}>{outcomeLabel(observed, cohort.linked_contacts, cohort.sent)}</strong>
    <small>{number(observed)} verified {observed === 1 ? "store" : "stores"}</small></>;
}

function CohortTable({ cohorts }: { cohorts: GrowthCohort[] }) {
  if (!cohorts.length) return <div className={styles.empty}><strong>No first-contact cohorts yet.</strong><p>A cohort appears after an approved first-contact reservation. Drafts and discoveries do not count as sends.</p></div>;
  return <div className={styles.tableWrap} tabIndex={0} role="region" aria-label="Outreach cohort comparison, scroll horizontally for outcomes">
    <table className={styles.cohortTable}><caption>Original experiment, channel, ICP, offer and message version stay separate. Unknown means the outcome cannot yet be linked.</caption>
      <thead><tr><th scope="col">Cohort / offer</th><th scope="col">First contacts</th><th scope="col">Receipt status</th><th scope="col">Substantive reply</th><th scope="col">Positive interest</th><th scope="col">Signup</th><th scope="col">Connected</th><th scope="col">Activated</th><th scope="col">Paid</th></tr></thead>
      <tbody>{cohorts.map(c => <tr key={c.id}>
        <th scope="row"><span className={styles.channel}>{label(c.channel)}</span><strong>{growthText(c.icp, "ICP not labeled")}</strong><small>{label(c.offer)} · message {growthText(c.message_version)}</small><small>Experiment {c.experiment_id.slice(0, 8)} · cohort {c.id.slice(0, 6)}</small><small>{c.linked_contacts}/{c.sent} merchant account links</small></th>
        <td><strong className={styles.tableNumber}>{number(c.sent)}</strong><small>{c.mature}/{c.sent} observed ≥7 days</small>{c.pending > 0 && <small className={styles.warningText}>{c.pending} unresolved</small>}</td>
        <td>{c.channel === "email" ? <><strong>{number(c.email_delivered)} delivered</strong><small>{number(c.email_bounced)} bounced · {c.delivery_unknown} unknown</small></> : <><strong>{!c.sent ? "Awaiting receipt" : c.channel === "contact_form" ? "Form accepted" : "Publicly posted"}</strong><small>{c.sent ? `${c.sent} receipts` : "No completed receipt"}</small><small>Email delivery: N/A</small></>}</td>
        <td><strong className={styles.tableNumber}>{c.substantive_replies}</strong><small>{percent(c.substantive_reply_rate)} of contacted</small></td>
        <td><strong className={styles.tableNumber}>{c.positive_interest}</strong><small>{percent(c.positive_interest_rate)} of contacted</small></td>
        <td><CohortOutcome cohort={c} stage="SIGNUP" /></td><td><CohortOutcome cohort={c} stage="SHOPIFY_CONNECTION" /></td>
        <td><CohortOutcome cohort={c} stage="INVENTORY_ANALYSIS_VIEWED" /></td><td><CohortOutcome cohort={c} stage="SUBSCRIPTION_PURCHASED" /></td>
      </tr>)}</tbody>
    </table>
  </div>;
}

export default function GrowthPage() {
  const [data, setData] = useState<GrowthSnapshot | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [funnelScope, setFunnelScope] = useState<"mission" | "all">("mission");
  const [outcomePeriod, setOutcomePeriod] = useState<GrowthOutcomePeriod>("today");
  const inFlight = useRef<{ signal?: AbortSignal; id: number } | null>(null);
  const requestSequence = useRef(0);
  const load = useCallback(async (signal?: AbortSignal) => {
    if (inFlight.current && !inFlight.current.signal?.aborted) return;
    const id = ++requestSequence.current;
    inFlight.current = { signal, id };
    setRefreshing(true);
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/growth/dashboard`, { credentials: "include", signal });
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) { setData(null); throw new Error("Sign in with a Skubase owner account to view growth operations."); }
        throw new Error("Growth data is temporarily unavailable.");
      }
      const snapshot = await response.json() as GrowthSnapshot;
      if (!signal?.aborted) { setData(snapshot); setError(""); }
    } catch (e) {
      if (!signal?.aborted) setError(e instanceof Error ? e.message : "Could not refresh growth data.");
    } finally { if (inFlight.current?.id === id) { inFlight.current = null; if (!signal?.aborted) setRefreshing(false); } }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    const timer = setInterval(() => { if (!document.hidden) void load(controller.signal); }, 30000);
    const onVisible = () => { if (!document.hidden) void load(controller.signal); };
    document.addEventListener("visibilitychange", onVisible);
    return () => { controller.abort(); clearInterval(timer); document.removeEventListener("visibilitychange", onVisible); };
  }, [load]);

  async function toggle() {
    if (!data) return;
    setBusy(true);
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/growth/control`, { method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ paused: !data.agent.paused }) });
      if (!response.ok) throw new Error("Could not update operator status.");
      setData(current => current ? { ...current, agent: { ...current.agent, paused: !data.agent.paused } } : current);
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Status update failed."); }
    finally { setBusy(false); }
  }

  const capacity = data?.agent.first_contact_capacity;
  const confirmed = capacity ? confirmedOutreach(capacity) : 0;
  const uncertain = capacity?.uncertain_contact_count ?? capacity?.unresolved ?? 0;
  const sendsInFlight = capacity?.in_flight_send_count ?? 0;
  const funnel = funnelScope === "all" ? data?.funnel : data?.measurement?.mission_funnel;
  const funnelMax = Math.max(1, ...Object.values(funnel || {}));
  const healthy = !!data && !data.agent.paused && !data.execution?.operational_fault && ["running", "healthy", "idle", "waiting"].includes(data.agent.health);
  const held = !!data && Object.keys(data.strategy.acquisition_hold || {}).length > 0;
  const unknownCosts = data?.economics.unknown_cost_records ?? 0;

  return <main className={styles.page}>
    <header className={styles.header}>
      <Link href="/dashboard" className={styles.brand}>skubase<span> / growth</span></Link>
      <div className={styles.headerActions}><span className={styles.pill}>Organic · $0 advertising</span>
        <Link href="/growth/outreach">View messages sent →</Link>
        <button onClick={() => void load()} disabled={refreshing}>{refreshing ? "Refreshing…" : "Refresh"}</button>
        {data && <button onClick={() => void toggle()} disabled={busy} className={styles.quietButton}>{busy ? "Updating…" : data.agent.paused ? "Resume operator" : "Pause operator"}</button>}
      </div>
    </header>
    <div className={styles.intro}><div><p className={styles.eyebrow}>OWNER’S GROWTH BRIEF</p><h1>From merchant need<br />to paying customers.</h1>
      <p>The evidence, experiments, and next actions that move Skubase toward paying customers.</p></div>
    </div>
    {error && <div className={styles.notice} role="alert">{error} {data ? "The last successful snapshot is shown below." : <Link href="/login">Sign in</Link>} <button onClick={() => void load()}>Retry</button></div>}
    {!data && !error && <div className={styles.loading} role="status"><span className={styles.loadingDot} />Loading the latest retained evidence…</div>}
    {data && <>
      <OutcomesSummary outcomes={data.outcomes} period={outcomePeriod} onPeriod={setOutcomePeriod}
        experimentNames={Object.fromEntries(data.experiments.items.map(experiment => [experiment.id, experiment.specification.hypothesis]))} />
      <section className={styles.hero} aria-labelledby="next-action"><div><p className={styles.eyebrow}>HIGHEST-VALUE NEXT MOVE</p><h2 id="next-action">{label(data.execution?.next_action || data.strategy.next_action || data.agent.next_action)}</h2>
        <p>{data.strategy.bottleneck.recommended_action}</p></div>
        <div className={styles.health}><span className={healthy ? styles.dot : styles.warningDot} />{data.agent.paused ? "Operator paused" : label(data.agent.health || "not started")}<small>Last wake {time(data.agent.last_wake)}</small><small>Current model: {data.agent.model || "No model running"}</small></div>
      </section>
      <details className={styles.details}><summary>Operations, experiment cohorts and full evidence history</summary>
      <p className={styles.caption}>Initial mission milestone: {number(data.mission.qualified_users)} / {number(data.mission.target)} qualified users. Each identity counted once; intent and payment evidence remain separate.</p>
      {data.execution && <section className={styles.card} aria-labelledby="execution-title">
        <h2 id="execution-title">Acquisition execution</h2>
        {data.execution.operational_fault && <p className={styles.notice} role="alert">Operational fault: {label(data.execution.operational_fault)}</p>}
        <dl className={styles.operations}>
          <dt>Daily outreach limit</dt><dd>{data.execution.daily_new_contact_cap === null ? "No daily limit" : `${number(data.execution.daily_new_contact_cap)} · ${data.execution.day_timezone ? "resets at midnight Pacific" : "rolling 24 hours"}`}</dd>
          <dt>Confirmed first contacts</dt><dd>{number(data.execution.sent_today)}{data.execution.daily_new_contact_cap !== null && ` / ${number(data.execution.daily_new_contact_cap)}`}</dd>
          <dt>Uncertain contacts</dt><dd>{data.execution.uncertain_contact_count ?? uncertain}</dd>
          <dt>Sends in progress</dt><dd>{data.execution.in_flight_send_count ?? sendsInFlight}</dd>
          <dt>Remaining capacity</dt><dd>{data.execution.daily_new_contact_cap === null ? "No daily limit" : number(data.execution.remaining_capacity)}</dd>
          <dt>Qualified ready</dt><dd>{data.execution.qualified_ready}</dd>
          <dt>Discovery pending</dt><dd>{data.execution.discovery_pending}</dd>
          <dt>Acquisition tasks running</dt><dd>{data.execution.acquisition_tasks_running}</dd>
          <dt>Oldest pending acquisition</dt><dd>{data.execution.oldest_pending_acquisition_age === null ? "None" : `${Math.floor(data.execution.oldest_pending_acquisition_age / 60)} minutes`}</dd>
          <dt>Last acquisition action</dt><dd>{data.execution.last_acquisition_action ? `${label(data.execution.last_acquisition_action.stage)} · ${time(data.execution.last_acquisition_action.at)}` : "No completed stage recorded"}</dd>
          <dt>Last successful send</dt><dd>{time(data.execution.last_successful_send)}</dd>
          <dt>Current blocker</dt><dd>{data.execution.current_blocker ? label(data.execution.current_blocker) : "None recorded"}</dd>
          <dt>Next action</dt><dd>{label(data.execution.next_action)}</dd>
          <dt>Next wake / retry</dt><dd>{time(data.execution.next_wake_retry)}</dd>
        </dl>
      </section>}
      {held && <div className={styles.notice}><strong>New acquisition is on hold.</strong> Existing conversations and product-funnel investigation remain the priority. {data.strategy.bottleneck.observation}</div>}
      <div className={styles.columns}>
        <section className={styles.card} aria-labelledby="capacity-title"><div className={styles.cardHeading}><h2 id="capacity-title">First-contact activity</h2><span className={styles.tag}>{capacity?.day_timezone ? "Today · Pacific time" : "Rolling 24 hours"}</span></div>
          {capacity ? <><div className={styles.capacityNumber}><strong>{number(confirmed)}<span>{capacity.limit === null ? " confirmed first contacts" : ` / ${number(capacity.limit)} confirmed`}</span></strong><span>{capacity.limit === null ? "No daily limit" : `${number(capacity.remaining)} remaining`} · {number(uncertain)} uncertain</span></div>
            {capacity.limit !== null && <div className={styles.capacityTrack} role="meter" aria-label="Confirmed first contacts" aria-valuemin={0} aria-valuemax={capacity.limit} aria-valuenow={Math.min(confirmed, capacity.limit)} aria-valuetext={`${confirmed} confirmed first contacts of ${capacity.limit}; ${uncertain} uncertain contacts counted separately`}>
              <span style={{ width: `${chartWidth(confirmed, capacity.limit)}%` }} /></div>}
            <div className={styles.capacityMeta}><span>{sendsInFlight} send in progress</span><span>{uncertain} uncertain contacts protected from retry</span></div>
            <div className={styles.callout}><strong>{capacity.limit !== null && capacity.late_confirmation_overage ? "Late receipts revealed outreach above the ceiling. New sends are stopped." : capacity.limit !== null && confirmed >= capacity.limit ? "Confirmed outreach ceiling reached." : sendsInFlight ? "A send is in progress; the next permit waits for its outcome." : "Continue outreach to other eligible merchants."}</strong><p>{capacity.limit === null ? "There is no daily outreach ceiling. Only confirmed submissions appear in the outreach count. " : `Only confirmed submissions count toward the ${number(capacity.limit)}-contact ceiling. `}Uncertain contacts stay protected from duplicate messages. Uncertain forms do not block email or other merchants. Sends proceed one at a time. Actual channel failures pause the affected channel. Replies, research and receipt checks continue.</p></div>
            {capacity.limit !== null && capacity.next_slot_at && <p className={styles.caption}>Next confirmed-message capacity release: {time(capacity.next_slot_at)}.</p>}
          </> : <div className={styles.empty}>Capacity data is unavailable. Check the shared send ledger before contacting a new merchant.</div>}
        </section>
        <section className={styles.card} aria-labelledby="activity-chart-title"><div className={styles.cardHeading}><h2 id="activity-chart-title">Conversations over volume</h2><span className={styles.tag}>Last 7 days</span></div>
          {data.outreach ? <ActivityChart days={data.outreach.activity} /> : <p className={styles.empty}>Activity history is not available in this snapshot.</p>}
        </section>
      </div>
      <section className={styles.section}><div className={styles.sectionHeading}><h2>Today’s evidence</h2><span>Since 00:00 UTC</span></div><div className={styles.metrics}>
        <Metric name="New merchants contacted" value={number(data.today.first_contacts)} detail="All permitted channels" />
        <Metric name="Substantive replies" value={number(data.today.replies)} detail="Distinct merchants · no automated mail" />
        <Metric name="Accounts created" value={number(data.today.signups)} detail="Recorded product events" />
        <Metric name="Stores connected" value={number(data.today.connections)} detail="Verified Shopify connection" />
        <Metric name="Useful analysis viewed" value={number(data.today.activations)} detail="Observed first value" />
        <Metric name="Verified purchases" value={number(data.today.purchases)} detail="Payment evidence required" />
      </div><p className={styles.caption}>{number(data.today.actions)} completed actions · {number(data.today.conversations_found)} opportunities found · {number(data.today.emails_sent)} service emails sent. Product events are not automatically attributed to outreach.</p></section>
      <div className={styles.columns}>
        <section className={styles.card} aria-labelledby="funnel-title"><div className={styles.cardHeading}><h2 id="funnel-title">From interest to value</h2></div>
          <div className={styles.segmented} role="group" aria-label="Funnel observation period"><button aria-pressed={funnelScope === "mission"} onClick={() => setFunnelScope("mission")}>Since mission started</button><button aria-pressed={funnelScope === "all"} onClick={() => setFunnelScope("all")}>All recorded history</button></div>
          <p className={styles.muted}>{funnelScope === "mission" ? `Events observed since ${time(data.measurement?.mission_started_at)}. This is a time window, not campaign attribution.` : "Includes historical accounts and connections. These are not newly acquired campaign customers."}</p>
          <div className={styles.funnel}>{FUNNEL_STAGES.map(([key, name]) => <div className={styles.funnelRow} key={key}><div><span>{name}</span><strong>{number(funnel?.[key])}</strong></div><div className={styles.funnelTrack} aria-hidden="true"><span style={{ width: `${chartWidth(funnel?.[key], funnelMax)}%` }} /></div></div>)}</div>
          <p className={styles.caption}>Distinct identities per stage. Stages are independent observations, so bars may grow rather than narrow. An unrecorded event is not proof that it never happened.</p>
          <div className={styles.callout}><strong>Current bottleneck</strong><p>{data.strategy.bottleneck.observation}</p></div>
        </section>
        <section className={styles.card}><h2>The current strategy</h2><dl className={styles.strategy}>
          <dt>Customer hypothesis</dt><dd>{data.strategy.icp || "No ICP hypothesis recorded yet."}</dd><dt>Offer being tested</dt><dd>{data.strategy.positioning || "No offer recorded yet."}</dd>
          <dt>Acquisition priorities</dt><dd>{data.strategy.priorities?.join(" → ") || "No priorities recorded yet."}</dd><dt>Biggest uncertainty</dt><dd>{data.strategy.biggest_uncertainty || "Not recorded."}</dd>
        </dl><div className={styles.callout}><strong>Existing conversations come first.</strong><p>Substantive replies, requested health checks, and delivery failures take priority over finding the next new prospect.</p></div></section>
      </div>
      <section className={styles.section} aria-labelledby="cohorts-title"><div className={styles.sectionHeading}><div><p className={styles.eyebrow}>KEEP THE EXPERIMENT INTACT</p><h2 id="cohorts-title">Which merchants and offers move forward?</h2></div><span>Observe before changing the message</span></div>
        <p className={styles.muted}>Read response counts alongside cohort age. A few silent prospects are not a losing experiment. Positive interest means an explicit positive response or access request; a question alone does not imply buying intent.</p>
        {data.outreach ? <><CohortTable cohorts={data.outreach.cohorts} /><p className={styles.caption}>{data.outreach.limitations} {data.outreach.cohorts_truncated && `This view is limited to the latest ${data.outreach.cohort_contact_limit} contact reservations.`} A “+” indicates a verified minimum with some unlinked contacts.</p></> : <p className={styles.empty}>Cohort history is not available in this snapshot.</p>}
      </section>
      <section className={styles.section}><div className={styles.sectionHeading}><h2>Merchant pipeline</h2><span>Research leads are separate from qualified users</span></div><div className={styles.metrics}>
        <Metric name="Retained contacts" value={number(data.pipeline.prospects)} detail="Includes unqualified inbound" /><Metric name="Eligible qualified prospects" value={number(data.pipeline.qualified_prospects)} detail="Suppressed contacts excluded" />
        <Metric name="Active conversations" value={number(data.pipeline.active_conversations)} /><Metric name="High-intent prospects" value={number(data.pipeline.high_intent_prospects)} /></div>
        <details className={styles.details}><summary>Review the latest {data.pipeline.contacts.length} contacts</summary>{data.pipeline.contacts.length > 0 ? <div className={styles.tableWrap} tabIndex={0} role="region" aria-label="Merchant pipeline"><table><caption>Latest retained contacts; availability is not permission to send.</caption><thead><tr><th scope="col">Merchant / source</th><th scope="col">Stage</th><th scope="col">Contact basis</th></tr></thead><tbody>
          {data.pipeline.contacts.map(c => <tr key={c.id}><th scope="row">{c.source.startsWith("https://") ? <a href={c.source} target="_blank" rel="noreferrer">{c.organization === "Unknown" ? "Public merchant conversation" : c.organization}<span aria-hidden="true"> ↗</span></a> : c.organization}</th><td><span className={c.suppressed ? styles.warningTag : styles.tag}>{c.suppressed ? "Suppressed" : label(c.status)}</span></td><td>{label(c.contact_basis)}</td></tr>)}
        </tbody></table></div> : <p className={styles.empty}>No contacts retained yet.</p>}</details>
      </section>
      <div className={styles.columns}><section className={styles.card}><h2>Experiments</h2><div className={styles.experimentCounts}>{["active", "observing", "winning", "losing", "inconclusive"].map(status => <span key={status}><strong>{number(data.experiments.counts[status] ?? 0)}</strong>{status}</span>)}</div>
        {data.experiments.items.length ? data.experiments.items.map(e => <article key={e.id} className={styles.item}><span className={styles.tag}>{label(e.status)}</span><h3>{e.specification.hypothesis}</h3><p>Primary outcome: {e.specification.primary_metric}</p><p>{e.result.interpretation || "Waiting for market evidence. No result claimed."}</p><small>{number(e.result.sample_size)} observed contacts · confidence {e.result.confidence || "unknown"}</small>{e.result.next_action && <p className={styles.nextExperiment}><strong>Next:</strong> {e.result.next_action}</p>}</article>) : <p className={styles.empty}>No experiments recorded yet.</p>}
      </section><section className={styles.card}><h2>What we’re learning</h2><p className={styles.muted}>{data.learning.recent_changes.length} recently changed beliefs · {data.learning.contradictions.length} beliefs with contradictions</p>
        {data.learning.beliefs.length ? data.learning.beliefs.map(b => <article key={b.key} className={styles.item}><h3>{b.claim}</h3><p>{number(b.sample_size)} observations · {b.key.startsWith("response:") ? "estimated response" : "provisional confidence"} {percent(b.confidence)}</p><small>{b.confidence_meaning} {b.key.startsWith("response:") && b.credible_interval_95?.length === 2 && <>95% interval {b.credible_interval_95.map(v => percent(v)).join("–")}. </>}{b.contradictory_evidence?.length || 0} contradictory records</small>{b.sample_size === 0 && <p className={styles.warningText}>No observed sample yet. This estimate is a prior, not evidence that the offer works.</p>}</article>) : <div className={styles.empty}><strong>No established beliefs yet.</strong><p>The earlier Reddit membership request is preserved as one historical observation.</p></div>}
      </section></div>
      <section className={styles.section}><div className={styles.sectionHeading}><h2>Economics</h2><span>Missing amounts stay unknown</span></div><div className={styles.metrics}>
        <Metric name="MRR" value={money(data.economics.mrr)} /><Metric name="Verified paying customers" value={number(data.economics.customers)} />
        <Metric name="Recorded model / API spend" value={money(data.economics.model_api_spend)} detail={unknownCosts ? `${unknownCosts} usage records have unknown cost` : "Known ledger amounts"} />
        <Metric name="Reserved cost exposure" value={money(data.economics.unresolved_cost_reservations)} detail="Unsettled · not confirmed spend" /><Metric name="Advertising spend" value={money(data.economics.advertising_spend)} detail="Paid ads disabled" /><Metric name="Customer acquisition cost" value={money(data.economics.cac)} />
      </div><p className={styles.caption}>{data.economics.limitations} Runtime API ceiling: {money(data.agent.daily_budget_usd)}/day. {unknownCosts > 0 && "Recorded spend is a partial total; unknown costs are not zero."}</p></section>
      <div className={styles.columns}><section className={styles.card}><h2>Needs attention</h2>{data.agent.errors.length ? data.agent.errors.map(e => <article key={e.id} className={styles.item}><h3>{label(e.kind)}</h3><p>{e.error}</p><small>{time(e.at)}</small></article>) : <p className={styles.muted}>No current task errors are recorded. Inbox delivery status is shown separately.</p>}
        {data.review_queue?.map(item => <article key={item.id} className={styles.item}><h3>{label(item.kind)}</h3><p>{item.data.reason || item.data.observation || item.data.body}</p>{item.data.recommended_action && <p>{item.data.recommended_action}</p>}
          {item.data.destination?.startsWith("https://") && <a href={item.data.destination} target="_blank" rel="noreferrer">Review the original conversation ↗</a>}<small>{time(item.at)} · evidence {item.id}</small></article>)}
      </section><section className={styles.card}><h2>Agent operations</h2><dl className={styles.operations}><dt>Queued next</dt><dd>{label(data.agent.next_action)}</dd><dt>Next due</dt><dd>{time(data.agent.next_due)}</dd><dt>Ready work</dt><dd>{number(data.agent.queue_ready)}</dd><dt>Last executive review</dt><dd>{time(data.agent.executive?.last_review)}</dd></dl>
        {data.agent.capabilities && <p className={styles.muted}>Requested-service email: {data.agent.capabilities.requested_service_email ? "active at info@skubase.io" : "disabled"}. Browser outreach follows the shared admission ledger and reviewed channel rules. Payment receipts: {data.agent.capabilities.payment_receipts ? "integration configured" : "integration not configured"}.</p>}
        <InboxMonitoring transport={data.agent.inbox_transport} />
        <details className={styles.details}><summary>Recent activity and evidence</summary>{data.recent_actions.length ? data.recent_actions.map(a => <div key={a.id} className={styles.activity}><span>{label(a.kind)}<small>Evidence {a.id}</small></span><time dateTime={new Date(a.at * 1000).toISOString()}>{time(a.at)}</time></div>) : <p className={styles.empty}>No activity recorded yet.</p>}</details>
      </section></div>
      </details>
      <footer className={styles.footer}><p>{data.mission.qualified_definition}</p><span>Snapshot {time(data.generated_at)} · refreshes every 30 seconds while visible.</span></footer>
    </>}
  </main>;
}
