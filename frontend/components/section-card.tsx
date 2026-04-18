import type { ReactNode } from "react";

export function SectionCard({
  children,
  className = ""
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={`section-card ${className}`.trim()}>{children}</section>;
}
