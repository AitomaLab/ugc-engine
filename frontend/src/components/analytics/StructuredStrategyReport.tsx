'use client';

import React, { useEffect, useMemo, useState } from 'react';
import StrategyReportMarkdown, { InsightList } from './StrategyReportMarkdown';

/**
 * Visual layout for AI Strategy / AI Learnings Markdown.
 *
 * Splits on ## / ### headings and maps known section types to cards.
 * Unrecognized sections fall back to denser StrategyReportMarkdown.
 * Report text is unchanged — presentation only.
 */

type SectionKind =
    | 'title'
    | 'stats'
    | 'top'
    | 'bottom'
    | 'doMore'
    | 'doLess'
    | 'priority'
    | 'generic';

interface ReportSection {
    heading: string;
    level: number;
    body: string;
    kind: SectionKind;
}

function classifyHeading(heading: string): SectionKind {
    const h = heading.toLowerCase();
    if (/\b(do more|replicate|keep doing)\b/.test(h)) return 'doMore';
    if (/\b(do less|avoid|stop)\b/.test(h)) return 'doLess';
    if (/\b(priority|what to do next|next steps|recommend)\b/.test(h)) return 'priority';
    if (/\b(bottom|underperform|went wrong|holding)\b/.test(h)) return 'bottom';
    if (/\b(top|why they worked|key factor|performers analysis|driving)\b/.test(h)) return 'top';
    if (/\b(overview|baseline|followers|summary|performance analysis)\b/.test(h)) return 'stats';
    return 'generic';
}

/** Compact labels for the side nav so long LLM headings don’t truncate. */
function shortNavLabel(heading: string): string {
    const h = heading.toLowerCase().trim();
    if (/\boverview\b/.test(h) || /\bsummary\b/.test(h)) return 'Overview';
    if (/\bmetric/.test(h) && !/\b(top|bottom)\b/.test(h)) return 'Metrics';
    if (/\bfactor/.test(h) && /\b(holding|back|under)\b/.test(h)) return 'Holding';
    if (/\bfactor/.test(h) && /\b(driving|why|worked|engagement)\b/.test(h)) return 'Driving';
    if (/\bfactor/.test(h)) return 'Factors';
    if (/\bholding\b/.test(h) && /\bengagement\b/.test(h)) return 'Holding';
    if (/\bdriving\b/.test(h) && /\bengagement\b/.test(h)) return 'Driving';
    if (/\btop performer/.test(h) && /\b(data|metric)\b/.test(h)) return 'Top data';
    if (/\bbottom performer/.test(h) && /\b(data|metric)\b/.test(h)) return 'Low data';
    if (/\btop performer/.test(h) || /\bwhy they worked\b/.test(h)) return 'Top posts';
    if (/\bbottom performer/.test(h) || /\bwent wrong\b/.test(h)) return 'Low posts';
    if (/\bwhat worked\b/.test(h)) return 'What worked';
    if (/\brecommend/.test(h) || /\bwhat to do next\b/.test(h) || /\bpriority\b/.test(h)) return 'Actions';
    if (/\bdo more\b/.test(h)) return 'Do more';
    if (/\bdo less\b/.test(h)) return 'Do less';
    if (/\bmetric/.test(h) && /\btop\b/.test(h)) return 'Top data';
    if (/\bmetric/.test(h) && /\bbottom\b/.test(h)) return 'Low data';
    // Fallback: trim filler words and keep labels short enough for the nav column
    const cleaned = heading
        .replace(/\b(analysis|report|section|the|for|and|key|factors?|engagement)\b/gi, ' ')
        .replace(/\s+/g, ' ')
        .trim();
    if (cleaned.length <= 14) return cleaned || heading;
    return `${cleaned.slice(0, 12).trimEnd()}…`;
}

