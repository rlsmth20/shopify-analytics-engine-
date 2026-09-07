/** Canonical amounts take precedence over legacy estimates. Missing cost is not zero. */
export type FinancialProvenance = {
  cost_source?: "recorded" | "estimated_from_price" | "missing";
  financial_values_known?: boolean;
  financial_values?: Record<string, number | null>;
};

export type KnownValue = { value_known?: boolean; known_value?: number | null };

const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);

export function financialValue(row: FinancialProvenance, key: string, legacyValue: number | null | undefined): number | null {
  if (row.financial_values && Object.prototype.hasOwnProperty.call(row.financial_values, key)) {
    const value = row.financial_values[key];
    return finite(value) ? value : null;
  }
  if (row.financial_values_known === false || (row.cost_source && row.cost_source !== "recorded")) return null;
  return finite(legacyValue) ? legacyValue : null;
}

export function knownPointValue(point: KnownValue & { value: number }): number | null {
  if (point.value_known === false) return null;
  if (Object.prototype.hasOwnProperty.call(point, "known_value")) return finite(point.known_value) ? point.known_value : null;
  return finite(point.value) ? point.value : null;
}

export function financialTotal(values: Array<number | null>): number | null {
  return values.every(finite) ? values.reduce<number>((sum, value) => sum + value!, 0) : null;
}
