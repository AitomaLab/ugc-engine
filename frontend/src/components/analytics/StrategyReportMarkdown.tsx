'use client';

import React from 'react';

/**
 * Minimal, dependency-free Markdown renderer for the AI Strategy Report.
 *
 * The report is LLM-generated Markdown limited to headings, bold spans,
 * bullet/numbered lists and paragraphs. We render to React elements (never
 * `dangerouslySetInnerHTML`) so there's no XSS surface — any unsupported
 * syntax simply falls through as plain text.
 */

function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
    // Split on **bold** spans, keeping the delimiters via capture group.
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, i) => {
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

export default function StrategyReportMarkdown({ source }: { source: string }) {
    const lines = source.replace(/\r\n/g, '\n').split('\n');
    const blocks: React.ReactNode[] = [];
    let listBuffer: { ordered: boolean; items: string[] } | null = null;

    const flushList = () => {
        if (!listBuffer) return;
        const { ordered, items } = listBuffer;
        const key = `list-${blocks.length}`;
        const style: React.CSSProperties = {
            margin: '4px 0 10px',
            paddingLeft: 20,
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
            fontSize: 13,
            lineHeight: 1.55,
            color: 'var(--text-2)',
        };
        const children = items.map((it, i) => (
            <li key={`${key}-i-${i}`}>{renderInline(it, `${key}-i-${i}`)}</li>
        ));
        blocks.push(
            ordered
                ? <ol key={key} style={style}>{children}</ol>
                : <ul key={key} style={style}>{children}</ul>,
        );
        listBuffer = null;
    };

    lines.forEach((raw, idx) => {
        const line = raw.trimEnd();
        const trimmed = line.trim();

        if (!trimmed) {
            flushList();
            return;
        }

        const heading = /^(#{1,6})\s+(.*)$/.exec(trimmed);
        if (heading) {
            flushList();
            const level = heading[1].length;
            const content = heading[2].replace(/^\*\*|\*\*$/g, '');
            const sizes: Record<number, number> = { 1: 18, 2: 15, 3: 13, 4: 12, 5: 12, 6: 12 };
            blocks.push(
                <div
                    key={`h-${idx}`}
                    style={{
                        fontSize: sizes[level] || 13,
                        fontWeight: 800,
                        color: 'var(--text-1)',
                        margin: level <= 2 ? '14px 0 6px' : '10px 0 4px',
                        letterSpacing: level <= 2 ? -0.2 : 0,
                    }}
                >
                    {renderInline(content, `h-${idx}`)}
                </div>,
            );
            return;
        }

        const bullet = /^[-*]\s+(.*)$/.exec(trimmed);
        if (bullet) {
            if (!listBuffer || listBuffer.ordered) {
                flushList();
                listBuffer = { ordered: false, items: [] };
            }
            listBuffer.items.push(bullet[1]);
            return;
        }

        const ordered = /^\d+\.\s+(.*)$/.exec(trimmed);
        if (ordered) {
            if (!listBuffer || !listBuffer.ordered) {
                flushList();
                listBuffer = { ordered: true, items: [] };
            }
            listBuffer.items.push(ordered[1]);
            return;
        }

        if (/^(-{3,}|_{3,}|\*{3,})$/.test(trimmed)) {
            flushList();
            blocks.push(
                <hr key={`hr-${idx}`} style={{ border: 0, borderTop: '1px solid var(--border)', margin: '12px 0' }} />,
            );
            return;
        }

        flushList();
        blocks.push(
            <p
                key={`p-${idx}`}
                style={{ margin: '0 0 8px', fontSize: 13, lineHeight: 1.55, color: 'var(--text-2)' }}
            >
                {renderInline(trimmed, `p-${idx}`)}
            </p>,
        );
    });

    flushList();

    return <div>{blocks}</div>;
}
