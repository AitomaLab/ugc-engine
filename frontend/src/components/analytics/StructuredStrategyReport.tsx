'use client';

import React, { useEffect, useMemo, useState } from 'react';
import StrategyReportMarkdown from './StrategyReportMarkdown';

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
    if (/\bkey factor/.test(h) && /\b(holding|back|under)\b/.test(h)) return 'Holding back';
    if (/\bkey factor/.test(h) && /\b(driving|why|worked|engagement)\b/.test(h)) return 'Driving engagement';
    if (/\bkey factor/.test(h)) return 'Key factors';
    if (/\btop performer/.test(h) && /\b(data|metric)\b/.test(h)) return 'Top metrics';
    if (/\bbottom performer/.test(h) && /\b(data|metric)\b/.test(h)) return 'Bottom metrics';
    if (/\btop performer/.test(h) || /\bwhy they worked\b/.test(h)) return 'Top performers';
    if (/\bbottom performer/.test(h) || /\bwent wrong\b/.test(h)) return 'Bottom performers';
    if (/\brecommend/.test(h) || /\bwhat to do next\b/.test(h) || /\bpriority\b/.test(h)) return 'Recommendations';
    if (/\bdo more\b/.test(h)) return 'Do more';
    if (/\bdo less\b/.test(h)) return 'Do less';
    if (/\bmetric/.test(h) && /\btop\b/.test(h)) return 'Top metrics';
    if (/\bmetric/.test(h) && /\bbottom\b/.test(h)) return 'Bottom metrics';
    // Fallback: trim filler words and cap length
    const cleaned = heading
        .replace(/\b(analysis|report|section|the|for|and)\b/gi, ' ')
        .replace(/\s+/g, ' ')
        .trim();
    if (cleaned.length <= 22) return cleaned || heading;
    return `${cleaned.slice(0, 20).trimEnd()}…`;
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

