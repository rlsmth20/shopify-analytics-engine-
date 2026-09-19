/** Shared pointer/keyboard navigation, independent of rendering. */
export function chartIndexForKey(key: string, current: number, length: number): number | null {
  if (length < 1) return null;
  current = Math.max(0, Math.min(length - 1, current));
  if (key === "Home") return 0;
  if (key === "End") return length - 1;
  if (key === "ArrowLeft") return Math.max(0, current - 1);
  if (key === "ArrowRight") return Math.min(length - 1, current + 1);
  return null;
}

export function nearestChartPoint(x: number, positions: number[]): number {
  return positions.reduce((best, position, i) => Math.abs(position - x) < Math.abs(positions[best] - x) ? i : best, 0);
}

export function chartScale(values: number[]) {
  const minValue = Math.min(0, ...values);
  const maxValue = Math.max(1, ...values);
  const rough = (maxValue - minValue) / 4;
  const power = 10 ** Math.floor(Math.log10(rough));
  const fraction = rough / power;
  const step = (fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10) * power;
  const min = Math.floor(minValue / step) * step;
  const max = Math.ceil(maxValue / step) * step;
  const ticks = Array.from({ length: Math.round((max - min) / step) + 1 }, (_, i) => Number((min + i * step).toPrecision(12)));
  return { min, max, range: max - min, ticks };
}

export function reportPage(page: number, size: number, total: number) {
  const count = Math.max(1, Math.ceil(total / size));
  const index = Math.min(Math.max(0, page), count - 1);
  return { index, count, start: index * size, end: Math.min((index + 1) * size, total) };
}
