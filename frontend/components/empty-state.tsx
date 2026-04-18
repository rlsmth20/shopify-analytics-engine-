import type { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  tone = "default",
  actions
}: {
  title: string;
  description: string;
  tone?: "default" | "error";
  actions?: ReactNode;
}) {
  return (
    <div className={`empty-state empty-state-${tone}`}>
      <div>
        <p className="empty-state-title">{title}</p>
        <p className="empty-state-copy">{description}</p>
      </div>
      {actions ? <div className="empty-state-actions">{actions}</div> : null}
    </div>
  );
}
