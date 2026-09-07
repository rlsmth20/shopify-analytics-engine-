import type { AlertEvent, AlertRule, AlertTrigger, NotificationChannel, NotificationChannelConfig } from "./api-v2";

export const ALERT_CHANNELS: NotificationChannel[] = ["email", "slack", "webhook", "sms"];
export const CHANNEL_LABELS: Record<NotificationChannel, string> = { email: "Email", slack: "Slack", webhook: "Webhook", sms: "SMS" };

export function targetError(channel: NotificationChannel, raw: string): string | null {
  const target = raw.trim();
  if (!target) return "Enter a destination first.";
  if (channel === "email") {
    if (target.length > 320 || !/^[^\s@<>,;]+@[^\s@<>,;]+\.[^\s@<>,;]+$/.test(target)) return "Enter one valid email address.";
    if (target.toLowerCase().startsWith("shopify-admin+")) return "Use an inbox you can access, rather than a Shopify account placeholder.";
    if (["alerts@example.com", "example@example.com"].includes(target.toLowerCase())) return "Replace the example address with your own email address.";
    return null;
  }
  if (channel === "sms") return /^\+[1-9]\d{7,14}$/.test(target) ? null : "Include the country code, for example +14155551234.";
  try {
    const url = new URL(target);
    if (url.protocol !== "https:" || url.username || url.password || url.hash || /\s/.test(target)) return "Use an HTTPS webhook URL without a username, password, or fragment.";
    const hostname = url.hostname.toLowerCase();
    if (url.port && url.port !== "443") return "Use a public HTTPS webhook URL on port 443.";
    // Catch obvious local destinations here; the server also validates resolved IPs.
    const octets = /^\d+\.\d+\.\d+\.\d+$/.test(hostname) ? hostname.split(".").map(Number) : null;
    const privateIp = octets && (octets[0] === 0 || octets[0] === 10 || octets[0] === 127
      || (octets[0] === 100 && octets[1] >= 64 && octets[1] <= 127)
      || (octets[0] === 169 && octets[1] === 254)
      || (octets[0] === 172 && octets[1] >= 16 && octets[1] <= 31)
      || (octets[0] === 192 && octets[1] === 168) || octets[0] >= 224);
    if (!hostname.includes(".") || hostname.endsWith(".localhost") || hostname.endsWith(".local")
      || hostname.endsWith(".internal") || hostname.startsWith("[") || privateIp) {
      return "Use a public internet webhook address; local and private hosts cannot receive these alerts.";
    }
    if (channel === "slack" && (url.hostname !== "hooks.slack.com" || !/^\/services\/[^/]+\/[^/]+\/[^/]+$/.test(url.pathname))) {
      return "Paste the incoming webhook URL created by Slack, starting with https://hooks.slack.com/services/.";
    }
    return null;
  } catch {
    return "Enter a complete HTTPS webhook URL.";
  }
}

export function channelState(channel: NotificationChannelConfig, allowed: boolean): {
  label: string; ready: boolean; tone: "good" | "warning" | "neutral";
} {
  if (channel.channel === "sms") return { label: "Not available yet", ready: false, tone: "neutral" };
  if (!allowed) return { label: "Plan upgrade needed", ready: false, tone: "neutral" };
  if (channel.available === false) return { label: "Service unavailable", ready: false, tone: "warning" };
  if (channel.available !== true) return { label: "Service status unknown", ready: false, tone: "warning" };
  if (channel.configured === false || targetError(channel.channel, channel.target)) return { label: "Add destination", ready: false, tone: "warning" };
  if (!channel.verified) return { label: "Send a test", ready: false, tone: "warning" };
  if (!channel.enabled) return { label: "Tested · paused", ready: false, tone: "neutral" };
  return { label: "Tested · enabled", ready: true, tone: "good" };
}

export function ruleHasReadyChannel(rule: AlertRule, channels: NotificationChannelConfig[], allowed: (channel: NotificationChannel) => boolean): boolean {
  return rule.channels.some((name) => {
    const config = channels.find((channel) => channel.channel === name);
    return config ? channelState(config, allowed(name)).ready : false;
  });
}

export function thresholdError(trigger: AlertTrigger, raw: string): string | null {
  if (!raw.trim()) return "Enter a threshold.";
  const number = Number(raw);
  if (!Number.isFinite(number) || number < 0) return "Use a non-negative number.";
  if (["forecast_miss", "supplier_slip", "price_drop"].includes(trigger) && number > 100) return "Enter a percentage between 0 and 100.";
  return null;
}

export function unsupportedTargeting(rule: AlertRule): string[] {
  const fields: string[] = [];
  if (rule.tags.length) fields.push("tags");
  if (rule.collections.length) fields.push("collections");
  if (rule.locations.length) fields.push("locations");
  if (rule.target_skus.length && rule.trigger === "supplier_slip") fields.push("SKUs");
  if (rule.categories.length && rule.trigger === "supplier_slip") fields.push("categories");
  return fields;
}

export function eventDeliveryLabel(event: AlertEvent): string {
  if (event.preview === true || event.delivery_status === "preview") return "Preview only · not sent";
  switch (event.delivery_status) {
    case "accepted": return "Request accepted";
    case "partial": return "Some channels accepted the request";
    case "pending": return "Delivery pending";
    case "failed": return "Delivery failed";
    case "skipped": return "Not sent · check channel setup";
    case "unknown": return "Delivery outcome unknown";
  }
  if (event.channels_sent.length) return "Request accepted";
  return event.delivered ? "Preview only · not sent" : "No confirmed delivery";
}

export function alertError(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

export function parseTargetList(value: string): string[] {
  return [...new Set(value.split(/[,\n]/).map((item) => item.trim()).filter(Boolean))];
}
