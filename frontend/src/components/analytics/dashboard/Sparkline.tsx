'use client';

import { useMemo } from 'react';

interface Props {
    values: number[];
    color?: string;
    height?: number;
    fill?: boolean;
}

/**
 * Tiny dependency-free sparkline used inside KPI cards. Renders a smooth
 * area curve (or just a line when `fill` is false) without grid lines or
 * axes — meant to read as a "trend snapshot" not a precise chart.
 */
export default function Sparkline({ values, color = '#337AFF', height = 56, fill = true }: Props) {
    const { line, area, hasData } = useMemo(() => {
        if (!values.length) return { line: '', area: '', hasData: false };
        const max = Math.max(0, ...values);
        if (max === 0) return { line: '', area: '', hasData: false };
        const w = 200;
        const h = 60;
        const stepX = values.length > 1 ? w / (values.length - 1) : 0;
        const yFor = (v: number) => h - (v / max) * h;
        const pts = values.map((v, i) => ({ x: i * stepX, y: yFor(v) }));
        const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(' ');
        const last = pts[pts.length - 1];
        const area = `${line} L ${last.x.toFixed(2)} ${h} L 0 ${h} Z`;
        return { line, area, hasData: true };
    }, [values]);

    if (!hasData) {
        return (
            <div
                aria-hidden
                style={{
                    height,
                    width: '100%',
                    background: 'linear-gradient(90deg, #F1F5F9, #F8FAFC)',
                    borderRadius: 6,
                }}
            />
        );
    }

    const gradientId = `spark-${color.replace(/[^a-zA-Z0-9]/g, '')}`;

    return (
        <svg
            viewBox="0 0 200 60"
            preserveAspectRatio="none"
            style={{ width: '100%', height, display: 'block' }}
            aria-hidden
        >
            <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity="0.45" />
                    <stop offset="100%" stopColor={color} stopOpacity="0" />
                </linearGradient>
            </defs>
            {fill && <path d={area} fill={`url(#${gradientId})`} />}
            <path
                d={line}
                fill="none"
                stroke={color}
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
            />
        </svg>
    );
}
