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

function renderOrderedList(items: OrderedItem[], key: string): React.ReactNode {
    return (
        <div
            key={key}
            style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
                margin: '8px 0 14px',
            }}
        >
            {items.map((item, i) => (
                <div
                    key={`${key}-${i}`}
                    style={{
                        display: 'flex',
                        gap: 12,
                        padding: '12px 14px',
                        background: 'var(--blue-light)',
                        border: '1px solid var(--border)',
                        borderRadius: 10,
                    }}
                >
                    <div
                        aria-hidden
                        style={{
                            width: 28,
                            height: 28,
                            borderRadius: '50%',
                            background: 'var(--blue)',
                            color: '#fff',
                            fontSize: 13,
                            fontWeight: 700,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                        }}
                    >
                        {i + 1}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                        <div
                            style={{
                                fontSize: 13,
                                fontWeight: 600,
                                color: 'var(--text-1)',
                                lineHeight: 1.45,
                                marginBottom: item.subItems.length ? 6 : 0,
                            }}
                        >
                            {renderInline(item.content, `${key}-${i}-c`)}
                        </div>
                        {item.subItems.length > 0 && (
                            <ul
                                style={{
                                    margin: 0,
                                    paddingLeft: 18,
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: 4,
                                    fontSize: 13,
                                    lineHeight: 1.55,
                                    color: 'var(--text-2)',
                                }}
                            >
                                {item.subItems.map((sub, j) => (
                                    <li key={`${key}-${i}-s-${j}`}>
                                        {renderInline(sub, `${key}-${i}-s-${j}`)}
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
}

function renderUnorderedList(items: string[], key: string): React.ReactNode {
    return (
        <ul
            key={key}
            style={{
                margin: '4px 0 10px',
                paddingLeft: 20,
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
                fontSize: 13,
                lineHeight: 1.55,
                color: 'var(--text-2)',
            }}
        >
            {items.map((it, i) => (
                <li key={`${key}-i-${i}`}>{renderInline(it, `${key}-i-${i}`)}</li>
            ))}
        </ul>
    );
}

export default function StrategyReportMarkdown({ source }: { source: string }) {
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
                style={{ margin: '0 0 8px', fontSize: 13, lineHeight: 1.55, color: 'var(--text-2)' }}
            >
                {renderInline(trimmed, `p-${idx}`)}
            </p>,
        );
    });

    flushList();

    return <div>{blocks}</div>;
}
