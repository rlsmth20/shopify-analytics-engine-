import type { ReactNode } from "react";

import { SectionCard } from "@/components/section-card";

export function ChartCard({
  title,
  description,
  children
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <SectionCard className="chart-card">
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">Analytics</p>
          <h2 className="section-title section-title-small">{title}</h2>
        </div>
        <p className="section-copy">{description}</p>
      </div>
      {children}
    </SectionCard>
  );
}
