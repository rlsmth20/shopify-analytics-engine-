import type { ReactNode } from "react";

export function DataQualityNote({
  title,
  children,
  actions,
}: {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="data-quality-note">
      <div>
        <p className="data-quality-title">{title}</p>
        <div className="data-quality-copy">{children}</div>
      </div>
      {actions ? <div className="data-quality-actions">{actions}</div> : null}
    </div>
  );
}
