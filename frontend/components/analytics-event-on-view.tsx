"use client";

import { useEffect } from "react";

import { trackEvent } from "@/lib/analytics";

export function AnalyticsEventOnView({ eventName }: { eventName: string }) {
  useEffect(() => {
    trackEvent(eventName);
  }, [eventName]);

  return null;
}
