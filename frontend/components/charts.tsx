"use client";

// Lightweight, dependency-free SVG charts — keeps the bundle small and lets us
// style everything via CSS variables so the charts match the rest of the app.

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { chartIndexForKey, chartScale, nearestChartPoint } from "@/lib/chart-interaction";

type SeriesPoint = { label: string; value: number; x?: number };

function useChartWidth(hasData: boolean) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  useEffect(() => {
    if (!ref.current || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(280, Math.round(entry.contentRect.width))));
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [hasData]);
  return { ref, width };
}

// ---------------------------------------------------------------------------
// Sparkline — compact trendline for KPI cards
// ---------------------------------------------------------------------------

export function Sparkline({
  values,
  width = 120,
  height = 34,
  strokeClass = "spark-line",
  fillClass = "spark-fill",
}: {
  values: number[];
  width?: number;
  height?: number;
  strokeClass?: string;
  fillClass?: string;
}) {
  if (values.length === 0) return null;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const step = values.length > 1 ? width / (values.length - 1) : width;
  const points = values
    .map((v, i) => `${i * step},${height - ((v - min) / range) * height}`)
    .join(" ");
  const fillPath = `M 0,${height} L ${points.replace(/ /g, " L ")} L ${width},${height} Z`;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="sparkline">
      <path d={fillPath} className={fillClass} />
      <polyline points={points} fill="none" className={strokeClass} strokeWidth={2} />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Area Line Chart — revenue trend, forecast vs actual
// ---------------------------------------------------------------------------

export function AreaLineChart({
  points,
  height = 220,
  yFormatter = (v: number) => v.toFixed(0),
  label = "Trend",
  showDataTable = false,
}: {
  points: SeriesPoint[];
  height?: number;
  yFormatter?: (v: number) => string;
  label?: string;
  showDataTable?: boolean;
}) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const { ref, width } = useChartWidth(points.length > 0);
  const gradientId = useId();
  if (points.length === 0) {
    return <ChartEmpty height={height} />;
  }
  const padding = { top: 16, right: 16, bottom: 28, left: 80 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const values = points.map((p) => p.value);
  const { min, range, ticks: yTicks } = chartScale(values);

  const xStep = points.length > 1 ? chartWidth / (points.length - 1) : chartWidth;
  const dated = points.every((point) => point.x !== undefined && Number.isFinite(point.x));
  const startX = points[0].x ?? 0;
  const endX = points[points.length - 1].x ?? 0;
  const coords = points.map((p, i) => ({
    x: points.length === 1 ? padding.left + chartWidth / 2 :
      padding.left + (dated && endX > startX ? ((p.x! - startX) / (endX - startX)) * chartWidth : i * xStep),
    y: padding.top + chartHeight - ((p.value - min) / range) * chartHeight,
    label: p.label,
    value: p.value,
  }));

  const linePath = coords.map((c, i) => `${i === 0 ? "M" : "L"} ${c.x} ${c.y}`).join(" ");
  const areaPath = `${linePath} L ${coords[coords.length - 1].x} ${
    padding.top + chartHeight
  } L ${coords[0].x} ${padding.top + chartHeight} Z`;

  const selectedIndex = Math.min(activeIndex ?? points.length - 1, points.length - 1);
  const active = activeIndex === null ? null : coords[selectedIndex];

  return (
    <div className="interactive-chart" ref={ref}>
    <svg
      viewBox={`0 0 ${width} ${height}`}
      height={height}
      className="chart chart-area"
      role="img"
      aria-label={`${label}. ${points.length} observations. Use left and right arrow keys to explore values.`}
      tabIndex={0}
      onFocus={() => setActiveIndex(points.length - 1)}
      onKeyDown={(event) => {
        const next = chartIndexForKey(event.key, activeIndex ?? points.length - 1, points.length);
        if (next === null) return;
        event.preventDefault();
        setActiveIndex(next);
      }}
      onPointerMove={(event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        const x = ((event.clientX - rect.left) / rect.width) * width;
        setActiveIndex(nearestChartPoint(x, coords.map(point => point.x)));
      }}
      onPointerDown={(event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        setActiveIndex(nearestChartPoint((event.clientX - rect.left) / rect.width * width, coords.map(point => point.x)));
      }}
    >
      <title>{label}</title>
      <defs><linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--chart-color-1)" stopOpacity=".22" /><stop offset="100%" stopColor="var(--chart-color-1)" stopOpacity=".02" /></linearGradient></defs>
      {yTicks.map((t, i) => {
        const y = padding.top + chartHeight - ((t - min) / range) * chartHeight;
        return (
          <g key={i}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={y}
              y2={y}
              className="chart-grid"
            />
            <text x={padding.left - 8} y={y + 4} textAnchor="end" className="chart-tick">
              {yFormatter(t)}
            </text>
          </g>
        );
      })}

      <path d={areaPath} fill={`url(#${gradientId})`} />
      <path d={linePath} className="chart-area-line" fill="none" strokeWidth={2.5} />
      {active ? <g>
        <line x1={active.x} x2={active.x} y1={padding.top} y2={padding.top + chartHeight} className="chart-crosshair" />
        <circle cx={active.x} cy={active.y} r={5} className="chart-area-dot" />
      </g> : null}

      {coords.length <= 40 &&
        coords.map((c, i) => (
          <circle key={i} cx={c.x} cy={c.y} r={2.5} className="chart-area-dot" />
        ))}

      {coords.length > 1 && (
        <>
          <text
            x={coords[0].x}
            y={height - 8}
            textAnchor="start"
            className="chart-tick-x"
          >
            {coords[0].label}
          </text>
          <text
            x={coords[coords.length - 1].x}
            y={height - 8}
            textAnchor="end"
            className="chart-tick-x"
          >
            {coords[coords.length - 1].label}
          </text>
        </>
      )}
    </svg>
    <div className="chart-explorer">
      <button type="button" aria-label={`Previous value in ${label}`} disabled={selectedIndex === 0} onClick={() => setActiveIndex(Math.max(0, selectedIndex - 1))}>←</button>
      <p className="chart-readout" aria-live="polite">{active ? <><strong>{active.label}</strong><span>{yFormatter(active.value)}</span></> : <><strong>{coords.at(-1)!.label}</strong><span>{yFormatter(coords.at(-1)!.value)}</span></>}</p>
      <button type="button" aria-label={`Next value in ${label}`} disabled={selectedIndex === points.length - 1} onClick={() => setActiveIndex(Math.min(points.length - 1, selectedIndex + 1))}>→</button>
    </div>
    <p className="chart-help">Hover or tap to inspect. Arrow keys move between values.</p>
    {showDataTable ? <details className="chart-data-table">
      <summary>View chart data</summary>
      <div className="table-scroll"><table><caption>{label}</caption><thead><tr><th scope="col">Date</th><th scope="col">Value</th></tr></thead><tbody>
        {points.map((point, index) => <tr key={`${point.label}-${index}`}><td>{point.label}</td><td>{yFormatter(point.value)}</td></tr>)}
      </tbody></table></div>
    </details> : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Horizontal Bar Chart — top movers, cash at risk by vendor
// ---------------------------------------------------------------------------

export function HorizontalBarChart({
  points,
  valueFormatter = (v: number) => String(v),
  barClassName = "chart-hbar",
}: {
  points: SeriesPoint[];
  valueFormatter?: (v: number) => string;
  barClassName?: string;
}) {
  const [sort, setSort] = useState("original");
  const [selected, setSelected] = useState<SeriesPoint | null>(null);
  if (points.length === 0) return <ChartEmpty height={120} />;
  const max = Math.max(...points.map((p) => p.value), 1);
  const shown = sort === "original" ? points : [...points].sort((a, b) => sort === "largest" ? b.value - a.value : a.label.localeCompare(b.label));
  return (
    <div className="hbar-wrapper">
      <label className="chart-sort">Order by <select value={sort} onChange={event => setSort(event.target.value)}><option value="original">Original ranking</option><option value="largest">Largest value</option><option value="name">Name</option></select></label>
      {shown.map((p, index) => (
        <button type="button" key={`${p.label}-${index}`} className={`hbar-row chart-select-row${selected === p ? " is-active" : ""}`} onClick={() => setSelected(p)} onFocus={() => setSelected(p)} onMouseEnter={() => setSelected(p)} aria-label={`${p.label}: ${valueFormatter(p.value)}`}>
          <span className="hbar-label" title={p.label}>
            {p.label}
          </span>
          <span className="hbar-track">
            <span
              className={`hbar-fill ${barClassName}`}
              style={{ width: `${Math.max((p.value / max) * 100, 0)}%` }}
            />
          </span>
          <span className="hbar-value">{valueFormatter(p.value)}</span>
        </button>
      ))}
      {selected && points.includes(selected) ? <p className="chart-selection" aria-live="polite"><strong>{selected.label}</strong><span>{valueFormatter(selected.value)}</span></p> : <p className="chart-help">Select a row to inspect the full label and value.</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Donut Chart — stock health, ABC distribution, alert severity
// ---------------------------------------------------------------------------

const DONUT_PALETTE = [
  "var(--chart-color-1)",
  "var(--chart-color-2)",
  "var(--chart-color-3)",
  "var(--chart-color-4)",
  "var(--chart-color-5)",
  "var(--chart-color-6)",
];

export function DonutChart({
  points,
  size = 180,
  stroke = 22,
  centerLabel,
  centerValue,
}: {
  points: SeriesPoint[];
  size?: number;
  stroke?: number;
  centerLabel?: string;
  centerValue?: string;
}) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const total = points.reduce((s, p) => s + p.value, 0);
  if (total === 0) return <ChartEmpty height={size} />;

  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  const active = activeIndex === null ? null : points[activeIndex];

  return (
    <div className="donut-wrapper">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Distribution of ${centerLabel ?? "total"}. Explore categories using the buttons below.`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={stroke}
          fill="none"
          className="donut-bg"
        />
        {points.map((p, i) => {
          const frac = p.value / total;
          const dash = frac * circumference;
          const gap = circumference - dash;
          const rotation = (offset / circumference) * 360;
          offset += dash;
          return (
            <circle
              key={p.label}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              strokeWidth={stroke}
              fill="none"
              strokeDasharray={`${dash} ${gap}`}
              strokeDashoffset={0}
              transform={`rotate(${rotation - 90} ${size / 2} ${size / 2})`}
              stroke={DONUT_PALETTE[i % DONUT_PALETTE.length]}
              strokeLinecap="butt"
              opacity={active && activeIndex !== i ? .22 : 1}
              onPointerEnter={() => setActiveIndex(i)}
              onClick={() => setActiveIndex(i)}
            />
          );
        })}
      </svg>
      <div className="donut-center">
        <div className="donut-value">{active ? `${(active.value / total * 100).toFixed(1)}%` : centerValue ?? total.toLocaleString()}</div>
        <div className="donut-label">{active ? active.label : centerLabel ?? "Total"}</div>
      </div>
      <div className="donut-legend">
        {points.map((p, i) => (
          <button type="button" key={p.label} className="donut-legend-item" aria-pressed={activeIndex === i} onClick={() => setActiveIndex(i)} onFocus={() => setActiveIndex(i)}>
            <span
              className="donut-legend-swatch"
              style={{ background: DONUT_PALETTE[i % DONUT_PALETTE.length] }}
            />
            <span className="donut-legend-label">{p.label}</span>
            <span className="donut-legend-value">{p.value.toLocaleString()} <small>{(p.value / total * 100).toFixed(1)}%</small></span>
          </button>
        ))}
        <button type="button" className="chart-reset" onClick={() => setActiveIndex(null)}>Show total</button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Diverging Bar Chart — forecast accuracy (+/-) around zero
// ---------------------------------------------------------------------------

export function DivergingBarChart({
  points,
  valueFormatter = (v: number) => `${v.toFixed(1)}%`,
}: {
  points: SeriesPoint[];
  valueFormatter?: (v: number) => string;
}) {
  if (points.length === 0) return <ChartEmpty height={120} />;
  const max = Math.max(...points.map((p) => Math.abs(p.value)), 1);
  return (
    <div className="diverging-wrapper">
      {points.map((p) => {
        const widthPct = (Math.abs(p.value) / max) * 50; // 50% track either side
        const isPositive = p.value >= 0;
        return (
          <div key={p.label} className="diverging-row">
            <span className="diverging-label" title={p.label}>
              {p.label}
            </span>
            <div className="diverging-track">
              <div className="diverging-axis" />
              <div
                className={isPositive ? "diverging-bar pos" : "diverging-bar neg"}
                style={{
                  width: `${widthPct}%`,
                  [isPositive ? "left" : "right"]: "50%",
                }}
              />
            </div>
            <span
              className={`diverging-value ${isPositive ? "pos" : "neg"}`}
              title={valueFormatter(p.value)}
            >
              {valueFormatter(p.value)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Forecast band chart — expected line + confidence interval band
// ---------------------------------------------------------------------------

export function ForecastBandChart({
  points,
  height = 220,
}: {
  points: { day_offset: number; expected_units: number; lower_bound: number; upper_bound: number }[];
  height?: number;
}) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [showRange, setShowRange] = useState(true);
  const { ref, width } = useChartWidth(points.length > 0);
  if (points.length === 0) return <ChartEmpty height={height} />;
  const padding = { top: 14, right: 16, bottom: 28, left: 64 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const values = points.flatMap((p) => [p.expected_units, p.upper_bound, p.lower_bound]);
  const { min, range, ticks: yTicks } = chartScale(values);
  const firstDay = points[0].day_offset;
  const dayRange = points[points.length - 1].day_offset - firstDay;

  const mapY = (v: number) =>
    padding.top + chartHeight - ((v - min) / range) * chartHeight;
  const mapX = (i: number) => padding.left + (dayRange > 0 ? (points[i].day_offset - firstDay) / dayRange * chartWidth : chartWidth / 2);

  const upperPath = points.map((p, i) => `${i === 0 ? "M" : "L"} ${mapX(i)} ${mapY(p.upper_bound)}`).join(" ");
  const lowerReversed = [...points].reverse();
  const bandPath = `${upperPath} ${lowerReversed
    .map((p, i) => `L ${mapX(points.length - 1 - i)} ${mapY(p.lower_bound)}`)
    .join(" ")} Z`;
  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"} ${mapX(i)} ${mapY(p.expected_units)}`).join(" ");

  const selectedIndex = Math.min(activeIndex, points.length - 1);
  const active = points[selectedIndex];
  const format = (value: number) => value.toLocaleString(undefined, { maximumFractionDigits: 1 });
  return (
    <div ref={ref} className="interactive-chart">
    <label className="chart-range-toggle"><input type="checkbox" checked={showRange} onChange={event => setShowRange(event.target.checked)} /> Show forecast range</label>
    <svg viewBox={`0 0 ${width} ${height}`} height={height} className="chart chart-forecast" role="img" tabIndex={0}
      aria-label="Forecast units and range. Use left and right arrow keys to explore each day."
      onKeyDown={event => { const next = chartIndexForKey(event.key, selectedIndex, points.length); if (next !== null) { event.preventDefault(); setActiveIndex(next); } }}
      onPointerMove={event => { const rect = event.currentTarget.getBoundingClientRect(); setActiveIndex(nearestChartPoint((event.clientX - rect.left) / rect.width * width, points.map((_, i) => mapX(i)))); }}
      onPointerDown={event => { const rect = event.currentTarget.getBoundingClientRect(); setActiveIndex(nearestChartPoint((event.clientX - rect.left) / rect.width * width, points.map((_, i) => mapX(i)))); }}>
      <title>Forecast units with lower and upper bounds</title>
      {yTicks.map((t, i) => {
        const y = mapY(t);
        return (
          <g key={i}>
            <line x1={padding.left} x2={width - padding.right} y1={y} y2={y} className="chart-grid" />
            <text x={padding.left - 8} y={y + 4} textAnchor="end" className="chart-tick">
              {format(t)}
            </text>
          </g>
        );
      })}
      {showRange ? <path d={bandPath} className="forecast-band" /> : null}
      <path d={linePath} className="forecast-line" fill="none" strokeWidth={2.5} />
      <line x1={mapX(selectedIndex)} x2={mapX(selectedIndex)} y1={padding.top} y2={padding.top + chartHeight} className="chart-crosshair" />
      <circle cx={mapX(selectedIndex)} cy={mapY(active.expected_units)} r={5} className="chart-area-dot" />
      <text x={padding.left} y={height - 8} className="chart-tick-x">
        Day +{firstDay}
      </text>
      <text x={width - padding.right} y={height - 8} textAnchor="end" className="chart-tick-x">
        Day +{points[points.length - 1].day_offset}
      </text>
    </svg>
    <p className="chart-readout" aria-live="polite"><strong>Day +{active.day_offset}</strong><span>{format(active.expected_units)} expected units</span><span>Range {format(active.lower_bound)}–{format(active.upper_bound)}</span></p>
    <label className="chart-day-slider">Explore forecast day<input type="range" min={0} max={points.length - 1} value={selectedIndex} onChange={event => setActiveIndex(Number(event.target.value))} aria-valuetext={`Day ${active.day_offset}: ${format(active.expected_units)} expected units`} /></label>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pie of weekly seasonality
// ---------------------------------------------------------------------------

export function WeekdayIndexBars({ index }: { index: number[] }) {
  if (index.length === 0) return null;
  const labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const max = Math.max(...index, 1.1);
  return (
    <div className="weekday-bars">
      {index.map((v, i) => (
        <div key={i} className="weekday-col">
          <div className="weekday-track">
            <div
              className="weekday-bar"
              style={{ height: `${(v / max) * 100}%` }}
              title={`${labels[i]} index ${v.toFixed(2)}`}
            />
          </div>
          <div className="weekday-label">{labels[i]}</div>
          <div className="weekday-value">{v.toFixed(2)}</div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared empty state
// ---------------------------------------------------------------------------

function ChartEmpty({ height }: { height: number }) {
  return (
    <div className="chart-empty" style={{ height }}>
      <span>No data</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Utility wrapper for putting charts inside section cards
// ---------------------------------------------------------------------------

export function ChartPanel({
  title,
  subtitle,
  children,
  footer,
  accent,
  className,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
  accent?: "primary" | "warning" | "danger" | "success";
  className?: string;
}) {
  const classes = [
    "chart-panel",
    accent ? `chart-panel-${accent}` : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={classes}>
      <div className="chart-panel-head">
        <h3 className="chart-panel-title">{title}</h3>
        {subtitle ? <p className="chart-panel-subtitle">{subtitle}</p> : null}
      </div>
      <div className="chart-panel-body">{children}</div>
      {footer ? <div className="chart-panel-foot">{footer}</div> : null}
    </div>
  );
}