function extractStatChips(body: string): Array<{ label: string; value: string }> {
    const chips: Array<{ label: string; value: string }> = [];
    for (const raw of body.split('\n')) {
        // Support "- **Followers:** 1,452" as well as plain "Followers: 1,452"
        const line = raw.trim().replace(/^[-*•]\s+/, '');
        const m = /^(?:\*\*)?([^*:\n]+?)(?:\*\*)?:\s*(.+)$/.exec(line);
        if (!m) continue;
        const label = m[1].trim();
        const value = m[2].replace(/\*\*/g, '').trim();
        if (!label || !value || value.length > 80) continue;
        // Skip long prose "labels"
        if (label.length > 40) continue;
        chips.push({ label, value });
    }
    return chips;
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
                ? `${current.detail} ${bullet[1].trim()}`
                : bullet[1].trim();
            continue;
        }
        if (current) {
            current.detail = current.detail ? `${current.detail} ${trimmed}` : trimmed;
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

function FactorGrid({
    items,
    tone,
}: {
    items: Array<{ title: string; detail: string }>;
    tone: 'blue' | 'amber';
}) {
    const badgeBg = tone === 'blue' ? 'var(--blue)' : '#D97706';
    const cardBg = tone === 'blue' ? 'rgba(51,122,255,0.06)' : 'rgba(217,119,6,0.07)';
    const border = tone === 'blue' ? 'rgba(51,122,255,0.14)' : 'rgba(217,119,6,0.18)';

    return (
        <div
            style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                gap: 10,
            }}
        >
            {items.map((item, i) => {
                const title = stripInlineMd(item.title);
                const iconKind = resolveTitleIcon(title);
                return (
                    <div
                        key={`${item.title}-${i}`}
                        style={{
                            display: 'flex',
                            gap: 10,
                            padding: '12px 12px',
                            background: cardBg,
                            border: `1px solid ${border}`,
                            borderRadius: 10,
                            minWidth: 0,
                        }}
                    >
                        <div
                            aria-hidden
                            title={`${i + 1}`}
                            style={{
                                width: 28,
                                height: 28,
                                borderRadius: 8,
                                background: badgeBg,
                                color: '#fff',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                flexShrink: 0,
                            }}
                        >
                            <TitleIcon kind={iconKind} size={14} />
                        </div>
                        <div style={{ minWidth: 0 }}>
                            <div
                                style={{
                                    fontSize: 12,
                                    fontWeight: 700,
                                    color: 'var(--text-1)',
                                    marginBottom: item.detail ? 4 : 0,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 6,
                                }}
                            >
                                {title}
                            </div>
                            {item.detail && (
                                <div style={{ fontSize: 12, lineHeight: 1.5, color: 'var(--text-2)' }}>
                                    {renderInline(item.detail, `f-${i}`)}
                                </div>
                            )}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

function BulletCards({
    items,
    tone,
}: {
    items: string[];
    tone: 'green' | 'amber';
}) {
    const bg = tone === 'green' ? 'rgba(52,199,89,0.07)' : 'rgba(255,159,10,0.08)';
    const border = tone === 'green' ? 'rgba(52,199,89,0.2)' : 'rgba(255,159,10,0.22)';
    const mark = tone === 'green' ? '#1f7a3a' : '#a35a00';

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {items.map((item, i) => {
                const plain = stripInlineMd(item);
                const split = /^([^:.—-]{2,48})\s*[:—-]\s*(.*)$/.exec(plain);
                const label = split?.[1]?.trim();
                const rest = split?.[2]?.trim();
                const iconKind = resolveTitleIcon(label || plain);
                return (
                    <div
                        key={i}
                        style={{
                            display: 'flex',
                            gap: 10,
                            padding: '10px 12px',
                            background: bg,
                            border: `1px solid ${border}`,
                            borderRadius: 10,
                        }}
                    >
                        <span
                            aria-hidden
                            style={{
                                width: 26,
                                height: 26,
                                borderRadius: 7,
                                background: mark,
                                color: '#fff',
                                display: 'inline-flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                flexShrink: 0,
                            }}
                        >
                            <TitleIcon kind={iconKind} size={13} />
                        </span>
                        <div style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--text-2)', minWidth: 0 }}>
                            {label && rest ? (
                                <>
                                    <strong style={{ color: 'var(--text-1)', fontWeight: 700 }}>{label}:</strong>{' '}
                                    {rest}
                                </>
                            ) : (
                                renderInline(item, `b-${i}`)
                            )}
                        </div>
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

function Checklist({ items }: { items: string[] }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {items.map((item, i) => (
                <div
                    key={i}
                    style={{
                        display: 'flex',
                        gap: 10,
                        padding: '8px 10px',
                        borderRadius: 8,
                        background: 'rgba(148,163,184,0.08)',
                    }}
                >
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
                    <div style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--text-2)' }}>
                        {renderInline(item, `c-${i}`)}
                    </div>
                </div>
            ))}
        </div>
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
        const chips = extractStatChips(section.body);
        const leftover = section.body
            .split('\n')
            .filter((line) => {
                const t = line.trim().replace(/^[-*•]\s+/, '');
                if (!t) return false;
                return !/^(?:\*\*)?[^*:\n]+?(?:\*\*)?:\s*.+$/.test(t);
            })
            .join('\n')
            .trim();

        return (
            <SectionShell key={key} title={section.heading} omitTitle={omitTitle}>
                {chips.length > 0 && (
                    <div
                        style={{
                            display: 'flex',
                            flexWrap: 'wrap',
                            gap: 8,
                        }}
                    >
                        {chips.map((chip) => (
                            <div
                                key={chip.label}
                                style={{
                                    padding: '8px 12px',
                                    borderRadius: 8,
                                    background: 'rgba(148,163,184,0.08)',
                                    border: '1px solid #E8EEF4',
                                    minWidth: 100,
                                }}
                            >
                                <div style={{ fontSize: 14, fontWeight: 700, color: '#475569' }}>{chip.value}</div>
                                <div style={{ fontSize: 10, fontWeight: 600, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: 0.3, marginTop: 2 }}>
                                    {chip.label}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
                {leftover && <StrategyReportMarkdown source={leftover} dense />}
                {!chips.length && !leftover && <StrategyReportMarkdown source={section.body} dense />}
            </SectionShell>
        );
    }

    if (section.kind === 'top' || section.kind === 'bottom') {
        if (!section.body.trim()) return null;
        const factors = parseOrderedItems(section.body);
        if (factors.length >= 2) {
            return (
                <SectionShell key={key} title={section.heading} omitTitle={omitTitle}>
                    <FactorGrid items={factors} tone={section.kind === 'top' ? 'blue' : 'amber'} />
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
                    <BulletCards items={bullets} tone={section.kind === 'doMore' ? 'green' : 'amber'} />
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
        const prose = bullets.length
            ? null
            : section.body.trim().replace(/^[-*•]\s+/, '');
        return (
            <SectionShell key={key} title={section.heading} accent="#337AFF" omitTitle={omitTitle}>
                <div
                    style={{
                        padding: '12px 14px',
                        borderRadius: 10,
                        background: 'rgba(51,122,255,0.07)',
                        border: '1px solid rgba(51,122,255,0.18)',
                        fontSize: 13,
                        lineHeight: 1.55,
                        color: 'var(--text-1)',
                        fontWeight: 600,
                    }}
                >
                    {bullets.length
                        ? (
                            <ol style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 6 }}>
                                {bullets.map((b, i) => (
                                    <li key={i} style={{ fontWeight: 500, color: 'var(--text-2)' }}>
                                        {renderInline(b, `p-${i}`)}
                                    </li>
                                ))}
                            </ol>
                        )
                        : renderInline(prose || section.body, 'priority')}
                </div>
            </SectionShell>
        );
    }

    // Generic: checklist if mostly bullets, else markdown
    const bullets = parseBullets(section.body);
    const lineCount = section.body.split('\n').filter((l) => l.trim()).length;
    if (bullets.length >= 2 && bullets.length >= lineCount * 0.6) {
        return (
            <SectionShell key={key} title={section.heading} omitTitle={omitTitle}>
                <Checklist items={bullets} />
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
    const { preamble, sections } = useMemo(() => parseSections(source), [source]);

    const panels = useMemo(() => {
        const list: NavPanel[] = [];

        if (preamble) {
            const chips = extractStatChips(preamble);
            list.push({
                id: 'preamble',
                label: 'Overview',
                fullLabel: 'Overview',
                kind: 'preamble',
                icon: 'overview',
                content: chips.length ? (
                    <SectionShell omitTitle>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                            {chips.map((chip) => (
                                <div
                                    key={chip.label}
                                    style={{
                                        padding: '8px 12px',
                                        borderRadius: 8,
                                        background: 'rgba(148,163,184,0.08)',
                                        border: '1px solid #E8EEF4',
                                        minWidth: 100,
                                    }}
                                >
                                    <div style={{ fontSize: 14, fontWeight: 700, color: '#475569' }}>{chip.value}</div>
                                    <div style={{ fontSize: 10, fontWeight: 600, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: 0.3, marginTop: 2 }}>
                                        {chip.label}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </SectionShell>
                ) : (
                    <SectionShell omitTitle>
                        <StrategyReportMarkdown source={preamble} dense />
                    </SectionShell>
                ),
            });
        }

        for (let i = 0; i < sections.length; i++) {
            const sec = sections[i];
            if (isEmptySection(sec)) continue;

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
                        <div
                            style={{
                                display: 'grid',
                                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                                gap: 12,
                            }}
                        >
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
                                <Checklist items={bullets} />
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
    }, [preamble, sections, learnings, source]);

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
                    {active?.fullLabel && (
                        <div
                            style={{
                                fontSize: 12,
                                fontWeight: 700,
                                color: '#64748B',
                                textTransform: 'uppercase',
                                letterSpacing: 0.4,
                                marginBottom: 10,
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 7,
                            }}
                        >
                            <TitleIcon kind={active.icon} size={13} />
                            {active.fullLabel}
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
                    grid-template-columns: minmax(180px, 220px) minmax(0, 1fr);
                    gap: 12px;
                    align-items: start;
                    min-height: min(62vh, 560px);
                }
                .strategy-dash-nav {
                    display: flex;
                    flex-direction: column;
                    gap: 4px;
                    padding: 6px;
                    background: #F8FAFC;
                    border: 1px solid #E8EEF4;
                    border-radius: 12px;
                    position: sticky;
                    top: 72px;
                    max-height: min(62vh, 560px);
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
                    min-height: min(62vh, 560px);
                    max-height: min(62vh, 560px);
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
