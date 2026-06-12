'use client';

import { useMemo, useState } from 'react';
import type { CumulativePoint } from '../analytics-types';
import { formatCount } from '../analytics-types';

interface Props {
    points: CumulativePoint[];
    height?: number;
    /** Defaults to 'engagement' to match the dashboard headline KPI. */
    series?: 'engagement' | 'views' | 'posts';
}

/**
 * Cumulative growth area chart — pure SVG, no chart library.
 *
 * Why hand-rolled? Recharts is ~120 KB gzipped and we only need an area
 * curve with axes + a hover tooltip. The static-but-typed shape keeps the
 * component small and ensures the dashboard doesn't pay for a chart engine
 * we'd otherwise use only in this one place.
 *
 * Renders:
 *   • Y-axis with 4 grid lines + abbreviated tick labels
 *   • X-axis showing first/middle/last dates
 *   • Smooth gradient-filled area
 *   • Hover line + tooltip with the exact value/date
 */
export default function CumulativeGrowthChart({ points, height = 240, series = 'engagement' }: Props) {
    const [hover, setHover] = useState<{ x: number; pointIdx: number } | null>(null);

    const accentColor = '#337AFF';

    const layout = useMemo(() => {
        const values = points.map((p) =>
            series === 'views' ? p.views : series === 'posts' ? p.posts : p.engagement,
        );
        const max = Math.max(0, ...values);
        if (values.length === 0 || max === 0) {
            return { hasData: false, max: 0, values, gridTicks: [] as number[] };
        }
        const ceil = niceCeiling(max);
        const gridTicks = [0, 0.25, 0.5, 0.75, 1].map((p) => Math.round(ceil * p));
        return { hasData: true, max: ceil, values, gridTicks };
    }, [points, series]);

    if (!layout.hasData) {
        return (
            <div
                style={{
                    height,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: '#F8FAFC',
                    border: '1px dashed #E2E8F0',
                    borderRadius: '14px',
                    color: '#94A3B8',
                    fontSize: '13px',
                    fontWeight: 600,
                }}
            >
                No accumulated growth in this window yet.
            </div>
        );
    }

    const W = 1000;
    const H = 280;
    const PAD_L = 56;
    const PAD_R = 16;
    const PAD_T = 16;
    const PAD_B = 32;
    const innerW = W - PAD_L - PAD_R;
    const innerH = H - PAD_T - PAD_B;

    const xFor = (i: number) =>
        PAD_L + (layout.values.length === 1 ? innerW / 2 : (i / (layout.values.length - 1)) * innerW);
    const yFor = (v: number) => PAD_T + innerH - (v / layout.max) * innerH;

    const linePts = layout.values.map((v, i) => ({ x: xFor(i), y: yFor(v) }));
    const lineD = linePts
        .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`)
        .join(' ');
    const areaD = `${lineD} L ${linePts[linePts.length - 1].x} ${PAD_T + innerH} L ${linePts[0].x} ${PAD_T + innerH} Z`;

    const handlePointer = (e: React.PointerEvent<SVGSVGElement>) => {
        const svg = e.currentTarget;
        const rect = svg.getBoundingClientRect();
        const ratio = (e.clientX - rect.left) / rect.width;
        const xViewBox = ratio * W;
        const idx = Math.max(
            0,
            Math.min(
                layout.values.length - 1,
                Math.round(((xViewBox - PAD_L) / innerW) * (layout.values.length - 1)),
            ),
        );
        setHover({ x: xFor(idx), pointIdx: idx });
    };

    const hoverPoint = hover ? points[hover.pointIdx] : null;
    const hoverValue = hoverPoint
        ? series === 'views' ? hoverPoint.views : series === 'posts' ? hoverPoint.posts : hoverPoint.engagement
        : 0;

    const xLabels: Array<{ idx: number; text: string }> = [];
    if (points.length >= 2) {
        xLabels.push({ idx: 0, text: shortDate(points[0].date) });
        const mid = Math.floor(points.length / 2);
        if (mid > 0 && mid < points.length - 1) {
            xLabels.push({ idx: mid, text: shortDate(points[mid].date) });
        }
        xLabels.push({ idx: points.length - 1, text: shortDate(points[points.length - 1].date) });
    } else if (points.length === 1) {
        xLabels.push({ idx: 0, text: shortDate(points[0].date) });
    }

    return (
        <div style={{ position: 'relative' }}>
            <svg
                viewBox={`0 0 ${W} ${H}`}
                preserveAspectRatio="none"
                style={{ width: '100%', height, display: 'block', cursor: 'crosshair' }}
                onPointerMove={handlePointer}
                onPointerLeave={() => setHover(null)}
                role="img"
                aria-label={`Cumulative ${series} over time, peak ${formatCount(layout.max)}`}
            >
                <defs>
                    <linearGradient id={`grow-${series}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={accentColor} stopOpacity="0.32" />
                        <stop offset="100%" stopColor={accentColor} stopOpacity="0.02" />
                    </linearGradient>
                </defs>

                {/* Y grid + tick labels */}
                {layout.gridTicks.map((tick) => {
                    const y = yFor(tick);
                    return (
                        <g key={tick}>
                            <line
                                x1={PAD_L}
                                x2={W - PAD_R}
                                y1={y}
                                y2={y}
                                stroke="rgba(15,23,42,0.08)"
                                strokeWidth={1}
                            />
                            <text
                                x={PAD_L - 8}
                                y={y + 4}
                                textAnchor="end"
                                fontSize={11}
                                fontFamily="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
                                fill="#94A3B8"
                            >
                                {formatCount(tick)}
                            </text>
                        </g>
                    );
                })}

                {/* Area + line */}
                <path d={areaD} fill={`url(#grow-${series})`} />
                <path
                    d={lineD}
                    fill="none"
                    stroke={accentColor}
                    strokeWidth={2.4}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                />

                {/* X labels */}
                {xLabels.map((lab) => (
                    <text
                        key={lab.idx}
                        x={xFor(lab.idx)}
                        y={H - 8}
                        textAnchor="middle"
                        fontSize={11}
                        fontFamily="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
                        fill="#64748B"
                    >
                        {lab.text}
                    </text>
                ))}

                {/* Hover affordance */}
                {hover && hoverPoint && (
                    <g>
                        <line
                            x1={hover.x}
                            x2={hover.x}
                            y1={PAD_T}
                            y2={PAD_T + innerH}
                            stroke="rgba(15,23,42,0.25)"
                            strokeDasharray="4 4"
                            strokeWidth={1}
                        />
                        <circle
                            cx={hover.x}
                            cy={yFor(hoverValue)}
                            r={5}
                            fill={accentColor}
                            stroke="#FFFFFF"
                            strokeWidth={2}
                        />
                    </g>
                )}
            </svg>

            {hover && hoverPoint && (
                <div
                    style={{
                        position: 'absolute',
                        top: 0,
                        left: `${(hover.x / W) * 100}%`,
                        transform: 'translate(-50%, -8px)',
                        background: '#FFFFFF',
                        border: '1px solid #E2E8F0',
                        borderRadius: '10px',
                        padding: '8px 12px',
                        color: '#0F172A',
                        fontSize: '12px',
                        fontWeight: 600,
                        whiteSpace: 'nowrap',
                        boxShadow: '0 4px 16px rgba(15,23,42,0.10)',
                        pointerEvents: 'none',
                    }}
                >
                    <div style={{ color: '#94A3B8', fontSize: '10px', textTransform: 'uppercase', letterSpacing: 0.6 }}>
                        {longDate(hoverPoint.date)}
                    </div>
                    <div style={{ color: accentColor, marginTop: 2 }}>
                        {formatCount(hoverValue)} {series}
                    </div>
                </div>
            )}
        </div>
    );
}

function niceCeiling(value: number): number {
    if (value <= 0) return 1;
    const exp = Math.floor(Math.log10(value));
    const base = Math.pow(10, exp);
    const m = value / base;
    if (m <= 1) return 1 * base;
    if (m <= 2) return 2 * base;
    if (m <= 5) return 5 * base;
    return 10 * base;
}

function shortDate(iso: string): string {
    try {
        const d = new Date(iso + 'T00:00:00Z');
        return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch {
        return iso;
    }
}

function longDate(iso: string): string {
    try {
        const d = new Date(iso + 'T00:00:00Z');
        return d.toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' });
    } catch {
        return iso;
    }
}
