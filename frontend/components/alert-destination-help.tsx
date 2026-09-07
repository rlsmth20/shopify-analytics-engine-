"use client";

import { useState } from "react";

// Mirrors the generic notification driver's JSON envelope. These are synthetic
// values for receiver mapping; this component never sends a notification.
export const WEBHOOK_EXAMPLE_JSON = JSON.stringify({
  subject: "Skubase example alert",
  body: "Example only: review an inventory issue in your Skubase workspace.",
  emitted_at: "2026-09-07T12:00:00+00:00",
  source: "skubase",
}, null, 2);

export function AlertDestinationHelp({ channel, className }: {
  channel: "slack" | "webhook";
  className?: string;
}) {
  const [copyStatus, setCopyStatus] = useState("");

  async function copyExample() {
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(WEBHOOK_EXAMPLE_JSON);
      setCopyStatus("Example JSON copied. No notification was sent.");
    } catch {
      setCopyStatus("Copy is unavailable. Select the example JSON and copy it manually.");
    }
  }

  return <details className={className}>
    <summary>{channel === "slack" ? "Set up your Slack channel" : "Connect your receiving workflow"}</summary>
    {channel === "slack" ? <>
      <p>Connect the channel your team uses with an incoming webhook from your Slack workspace.</p>
      <ol style={{ paddingLeft: "1.4rem", display: "grid", gap: "0.75rem", marginTop: "0.75rem" }}>
        <li><strong>Choose your workspace.</strong> <a href="https://api.slack.com/apps" target="_blank" rel="noopener noreferrer">Create or open a Slack app ↗</a> in the workspace your team uses.</li>
        <li><strong>Choose the receiving channel.</strong> In the app settings, open <strong>Incoming Webhooks</strong>, switch it on, then choose <strong>Add New Webhook to Workspace</strong>. Select your channel and approve access. Join a private channel before selecting it.</li>
        <li><strong>Save and test in Skubase.</strong> Copy the generated webhook URL, paste it below and select <strong>Save destination</strong>, then <strong>Send test</strong>. Check that the Skubase test appears in your chosen Slack channel.</li>
        <li><strong>Enable the alerts you want.</strong> After checking the test, enable this channel and save it. In <strong>Choose rules</strong>, select Slack for a rule and enable that rule.</li>
      </ol>
      <p className="muted small">Keep the webhook URL private; it can post to that channel. <a href="https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/" target="_blank" rel="noopener noreferrer">Slack’s official setup guide ↗</a></p>
    </> : <>
      <p>Use an automation tool or receiving system your business controls. You can use an existing service; this guide does not create one.</p>
      <ol style={{ paddingLeft: "1.4rem", display: "grid", gap: "0.75rem", marginTop: "0.75rem" }}>
        <li><strong>Create a receiver.</strong> In your tool, add an incoming webhook that accepts JSON POST requests. Choose a receiver that works with its generated secret URL; custom authorization headers and request signatures are not configured in Skubase.</li>
        <li><strong>Copy its receiving URL.</strong> Use its public HTTPS URL on port 443, not the workflow editor’s address. Keep it private. Local network addresses and sign-in pages cannot receive these notifications.</li>
        <li><strong>Save, test and check the receiver.</strong> Paste the URL below, select <strong>Save destination</strong>, then <strong>Send test</strong>. Check your tool’s received-event log and map the fields below. The receiver should return a successful HTTP response.</li>
        <li><strong>Enable the workflow and alert rule.</strong> After checking the received test, enable this channel and save it. In <strong>Choose rules</strong>, select webhook for a rule and enable that rule. Confirm your receiving workflow is active too.</li>
      </ol>
      <p className="muted small">A successful test means the receiver accepted the request. Check its output before relying on the workflow.</p>
      <label className="form-field">
        <span className="form-label">Example JSON payload — synthetic data</span>
        <textarea readOnly rows={8} value={WEBHOOK_EXAMPLE_JSON} spellCheck={false}
          style={{ width: "100%", minWidth: 0, boxSizing: "border-box", fontFamily: "monospace", fontSize: "0.8rem", lineHeight: 1.5 }} />
      </label>
      <button type="button" className="button button-secondary button-sm" onClick={() => void copyExample()}>Copy example JSON</button>
      <p className="muted small" role="status">{copyStatus || "This guide does not send the example. Send test in the channel form sends a real test to your saved destination."}</p>
    </>}
  </details>;
}
