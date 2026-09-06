export function isShopifyIdentityEmail(email: string): boolean {
  return /^shopify-(?:admin\+\d+|owner)@[^@\s]+\.myshopify\.com$/i.test(email.trim());
}

export function contactResponseError(ok: boolean, body: unknown): string | null {
  const response = body && typeof body === "object"
    ? body as Record<string, unknown>
    : null;
  if (ok && response?.ok === true) return null;
  if (typeof response?.detail === "string") return response.detail;
  if (Array.isArray(response?.detail)) {
    return "Check your name, reply email, and message, then try again.";
  }
  return "We couldn't confirm your message was sent. Please email hello@skubase.io directly.";
}
