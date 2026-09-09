export const SESSION_CHANGED_KEY = "skubase_session_changed";

export function announceSessionChange(): void {
  try {
    localStorage.setItem(SESSION_CHANGED_KEY, `${Date.now()}:${Math.random()}`);
  } catch {
    // Optional cross-tab notification, never a prerequisite for authentication.
  }
}

export function workspaceStorageKey(key: string, user: { id: number; shop_id?: number }): string {
  return `${key}:user:${user.id}:shop:${user.shop_id ?? "unknown"}`;
}

export function readChecklist(raw: string | null): Record<string, boolean> {
  try {
    const parsed: unknown = JSON.parse(raw || "{}");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return Object.fromEntries(Object.entries(parsed).filter(([, value]) => value === true));
  } catch { return {}; }
}
