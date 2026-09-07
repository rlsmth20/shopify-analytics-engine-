export type ScheduledEmailDelivery = {
  last_delivery_status?: "pending" | "accepted" | "failed" | "unavailable" | "unknown" | null;
  last_sent_at?: string | null;
  last_delivery_error?: string | null;
  delivery_attempts?: number;
  last_delivery_period?: string | null;
};
export type EmailSchedule = ScheduledEmailDelivery & { report_type: string; recipient_email: string; enabled: boolean };

export function scheduleDeliveryMessage(schedule?: ScheduledEmailDelivery | null): { text: string; needsReview: boolean } {
  if (!schedule?.last_delivery_status) return { text: "No delivery status is available for this schedule yet.", needsReview: false };
  if (schedule.last_delivery_status === "accepted") {
    const sentAt = schedule.last_sent_at ? new Date(schedule.last_sent_at) : null;
    const time = sentAt && Number.isFinite(sentAt.getTime()) ? ` on ${sentAt.toLocaleString()}` : "";
    return { text: `The email provider accepted the latest message${time}. Check the receiving inbox; acceptance does not confirm it arrived.`, needsReview: false };
  }
  if (schedule.last_delivery_status === "unknown") return { text: "The last delivery needs review. The message may have been accepted, so automatic retries for that message are paused.", needsReview: true };
  if ((schedule.delivery_attempts ?? 0) >= 3) return { text: "Delivery for the last scheduled period is paused after three attempts. Review the destination and contact support.", needsReview: true };
  if (schedule.last_delivery_status === "unavailable") return { text: "The email service or destination was unavailable for the last attempt. Review the recipient and contact support if this continues.", needsReview: true };
  if (schedule.last_delivery_status === "failed") return { text: "The last delivery attempt failed. Confirmed failures receive a limited number of retries.", needsReview: false };
  return { text: "The latest scheduled message is awaiting a confirmed delivery result.", needsReview: false };
}

export function readEmailSchedules(body: unknown): EmailSchedule[] {
  if (!body || typeof body !== "object" || !("schedules" in body) || !Array.isArray(body.schedules)) {
    throw new Error("Could not read saved email schedules. Try again before changing this setting.");
  }
  if (!body.schedules.every(row => row && typeof row.report_type === "string" && typeof row.recipient_email === "string" && typeof row.enabled === "boolean")) {
    throw new Error("The saved schedule response is incomplete. Try again before changing this setting.");
  }
  return body.schedules;
}

export function emailScheduleError(body: unknown, fallback: string): string {
  const detail = body && typeof body === "object" && "detail" in body ? body.detail : null;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.flatMap(item => item && typeof item.msg === "string" ? [item.msg] : []);
    if (messages.length) return messages.slice(0, 3).join(" ");
  }
  return fallback;
}

export function validScheduleEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}
