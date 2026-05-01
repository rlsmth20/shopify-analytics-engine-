"use client";

// Lightweight, dependency-free SVG charts — keeps the bundle small and lets us
// style everything via CSS variables so the charts match the rest of the app.

import type { ReactNode } from "react";

type SeriesPoint = { label: string; value: number };

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
}: {
  points: SeriesPoint[];
  height?: number;
  yFormatter?: (v: number) => string;
}) {
  if (points.length === 0) {
    return <ChartEmpty height={height} />;
  }
  const width = 640;
  const padding = { top: 16, right: 16, bottom: 28, left: 48 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const values = points.map((p) => p.value);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 1);
  const range = max - min || 1;

  const xStep = points.length > 1 ? chartWidth / (points.length - 1) : chartWidth;
  const coords = points.map((p, i) => ({
    x: padding.left + i * xStep,
    y: padding.top + chartHeight - ((p.value - min) / range) * chartHeight,
    label: p.label,
    value: p.value,
  }));

  const linePath = coords.map((c, i) => `${i === 0 ? "M" : "L"} ${c.x} ${c.y}`).join(" ");
  const areaPath = `${linePath} L ${coords[coords.length - 1].x} ${
    padding.top + chartHeight
  } L ${coords[0].x} ${padding.top + chartHeight} Z`;

  // Y ticks
  const ticks = 4;
  const yTicks = Array.from({ length: ticks + 1 }, (_, i) => min + (range * i) / ticks);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className="chart chart-area"
      role="img"
    >
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

      <path d={areaPath} className="chart-area-fill" />
      <path d={linePath} className="chart-area-line" fill="none" strokeWidth={2.5} />

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
  if (points.length === 0) return <ChartEmpty height={120} />;
  const max = Math.max(...points.map((p) => p.value), 1);
  return (
    <div className="hbar-wrapper">
      {points.map((p) => (
        <div key={p.label} className="hbar-row">
          <span className="hbar-label" title={p.label}>
            {p.label}
          </span>
          <div className="hbar-track">
            <div
              className={barClassName}
              style={{ width: `${Math.max((p.value / max) * 100, 2)}%` }}
            />
          </div>
          <span className="hbar-value">{valueFormatter(p.value)}</span>
        </div>
      ))}
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
  const total = points.reduce((s, p) => s + p.value, 0);
  if (total === 0) return <ChartEmpty height={size} />;

  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="donut-wrapper">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
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
            />
          );
        })}
      </svg>
      <div className="donut-center">
        <div className="donut-value">{centerValue ?? total.toString()}</div>
        <div className="donut-label">{centerLabel ?? "Total"}</div>
      </div>
      <div className="donut-legend">
        {points.map((p, i) => (
          <div key={p.label} className="donut-legend-item">
            <span
              className="donut-legend-swatch"
              style={{ background: DONUT_PALETTE[i % DONUT_PALETTE.length] }}
            />
            <span className="donut-legend-label">{p.label}</span>
            <span className="donut-legend-value">— {p.value.toLocaleString()}</span>
          </div>
        ))}
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
  if (points.length === 0) return <ChartEmpty height={height} />;
  const width = 640;
  const padding = { top: 14, right: 16, bottom: 28, left: 44 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const values = points.flatMap((p) => [p.expected_units, p.upper_bound, p.lower_bound]);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 1);
  const range = max - min || 1;
  const xStep = points.length > 1 ? chartWidth / (points.length - 1) : chartWidth;

  const mapY = (v: number) =>
    padding.top + chartHeight - ((v - min) / range) * chartHeight;
  const mapX = (i: number) => padding.left + i * xStep;

  const upperPath = points.map((p, i) => `${i === 0 ? "M" : "L"} ${mapX(i)} ${mapY(p.upper_bound)}`).join(" ");
  const lowerReversed = [...points].reverse();
  const bandPath = `${upperPath} ${lowerReversed
    .map((p, i) => `L ${mapX(points.length - 1 - i)} ${mapY(p.lower_bound)}`)
    .join(" ")} Z`;
  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"} ${mapX(i)} ${mapY(p.expected_units)}`).join(" ");

  const yTicks = [min, min + range / 2, max];
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart chart-forecast" role="img">
      {yTicks.map((t, i) => {
        const y = mapY(t);
        return (
          <g key={i}>
            <line x1={padding.left} x2={width - padding.right} y1={y} y2={y} className="chart-grid" />
            <text x={padding.left - 8} y={y + 4} textAnchor="end" className="chart-tick">
              {t.toFixed(1)}
            </text>
          </g>
        );
      })}
      <path d={bandPath} className="forecast-band" />
      <path d={linePath} className="forecast-line" fill="none" strokeWidth={2.5} />
      <text x={padding.left} y={height - 8} className="chart-tick-x">
        Day +1
      </text>
      <text x={width - padding.right} y={height - 8} textAnchor="end" className="chart-tick-x">
        Day +{points.length}
      </text>
    </svg>
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