function parseSections(source: string): { preamble: string; sections: ReportSection[] } {
    const lines = source.replace(/\r\n/g, '\n').split('\n');
    const sections: ReportSection[] = [];
    let preamble: string[] = [];
    let current: ReportSection | null = null;

    const flush = () => {
        if (current) {
            current.body = current.body.replace(/\n+$/, '').trim();
            sections.push(current);
            current = null;
        }
    };

    for (const raw of lines) {
        const heading = /^(#{1,6})\s+(.*)$/.exec(raw.trim());
        if (heading) {
            flush();
            const level = heading[1].length;
            const title = heading[2].replace(/^\*\*|\*\*$/g, '').trim();
            current = {
                heading: title,
                level,
                body: '',
                kind: level === 1 ? 'title' : classifyHeading(title),
            };
            continue;
        }
        if (!current) {
            preamble.push(raw);
        } else {
            current.body += `${raw}\n`;
        }
    }
    flush();

    // Promote a lone H1 as title; if first section looks like title with empty body, keep it.
    if (sections.length && sections[0].kind === 'generic' && sections[0].level <= 2 && !sections[0].body.trim()) {
        sections[0].kind = 'title';
    }

    // Drop empty headings (e.g. "### Top Performers Analysis" with content under the next ###).
    // Keep title-only H1s — those are intentional page titles.
    const pruned = sections.filter((s) => s.kind === 'title' || Boolean(s.body.trim()));

    return { preamble: preamble.join('\n').trim(), sections: pruned };
}

function isEmptySection(section: ReportSection): boolean {
    return section.kind !== 'title' && !section.body.trim();
}

function parseOrderedItems(body: string): Array<{ title: string; detail: string }> {
    const items: Array<{ title: string; detail: string }> = [];
    const lines = body.split('\n');
    let current: { title: string; detail: string } | null = null;

    const flushItem = () => {
        if (current) {
            current.detail = current.detail.trim();
            items.push(current);
            current = null;
        }
    };

    for (const raw of lines) {
        const trimmed = raw.trim();
        if (!trimmed) continue;
        const ordered = /^\d+\.\s+(.*)$/.exec(trimmed);
        if (ordered) {
            flushItem();
            const content = ordered[1].trim();
            // "**Hook:** rest" or "Hook: rest" or "Hook — rest"
            const split = /^\*\*([^*]+)\*\*\s*[:—-]\s*(.*)$/.exec(content)
                || /^([^:.—-]{1,40})\s*[:—-]\s+(.*)$/.exec(content);
            if (split) {
                current = { title: split[1].replace(/\*\*/g, '').trim(), detail: split[2].trim() };
            } else {
                current = { title: content.replace(/\*\*/g, '').trim(), detail: '' };
            }
            continue;
        }
        const bullet = /^[-*•]\s+(.*)$/.exec(trimmed);
        if (bullet && current) {
            current.detail = current.detail
                ? `${current.detail}\n${bullet[1].trim()}`
                : bullet[1].trim();
            continue;
        }
        if (current) {
            current.detail = current.detail ? `${current.detail}\n${trimmed}` : trimmed;
        }
    }
    flushItem();
    return items;
}

function parseBullets(body: string): string[] {
    const bullets: string[] = [];
    for (const raw of body.split('\n')) {
        const m = /^[-*•]\s+(.*)$/.exec(raw.trim()) || /^\d+\.\s+(.*)$/.exec(raw.trim());
        if (m) bullets.push(m[1].trim());
    }
    return bullets;
}

function stripInlineMd(text: string): string {
    return text.replace(/\*\*([^*]+)\*\*/g, '$1').trim();
}

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

type TitleIconKind =
    | 'hook'
    | 'topic'
    | 'timing'
    | 'format'
    | 'quality'
    | 'interaction'
    | 'overview'
    | 'metrics'
    | 'topMetrics'
    | 'bottomMetrics'
    | 'driving'
    | 'holding'
    | 'recommend'
    | 'doMore'
    | 'doLess'
    | 'generic';

function resolveTitleIcon(title: string, kind?: SectionKind | 'preamble'): TitleIconKind {
    const t = title.toLowerCase();
    if (/\b(hook|caption|cta|call to action)\b/.test(t)) return 'hook';
    if (/\b(topic|theme|trend|subject)\b/.test(t)) return 'topic';
    if (/\b(timing|frequency|schedule|published|day)\b/.test(t)) return 'timing';
    if (/\b(format|media|video|image|reel)\b/.test(t)) return 'format';
    if (/\b(quality|vague|content quality)\b/.test(t)) return 'quality';
    if (/\bholding\b/.test(t) || (kind === 'bottom' && /\bfactor/.test(t))) return 'holding';
    if (/\bdriving\b/.test(t) || (kind === 'top' && /\bfactor|engagement/.test(t))) return 'driving';
    if (/\bbottom metrics\b/.test(t) || (/\bbottom\b/.test(t) && /\bmetric/.test(t))) return 'bottomMetrics';
    if (/\btop metrics\b/.test(t) || (/\btop\b/.test(t) && /\bmetric/.test(t))) return 'topMetrics';
    if (/\bbottom performer/.test(t)) return 'bottomMetrics';
    if (/\btop performer/.test(t)) return 'topMetrics';
    if (/\bdo more\b/.test(t) || kind === 'doMore') return 'doMore';
    if (/\bdo less\b/.test(t) || kind === 'doLess') return 'doLess';
    if (/\b(recommend|next|priority|action|increase|enhance)\b/.test(t) || kind === 'priority') return 'recommend';
    if (/\b(interaction|engage|audience|connect)\b/.test(t)) return 'interaction';
    if (/\b(overview|follower|summary|baseline)\b/.test(t) || kind === 'stats' || kind === 'preamble') return 'overview';
    if (/\b(metric|views|likes)\b/.test(t)) return 'metrics';
    return 'generic';
}

function TitleIcon({ kind, size = 14 }: { kind: TitleIconKind; size?: number }) {
    const props = {
        width: size,
        height: size,
        viewBox: '0 0 24 24',
        fill: 'none' as const,
        stroke: 'currentColor',
        strokeWidth: 2,
        strokeLinecap: 'round' as const,
        strokeLinejoin: 'round' as const,
        'aria-hidden': true as const,
    };
    switch (kind) {
        case 'hook':
            return (
                <svg {...props}>
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
            );
        case 'topic':
            return (
                <svg {...props}>
                    <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
                    <line x1="7" y1="7" x2="7.01" y2="7" />
                </svg>
            );
        case 'timing':
            return (
                <svg {...props}>
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                </svg>
            );
        case 'format':
            return (
                <svg {...props}>
                    <rect x="2" y="4" width="20" height="16" rx="2" />
                    <polygon points="10 9 16 12 10 15 10 9" fill="currentColor" stroke="none" />
                </svg>
            );
        case 'quality':
            return (
                <svg {...props}>
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                </svg>
            );
        case 'interaction':
            return (
                <svg {...props}>
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                    <circle cx="9" cy="7" r="4" />
                    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
            );
        case 'overview':
            return (
                <svg {...props}>
                    <path d="M3 3v18h18" />
                    <path d="M7 14l4-4 4 4 5-6" />
                </svg>
            );
        case 'metrics':
            return (
                <svg {...props}>
                    <line x1="18" y1="20" x2="18" y2="10" />
                    <line x1="12" y1="20" x2="12" y2="4" />
                    <line x1="6" y1="20" x2="6" y2="14" />
                </svg>
            );
        case 'topMetrics':
            return (
                <svg {...props}>
                    <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
                    <polyline points="17 6 23 6 23 12" />
                </svg>
            );
        case 'bottomMetrics':
            return (
                <svg {...props}>
                    <polyline points="23 18 13.5 8.5 8.5 13.5 1 6" />
                    <polyline points="17 18 23 18 23 12" />
                </svg>
            );
        case 'driving':
            return (
                <svg {...props}>
                    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                </svg>
            );
        case 'holding':
            return (
                <svg {...props}>
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                    <line x1="12" y1="9" x2="12" y2="13" />
                    <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
            );
        case 'recommend':
            return (
                <svg {...props}>
                    <path d="M9 18h6" />
                    <path d="M10 22h4" />
                    <path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z" />
                </svg>
            );
        case 'doMore':
            return (
                <svg {...props}>
                    <circle cx="12" cy="12" r="9" />
                    <line x1="12" y1="8" x2="12" y2="16" />
                    <line x1="8" y1="12" x2="16" y2="12" />
                </svg>
            );
        case 'doLess':
            return (
                <svg {...props}>
                    <circle cx="12" cy="12" r="9" />
                    <line x1="8" y1="12" x2="16" y2="12" />
                </svg>
            );
        default:
            return (
                <svg {...props}>
                    <circle cx="12" cy="12" r="9" />
                    <path d="M12 8v4l2.5 1.5" />
                </svg>
            );
    }
}

const METRIC_FIELD_RE = /^(engagement(?:\s*rate)?|views?|likes?|comments?|shares?|saves?|followers?)$/i;
/** Short attributes shown as pills in the collapsed row. */
const META_FIELD_RE = /^(format|timing|topic|theme|media|type|length|duration)$/i;
/** Longer copy kept behind expand. */
const BODY_FIELD_RE = /^(caption|hook|video hook|why|insight|note|analysis|reason)$/i;

function shortMetricLabel(label: string): string {
    const l = label.toLowerCase();
    if (/engagement/.test(l)) return 'Eng';
    if (/views?/.test(l)) return 'Views';
    if (/likes?/.test(l)) return 'Likes';
    if (/comments?/.test(l)) return 'Comments';
    if (/shares?/.test(l)) return 'Shares';
    if (/saves?/.test(l)) return 'Saves';
    return label;
}

/** Split a performer detail blob into metrics / meta pills / body fields. */
function parseDetailFields(detail: string): {
    metrics: Array<{ label: string; value: string }>;
    meta: Array<{ label: string; value: string }>;
    body: Array<{ label: string; value: string }>;
    prose: string;
} {
    const metrics: Array<{ label: string; value: string }> = [];
    const meta: Array<{ label: string; value: string }> = [];
    const body: Array<{ label: string; value: string }> = [];
    const proseParts: string[] = [];

    const chunks = detail
        .split(/\n|(?=\*\*[^*]+\*\*\s*[:—-])|(?<=[.!?])\s+(?=[A-Z][a-z]+\s*[:—-])/)
        .flatMap((chunk) => chunk.split(/\s+[·•]\s+/))
        .map((c) => c.trim())
        .filter(Boolean);

    for (const chunk of chunks) {
        const m = /^(?:\*\*)?([^*:\n—-]{1,40})(?:\*\*)?\s*[:—-]\s*(.+)$/.exec(chunk);
        if (!m) {
            proseParts.push(chunk);
            continue;
        }
        const label = stripInlineMd(m[1]);
        const value = m[2].trim();
        if (!label || !value) {
            proseParts.push(chunk);
            continue;
        }
        if (METRIC_FIELD_RE.test(label)) {
            metrics.push({ label, value: stripInlineMd(value) });
        } else if (META_FIELD_RE.test(label)) {
            meta.push({ label, value: stripInlineMd(value) });
        } else if (BODY_FIELD_RE.test(label)) {
            body.push({ label, value });
        } else {
            // Unknown labeled fields: short → meta pill, long → body
            if (stripInlineMd(value).length <= 48) {
                meta.push({ label, value: stripInlineMd(value) });
            } else {
                body.push({ label, value });
            }
        }
    }

    return { metrics, meta, body, prose: proseParts.join(' ').trim() };
}

/**
 * Compact accordion for Top / Bottom performers.
 * Collapsed: rank + title + inline metrics + meta pills.
 * Expanded: caption / hook / longer analysis only.
 */
function PerformerStack({
    items,
    tone,
}: {
    items: Array<{ title: string; detail: string }>;
    tone: 'blue' | 'amber';
}) {
    const [openIndex, setOpenIndex] = useState<number | null>(0);
    const badgeBg = tone === 'blue' ? 'var(--blue)' : '#D97706';
    const cardBg = tone === 'blue' ? 'rgba(51,122,255,0.04)' : 'rgba(217,119,6,0.05)';
    const border = tone === 'blue' ? 'rgba(51,122,255,0.14)' : 'rgba(217,119,6,0.18)';
    const openBorder = tone === 'blue' ? 'rgba(51,122,255,0.28)' : 'rgba(217,119,6,0.32)';

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {items.map((item, i) => {
                const title = stripInlineMd(item.title);
                const { metrics, meta, body, prose } = parseDetailFields(item.detail || '');
                const open = openIndex === i;
                const hasDetails = body.length > 0 || Boolean(prose) || (!metrics.length && !meta.length && Boolean(item.detail));

                return (
                    <div
                        key={`${item.title}-${i}`}
                        style={{
                            background: open ? cardBg : '#FFFFFF',
                            border: `1px solid ${open ? openBorder : border}`,
                            borderRadius: 10,
                            minWidth: 0,
                            overflow: 'hidden',
                        }}
                    >
                        <button
                            type="button"
                            onClick={() => setOpenIndex(open ? null : i)}
                            aria-expanded={open}
                            style={{
                                width: '100%',
                                display: 'flex',
                                alignItems: 'flex-start',
                                gap: 10,
                                padding: '10px 12px',
                                border: 'none',
                                background: 'transparent',
                                cursor: hasDetails ? 'pointer' : 'default',
                                textAlign: 'left',
                                color: 'inherit',
                            }}
                        >
                            <div
                                aria-hidden
                                style={{
                                    width: 22,
                                    height: 22,
                                    borderRadius: 6,
                                    background: badgeBg,
                                    color: '#fff',
                                    fontSize: 11,
                                    fontWeight: 800,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    flexShrink: 0,
                                    marginTop: 1,
                                }}
                            >
                                {i + 1}
                            </div>

                            <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 5 }}>
                                <div
                                    style={{
                                        display: 'flex',
                                        alignItems: 'baseline',
                                        justifyContent: 'space-between',
                                        gap: 10,
                                        flexWrap: 'wrap',
                                    }}
                                >
                                    <span
                                        style={{
                                            fontSize: 13,
                                            fontWeight: 700,
                                            color: 'var(--text-1)',
                                            lineHeight: 1.3,
                                        }}
                                    >
                                        {title}
                                    </span>
                                    {metrics.length > 0 && (
                                        <span
                                            style={{
                                                fontSize: 11,
                                                fontWeight: 700,
                                                color: '#475569',
                                                whiteSpace: 'nowrap',
                                                letterSpacing: 0.1,
                                            }}
                                        >
                                            {metrics.map((m, mi) => (
                                                <React.Fragment key={m.label}>
                                                    {mi > 0 && (
                                                        <span style={{ color: '#CBD5E1', fontWeight: 500 }}> · </span>
                                                    )}
                                                    <span style={{ color: 'var(--text-1)' }}>{m.value}</span>
                                                    <span style={{ color: '#94A3B8', fontWeight: 600 }}> {shortMetricLabel(m.label)}</span>
                                                </React.Fragment>
                                            ))}
                                        </span>
                                    )}
                                </div>

                                {(meta.length > 0 || hasDetails) && (
                                    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 5 }}>
                                        {meta.map((m) => (
                                            <span
                                                key={`${i}-${m.label}`}
                                                style={{
                                                    fontSize: 10,
                                                    fontWeight: 600,
                                                    color: '#64748B',
                                                    background: 'rgba(148,163,184,0.12)',
                                                    borderRadius: 999,
                                                    padding: '2px 7px',
                                                    maxWidth: 220,
                                                    overflow: 'hidden',
                                                    textOverflow: 'ellipsis',
                                                    whiteSpace: 'nowrap',
                                                }}
                                                title={`${m.label}: ${m.value}`}
                                            >
                                                <span style={{ color: '#94A3B8' }}>{m.label}</span>
                                                {' '}
                                                {m.value}
                                            </span>
                                        ))}
                                        {hasDetails && (
                                            <span
                                                style={{
                                                    marginLeft: 'auto',
                                                    fontSize: 10,
                                                    fontWeight: 700,
                                                    color: open ? badgeBg : '#94A3B8',
                                                    display: 'inline-flex',
                                                    alignItems: 'center',
                                                    gap: 3,
                                                }}
                                            >
                                                {open ? 'Hide' : 'Details'}
                                                <svg
                                                    width="10"
                                                    height="10"
                                                    viewBox="0 0 24 24"
                                                    fill="none"
                                                    stroke="currentColor"
                                                    strokeWidth={2.5}
                                                    style={{
                                                        transform: open ? 'rotate(180deg)' : 'none',
                                                        transition: 'transform 0.15s ease',
                                                    }}
                                                    aria-hidden
                                                >
                                                    <polyline points="6 9 12 15 18 9" />
                                                </svg>
                                            </span>
                                        )}
                                    </div>
                                )}
                            </div>
                        </button>

                        {open && hasDetails && (
                            <div style={{ padding: '0 12px 12px 12px' }}>
                                <InsightList
                                    keyPrefix={`perf-${i}`}
                                    items={[
                                        ...body.map((f) => `**${f.label}:** ${f.value}`),
                                        ...(!body.length && !metrics.length && !meta.length && item.detail
                                            ? [item.detail]
                                            : []),
                                        ...(prose ? [prose] : []),
                                    ]}
                                />
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
}

function SectionShell({
    title,
    children,
    accent,
    omitTitle,
}: {
    title?: string;
    children: React.ReactNode;
    accent?: string;
    /** When true, hide the in-card title (side nav already shows it). */
    omitTitle?: boolean;
}) {
    const iconKind = title ? resolveTitleIcon(title) : 'generic';
    const color = accent || '#94A3B8';
    return (
        <section
            style={{
                background: '#FFFFFF',
                border: '1px solid #E8EEF4',
                borderRadius: 12,
                padding: '14px 14px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
                minHeight: 0,
            }}
        >
            {title && !omitTitle && (
                <div
                    style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color,
                        textTransform: 'uppercase',
                        letterSpacing: 0.45,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 7,
                    }}
                >
                    <span
                        aria-hidden
                        style={{
                            width: 20,
                            height: 20,
                            borderRadius: 6,
                            background: 'rgba(148,163,184,0.14)',
                            color,
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                        }}
                    >
                        <TitleIcon kind={iconKind} size={12} />
                    </span>
                    {title}
                </div>
            )}
            {children}
        </section>
    );
}

function renderSection(
    section: ReportSection,
    index: number,
    opts?: { omitTitle?: boolean },
): React.ReactNode {
    const key = `sec-${index}`;
    const omitTitle = opts?.omitTitle;

    if (section.kind === 'title') {
        return (
            <div key={key} style={{ marginBottom: 2 }}>
                <h2
                    style={{
                        margin: 0,
                        fontSize: 17,
                        fontWeight: 700,
                        color: '#334155',
                        letterSpacing: -0.2,
                        lineHeight: 1.3,
                    }}
                >
                    {section.heading}
                </h2>
                {section.body.trim() && (
                    <div style={{ marginTop: 8 }}>
                        <StrategyReportMarkdown source={section.body} dense />
                    </div>
                )}
            </div>
        );
    }

    if (section.kind === 'stats') {
        const bullets = parseBullets(section.body);
        if (bullets.length >= 1) {
            return (
                <SectionShell key={key} title={section.heading} omitTitle={omitTitle}>
                    <InsightList items={bullets} keyPrefix={`stats-${index}`} />
                </SectionShell>
            );
        }

        // Turn "Label: value" lines into the same insight rows (short or long).
        const labeled: string[] = [];
        const leftoverLines: string[] = [];
        for (const raw of section.body.split('\n')) {
            const line = raw.trim().replace(/^[-*•]\s+/, '');
            if (!line) continue;
            const m = /^(?:\*\*)?([^*:\n]+?)(?:\*\*)?:\s*(.+)$/.exec(line);
            if (m && m[1].trim().length <= 40) {
                labeled.push(`**${m[1].trim()}:** ${m[2].trim()}`);
            } else {
                leftoverLines.push(raw);
            }
        }
        if (labeled.length) {
            return (
                <SectionShell key={key} title={section.heading} omitTitle={omitTitle}>
                    <InsightList items={labeled} keyPrefix={`stats-l-${index}`} />
                    {leftoverLines.length > 0 && (
                        <StrategyReportMarkdown source={leftoverLines.join('\n')} dense />
                    )}
                </SectionShell>
            );
        }

        return (
            <SectionShell key={key} title={section.heading} omitTitle={omitTitle}>
                <StrategyReportMarkdown source={section.body} dense />
            </SectionShell>
        );
    }

    if (section.kind === 'top' || section.kind === 'bottom') {
        if (!section.body.trim()) return null;
        const factors = parseOrderedItems(section.body);
        const isPerformers = /\bperformer/.test(section.heading.toLowerCase());
        if (factors.length >= 1 && isPerformers) {
            return (
                <SectionShell key={key} title={section.heading} omitTitle={omitTitle}>
                    <PerformerStack items={factors} tone={section.kind === 'top' ? 'blue' : 'amber'} />
                </SectionShell>
            );
        }
        if (factors.length >= 1) {
            return (
                <SectionShell key={key} title={section.heading} omitTitle={omitTitle}>
                    <InsightList
                        keyPrefix={`fac-${index}`}
                        items={factors.map((f) => (
                            f.detail
                                ? `**${stripInlineMd(f.title)}:** ${f.detail}`
                                : f.title
                        ))}
                    />
                </SectionShell>
            );
        }
        const bullets = parseBullets(section.body);
        if (bullets.length) {
            return (
                <SectionShell key={key} title={section.heading} omitTitle={omitTitle}>
                    <InsightList items={bullets} keyPrefix={`fac-b-${index}`} />
                </SectionShell>
            );
        }
        return (
            <SectionShell key={key} title={section.heading} omitTitle={omitTitle}>
                <StrategyReportMarkdown source={section.body} dense />
            </SectionShell>
        );
    }

    if (section.kind === 'doMore' || section.kind === 'doLess') {
        const bullets = parseBullets(section.body);
        if (bullets.length) {
            return (
                <SectionShell
                    key={key}
                    title={section.heading}
                    accent={section.kind === 'doMore' ? '#1f7a3a' : '#a35a00'}
                    omitTitle={omitTitle}
                >
                    <InsightList items={bullets} keyPrefix={`do-${index}`} />
                </SectionShell>
            );
        }
        return (
            <SectionShell key={key} title={section.heading} omitTitle={omitTitle}>
                <StrategyReportMarkdown source={section.body} dense />
            </SectionShell>
        );
    }

    if (section.kind === 'priority') {
        const bullets = parseBullets(section.body);
        if (bullets.length) {
            return (
                <SectionShell key={key} title={section.heading} accent="#337AFF" omitTitle={omitTitle}>
                    <InsightList items={bullets} keyPrefix={`pri-${index}`} />
                </SectionShell>
            );
        }
        return (
            <SectionShell key={key} title={section.heading} accent="#337AFF" omitTitle={omitTitle}>
                <InsightList
                    items={[section.body.trim().replace(/^[-*•]\s+/, '')]}
                    keyPrefix={`pri-p-${index}`}
                />
            </SectionShell>
        );
    }

    // Generic: insight rows if mostly bullets, else markdown (lists still use InsightList)
    const bullets = parseBullets(section.body);
    const lineCount = section.body.split('\n').filter((l) => l.trim()).length;
    if (bullets.length >= 2 && bullets.length >= lineCount * 0.6) {
        return (
            <SectionShell key={key} title={section.heading} omitTitle={omitTitle}>
                <InsightList items={bullets} keyPrefix={`gen-${index}`} />
            </SectionShell>
        );
    }

    return (
        <SectionShell key={key} title={section.heading} omitTitle={omitTitle}>
            <StrategyReportMarkdown source={section.body || section.heading} dense />
        </SectionShell>
    );
}

interface Props {
    source: string;
    /** When true, prefer checklist styling for generic bullet sections (AI Learnings). */
    learnings?: boolean;
}

interface NavPanel {
    id: string;
    /** Short label for the side nav. */
    label: string;
    /** Full section heading for the content pane header. */
    fullLabel: string;
    kind: SectionKind | 'preamble';
    icon: TitleIconKind;
    content: React.ReactNode;
}

export default function StructuredStrategyReport({ source, learnings = false }: Props) {
    const { sections } = useMemo(() => parseSections(source), [source]);

    const panels = useMemo(() => {
        const list: NavPanel[] = [];

        for (let i = 0; i < sections.length; i++) {
            const sec = sections[i];
            if (isEmptySection(sec)) continue;

            // Drop Overview / stats summary panels from the side nav.
            if (sec.kind === 'stats' || shortNavLabel(sec.heading) === 'Overview') {
                continue;
            }

            if (sec.kind === 'title') {
                // Account handle is already in the sticky header — skip redundant H1.
                if (sec.body.trim()) {
                    list.push({
                        id: `title-body-${i}`,
                        label: 'Summary',
                        fullLabel: 'Summary',
                        kind: 'title',
                        icon: 'overview',
                        content: (
                            <SectionShell omitTitle>
                                <StrategyReportMarkdown source={sec.body} dense />
                            </SectionShell>
                        ),
                    });
                }
                continue;
            }

            const next = sections[i + 1];
            if (sec.kind === 'doMore' && next?.kind === 'doLess' && !isEmptySection(next)) {
                list.push({
                    id: `pair-${i}`,
                    label: 'Do more / less',
                    fullLabel: `${sec.heading} / ${next.heading}`,
                    kind: 'doMore',
                    icon: 'doMore',
                    content: (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                            {renderSection(sec, i, { omitTitle: true })}
                            {renderSection(next, i + 1, { omitTitle: true })}
                        </div>
                    ),
                });
                i += 1;
                continue;
            }

            if (learnings && sec.kind === 'generic') {
                const bullets = parseBullets(sec.body);
                if (bullets.length >= 2) {
                    const learnLabel = shortNavLabel(sec.heading);
                    list.push({
                        id: `learn-${i}`,
                        label: learnLabel,
                        fullLabel: sec.heading,
                        kind: 'generic',
                        icon: resolveTitleIcon(learnLabel, 'generic'),
                        content: (
                            <SectionShell omitTitle>
                                <InsightList items={bullets} keyPrefix={`learn-${i}`} />
                            </SectionShell>
                        ),
                    });
                    continue;
                }
            }

            const node = renderSection(sec, i, { omitTitle: true });
            if (!node) continue;
            const navLabel = shortNavLabel(sec.heading);
            list.push({
                id: `sec-${i}`,
                label: navLabel,
                fullLabel: sec.heading,
                kind: sec.kind,
                icon: resolveTitleIcon(navLabel, sec.kind),
                content: node,
            });
        }

        if (!list.length) {
            list.push({
                id: 'fallback',
                label: 'Report',
                fullLabel: 'Report',
                kind: 'generic',
                icon: 'generic',
                content: (
                    <SectionShell omitTitle>
                        <StrategyReportMarkdown source={source} dense />
                    </SectionShell>
                ),
            });
        }

        return list;
    }, [sections, learnings, source]);

    const [activeId, setActiveId] = useState(panels[0]?.id ?? 'fallback');

    useEffect(() => {
        if (!panels.some((p) => p.id === activeId)) {
            setActiveId(panels[0]?.id ?? 'fallback');
        }
    }, [panels, activeId]);

    const active = panels.find((p) => p.id === activeId) || panels[0];

    return (
        <div className="strategy-dash">
            <div className="strategy-dash-body">
                <nav className="strategy-dash-nav" aria-label="Report sections">
                    {panels.map((panel) => {
                        const activePanel = panel.id === active?.id;
                        return (
                            <button
                                key={panel.id}
                                type="button"
                                onClick={() => setActiveId(panel.id)}
                                className="strategy-dash-nav-item"
                                title={panel.fullLabel}
                                style={{
                                    background: activePanel ? 'rgba(51,122,255,0.10)' : 'transparent',
                                    color: activePanel ? '#337AFF' : '#64748B',
                                    borderColor: activePanel ? 'rgba(51,122,255,0.22)' : 'transparent',
                                    fontWeight: activePanel ? 700 : 600,
                                }}
                            >
                                <span
                                    aria-hidden
                                    className="strategy-dash-nav-icon"
                                    style={{
                                        width: 26,
                                        height: 26,
                                        borderRadius: 8,
                                        background: activePanel ? '#337AFF' : 'rgba(148,163,184,0.14)',
                                        color: activePanel ? '#FFFFFF' : '#64748B',
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        flexShrink: 0,
                                    }}
                                >
                                    <TitleIcon kind={panel.icon} size={13} />
                                </span>
                                <span
                                    style={{
                                        textAlign: 'left',
                                        whiteSpace: 'normal',
                                        lineHeight: 1.25,
                                    }}
                                >
                                    {panel.label}
                                </span>
                            </button>
                        );
                    })}
                </nav>

                <div className="strategy-dash-pane" key={active?.id}>
                    {active?.label && (
                        <div
                            style={{
                                fontSize: 11,
                                fontWeight: 700,
                                color: '#64748B',
                                textTransform: 'uppercase',
                                letterSpacing: 0.4,
                                marginBottom: 8,
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 6,
                            }}
                        >
                            <TitleIcon kind={active.icon} size={12} />
                            {active.label}
                        </div>
                    )}
                    {active?.content}
                </div>
            </div>

            <style>{`
                .strategy-dash {
                    display: flex;
                    flex-direction: column;
                    min-height: 0;
                }
                .strategy-dash-body {
                    display: grid;
                    grid-template-columns: minmax(160px, 200px) minmax(0, 1fr);
                    gap: 10px;
                    align-items: start;
                    min-height: min(70vh, 640px);
                }
                .strategy-dash-nav {
                    display: flex;
                    flex-direction: column;
                    gap: 3px;
                    padding: 5px;
                    background: #F8FAFC;
                    border: 1px solid #E8EEF4;
                    border-radius: 12px;
                    position: sticky;
                    top: 72px;
                    max-height: min(70vh, 640px);
                    overflow: auto;
                }
                .strategy-dash-nav-item {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    width: 100%;
                    padding: 8px 10px;
                    border-radius: 8px;
                    border: 1px solid transparent;
                    background: transparent;
                    cursor: pointer;
                    font-size: 12px;
                    line-height: 1.3;
                    transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
                }
                .strategy-dash-nav-item:hover {
                    background: rgba(148,163,184,0.12);
                    color: #475569;
                }
                .strategy-dash-pane {
                    min-width: 0;
                    min-height: min(70vh, 640px);
                    max-height: min(70vh, 640px);
                    overflow: auto;
                    padding-right: 2px;
                }
                @media (max-width: 800px) {
                    .strategy-dash-body {
                        grid-template-columns: 1fr;
                        min-height: 0;
                    }
                    .strategy-dash-nav {
                        position: static;
                        flex-direction: row;
                        flex-wrap: nowrap;
                        overflow-x: auto;
                        max-height: none;
                        gap: 6px;
                        padding: 6px;
                    }
                    .strategy-dash-nav-item {
                        width: auto;
                        flex-shrink: 0;
                        max-width: none;
                    }
                    .strategy-dash-nav-item span:last-child {
                        white-space: nowrap;
                    }
                    .strategy-dash-pane {
                        min-height: 0;
                        max-height: none;
                    }
                }
            `}</style>
        </div>
    );
}
