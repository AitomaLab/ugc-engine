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

type OrderedItem = {
    content: string;
    subItems: string[];
};

type ListBuffer =
    | { ordered: true; items: OrderedItem[] }
    | { ordered: false; items: string[] };

function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
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

const INSIGHT_ROW: React.CSSProperties = {
    display: 'flex',
    gap: 10,
    padding: '10px 12px',
    borderRadius: 8,
    background: 'rgba(148,163,184,0.08)',
};

/**
 * Shared list row style for AI Strategy / Learnings — grey pill rows with a
 * bullet and bold Label: description text.
 */
export function InsightList({
    items,
    keyPrefix = 'insight',
}: {
    items: string[];
    keyPrefix?: string;
}) {
    if (!items.length) return null;
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {items.map((item, i) => (
                <div key={`${keyPrefix}-${i}`} style={INSIGHT_ROW}>
                    <span
                        aria-hidden
                        style={{
                            width: 6,
                            height: 6,
                            borderRadius: '50%',
                            background: '#94A3B8',
                            marginTop: 6,
                            flexShrink: 0,
                        }}
                    />
                    <div style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--text-2)', minWidth: 0 }}>
                        {renderInline(item, `${keyPrefix}-${i}`)}
                    </div>
                </div>
            ))}
        </div>
    );
}

function renderOrderedList(items: OrderedItem[], key: string): React.ReactNode {
    const rows: string[] = [];
    for (const item of items) {
        if (item.subItems.length) {
            rows.push(item.content);
            for (const sub of item.subItems) rows.push(sub);
        } else {
            rows.push(item.content);
        }
    }
    return (
        <div key={key} style={{ margin: '4px 0 10px' }}>
            <InsightList items={rows} keyPrefix={key} />
        </div>
    );
}

function renderUnorderedList(items: string[], key: string): React.ReactNode {
    return (
        <div key={key} style={{ margin: '4px 0 10px' }}>
            <InsightList items={items} keyPrefix={key} />
        </div>
    );
}

export default function StrategyReportMarkdown({
    source,
    dense = false,
}: {
    source: string;
    /** Tighter spacing + 2-col ordered lists for account detail tabs. */
    dense?: boolean;
}) {
    const lines = source.replace(/\r\n/g, '\n').split('\n');
    const blocks: React.ReactNode[] = [];
    let listBuffer: ListBuffer | null = null;

    const flushList = () => {
        if (!listBuffer) return;
        const key = `list-${blocks.length}`;
        if (listBuffer.ordered) {
            blocks.push(renderOrderedList(listBuffer.items, key));
        } else {
            blocks.push(renderUnorderedList(listBuffer.items, key));
        }
        listBuffer = null;
    };

    const appendOrderedItem = (content: string) => {
        if (!listBuffer || !listBuffer.ordered) {
            flushList();
            listBuffer = { ordered: true, items: [] };
        }
        listBuffer.items.push({ content, subItems: [] });
    };

    const appendBulletToOrdered = (content: string) => {
        if (listBuffer?.ordered && listBuffer.items.length > 0) {
            listBuffer.items[listBuffer.items.length - 1].subItems.push(content);
            return true;
        }
        return false;
    };

    lines.forEach((raw, idx) => {
        const line = raw.trimEnd();
        const trimmed = line.trim();

        if (!trimmed) {
            // Blank lines do not terminate lists — LLM output often separates
            // numbered items and their sub-bullets with empty lines.
            return;
        }

        const heading = /^(#{1,6})\s+(.*)$/.exec(trimmed);
        if (heading) {
            flushList();
            const level = heading[1].length;
            const content = heading[2].replace(/^\*\*|\*\*$/g, '');
            const sizes: Record<number, number> = dense
                ? { 1: 16, 2: 13, 3: 12, 4: 11, 5: 11, 6: 11 }
                : { 1: 18, 2: 15, 3: 13, 4: 12, 5: 12, 6: 12 };
            blocks.push(
                <div
                    key={`h-${idx}`}
                    style={{
                        fontSize: sizes[level] || 13,
                        fontWeight: dense ? 700 : 800,
                        color: dense ? '#475569' : 'var(--text-1)',
                        margin: dense
                            ? (level <= 2 ? '8px 0 4px' : '6px 0 3px')
                            : (level <= 2 ? '14px 0 6px' : '10px 0 4px'),
                        letterSpacing: level <= 2 ? -0.2 : 0,
                    }}
                >
                    {renderInline(content, `h-${idx}`)}
                </div>,
            );
            return;
        }

        const ordered = /^\d+\.\s+(.*)$/.exec(trimmed);
        if (ordered) {
            appendOrderedItem(ordered[1]);
            return;
        }

        const bullet = /^[-*•]\s+(.*)$/.exec(trimmed);
        if (bullet) {
            if (appendBulletToOrdered(bullet[1])) return;
            if (!listBuffer || listBuffer.ordered) {
                flushList();
                listBuffer = { ordered: false, items: [] };
            }
            listBuffer.items.push(bullet[1]);
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
                style={{
                    margin: dense ? '0 0 6px' : '0 0 8px',
                    fontSize: dense ? 12.5 : 13,
                    lineHeight: 1.5,
                    color: 'var(--text-2)',
                }}
            >
                {renderInline(trimmed, `p-${idx}`)}
            </p>,
        );
    });

    flushList();

    return <div>{blocks}</div>;
}
