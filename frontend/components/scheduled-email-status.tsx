import { scheduleDeliveryMessage, type ScheduledEmailDelivery } from "@/lib/email-schedule";

export function ScheduledEmailStatus({ delivery }: { delivery?: ScheduledEmailDelivery | null }) {
  const status = scheduleDeliveryMessage(delivery);
  const detail = typeof delivery?.last_delivery_error === "string" ? delivery.last_delivery_error : null;
  return <p className="section-copy" role="status">{status.text}{detail ? <> {detail}</> : null}{status.needsReview ? <> <a href="mailto:info@skubase.io?subject=Scheduled%20email%20delivery">Contact Skubase</a></> : null}</p>;
}
