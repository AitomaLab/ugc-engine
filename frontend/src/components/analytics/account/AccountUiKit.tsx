'use client';

import React from 'react';

/**
 * Shared, dependency-free UI atoms for the account detail tabs
 * (Overview / AI Strategy / AI Learnings). Kept tiny and local so each tab
 * reads top-to-bottom without hunting through the big modal file.
 */

/** Bold-aware inline renderer for `**bold**` spans (no dangerouslySetInnerHTML). */
export function renderInlineBold(text: string, keyPrefix: string): React.ReactNode[] {
    return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) => {
        const bold = /^\*\*([^*]+)\*\*$/.exec(part);
        if (bold) {
            return (
                <strong key={`${keyPrefix}-b-${i}`} style={{ color: 'var(--text-1)', fontWeight: 700 }}>
                    {bold[1]}
                </strong>
            );
        }
        return <React.Fragment key={`${keyPrefix}-t-${i}`}>{part}</React.Fragment>;
    });
}

/** Uppercase section header with an optional right-aligned action slot. */
export function Section({
    title,
    subtitle,
    action,
    children,
}: {
    title: string;
    subtitle?: string;
    action?: React.ReactNode;
    children: React.ReactNode;
}) {
    return (
        <section style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                    <h3 style={{ margin: 0, fontSize: 12, fontWeight: 700, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                        {title}
                    </h3>
                    {subtitle && (
                        <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{subtitle}</span>
                    )}
                </div>
                {action}
            </div>
            {children}
        </section>
    );
}

/** Compact KPI tile used in the Overview header strip. */
export function StatCell({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
    return (
        <div
            style={{
                background: 'white',
                border: '1px solid var(--border)',
                borderRadius: 10,
                padding: '10px 12px',
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
                minWidth: 0,
            }}
        >
            <span style={{ fontSize: 16, fontWeight: 800, color: accent ? 'var(--blue)' : 'var(--text-1)', fontVariantNumeric: 'tabular-nums' }}>
                {value}
            </span>
            <span style={{ fontSize: 10, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: 0.4 }}>
                {label}
            </span>
        </div>
    );
}

/** White rounded panel wrapper for section bodies. */
export function Panel({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
    return (
        <div
            style={{
                background: 'white',
                border: '1px solid var(--border)',
                borderRadius: 14,
                padding: '16px 18px',
                ...style,
            }}
        >
            {children}
        </div>
    );
}

/** Dashed placeholder used for pending / empty states. */
export function EmptyNote({ children }: { children: React.ReactNode }) {
    return (
        <div
            style={{
                background: 'rgba(51,122,255,0.05)',
                border: '1px dashed var(--border)',
                borderRadius: 12,
                padding: '16px 18px',
                fontSize: 13,
                color: 'var(--text-2)',
                lineHeight: 1.5,
            }}
        >
            {children}
        </div>
    );
}
