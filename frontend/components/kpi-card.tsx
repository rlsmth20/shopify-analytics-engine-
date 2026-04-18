import type { ReactNode } from "react";

export function KpiCard({
  label,
  value,
  note
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
}) {
  return (
    <article className="kpi-card">
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value">{value}</strong>
      {note ? <p className="kpi-note">{note}</p> : null}
    </article>
  );
}
