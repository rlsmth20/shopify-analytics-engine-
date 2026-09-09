const LOGIN_DESTINATIONS = new Set(["/dashboard", "/import-stocky", "/import-shipstation"]);

export function loginDestination(value: string | null | undefined): string | null {
  return value && LOGIN_DESTINATIONS.has(value) ? value : null;
}

export function loginError(body: unknown): string {
  const fallback = "We couldn't send the link right now. Try again in a moment.";
  if (!body || typeof body !== "object" || !("detail" in body)) return fallback;
  const detail = (body as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return "Check your email address and try again.";
  if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") return detail.message;
  return fallback;
}
