'use client';

import { useMemo } from 'react';
import type { TrendPoint } from './analytics-types';

interface Props {
    points: TrendPoint[];
    height?: number;
    /** Which series to plot. Defaults to engagement. */
    series?: 'engagement' | 'views' | 'posts';
}

/**
 * Inline SVG sparkline. Deliberately dependency-free — `recharts` /
 * `chart.js` are overkill for a ~30-point dataset and would balloon the
 * client bundle.
 *
 * Renders:
 *   • A smooth area chart of the selected series
 *   • Faint gridline at the midpoint for a sense of scale
 *   • Small dots at first / max / last so the user can read the swing
 *   • Date labels on the first and last buckets
 *
 * Empty state degrades gracefully to "No activity yet" copy.
 */
export default function TrendChart({ points, height = 140, series = 'engagement' }: Props) {
    const { path, areaPath, dots, maxValue, hasData } = useMemo(() => {
        const values = points.map((p) => (
            series === 'engagement' ? p.engagement
                : series === 'views' ? p.views
                : p.posts
        ));
        const max = Math.max(0, ...values);
        if (values.length === 0 || max === 0) {
            return { path: '', areaPath: '', dots: [], maxValue: 0, hasData: false };
        }
        const w = 1000;
        const h = 100;
        // Keep peak dots inside the viewBox (avoid clipping at y=0).
        const padY = 10;
        const plotH = h - padY * 2;
        const stepX = values.length > 1 ? w / (values.length - 1) : 0;
        const yFor = (v: number) => padY + plotH - (v / max) * plotH;

        const linePoints = values.map((v, i) => ({ x: i * stepX, y: yFor(v) }));
        const lineD = linePoints.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(' ');
        const areaD = `${lineD} L ${(values.length - 1) * stepX} ${h - padY} L 0 ${h - padY} Z`;

        const maxIndex = values.indexOf(max);
        const dotIndices = Array.from(new Set([0, maxIndex, values.length - 1]));
        const dotPositions = dotIndices.map((i) => ({
            x: linePoints[i].x,
            y: linePoints[i].y,
            value: values[i],
            isMax: i === maxIndex,
        }));

        return { path: lineD, areaPath: areaD, dots: dotPositions, maxValue: max, hasData: true };
    }, [points, series]);

    if (!hasData) {
        return (
            <div
                style={{
                    height,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'rgba(148,163,184,0.08)',
                    borderRadius: '10px',
                    color: 'var(--text-3)',
                    fontSize: '12px',
                    fontWeight: 600,
                }}
            >
                No activity in this window yet.
            </div>
        );
    }

    const firstDate = points[0]?.date;
    const lastDate = points[points.length - 1]?.date;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
            <svg
                viewBox="0 0 1000 100"
                preserveAspectRatio="none"
                style={{ width: '100%', height, display: 'block', overflow: 'visible' }}
                role="img"
                aria-label={`${series} trend over time, max ${maxValue}`}
            >
                <defs>
                    <linearGradient id="trendArea" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#337AFF" stopOpacity="0.28" />
                        <stop offset="100%" stopColor="#337AFF" stopOpacity="0.02" />
                    </linearGradient>
                </defs>
                <line
                    x1="0" y1="50" x2="1000" y2="50"
                    stroke="rgba(13,27,62,0.06)"
                    strokeWidth={1}
                    strokeDasharray="6 6"
                    vectorEffect="non-scaling-stroke"
                />
                <path d={areaPath} fill="url(#trendArea)" />
                <path
                    d={path}
                    fill="none"
                    stroke="#337AFF"
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    vectorEffect="non-scaling-stroke"
                />
                {dots.map((d, i) => (
                    <circle
                        key={i}
                        cx={d.x}
                        cy={d.y}
                        r={d.isMax ? 4.5 : 3}
                        fill={d.isMax ? '#337AFF' : 'white'}
                        stroke="#337AFF"
                        strokeWidth={2}
                        vectorEffect="non-scaling-stroke"
                    />
                ))}
            </svg>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-3)' }}>
                <span>{formatDate(firstDate)}</span>
                <span>Peak: <strong style={{ color: 'var(--text-2)' }}>{maxValue.toLocaleString()}</strong></span>
                <span>{formatDate(lastDate)}</span>
            </div>
        </div>
    );
}

function formatDate(iso: string | undefined): string {
    if (!iso) return '';
    try {
        const d = new Date(iso + 'T00:00:00Z');
        return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch {
        return iso;
    }
}
