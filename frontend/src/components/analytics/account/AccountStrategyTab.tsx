'use client';

import { useMemo } from 'react';
import { useTranslation } from '@/lib/i18n';
import PostCard from '../PostCard';
import StrategyReportMarkdown from '../StrategyReportMarkdown';
import StructuredStrategyReport from '../StructuredStrategyReport';
import type { AnalyticsPost } from '../analytics-types';
import { parseStrategyReport } from './parseAccountReport';
import { Section, Panel, EmptyNote, renderInlineBold } from './AccountUiKit';

interface Props {
    report: string | null;
    loading: boolean;
    isRefreshing: boolean;
    posts: AnalyticsPost[];
    thumbMap: Record<string, string>;
    onOpenPost: (postId: string) => void;
}

const PEAK = 3;

/**
 * Ranked previews for a diagnosis section — a rank chip above each card
 * (instead of "Post 1 / Post 2" text rows) and the real clickable video;
 * clicking opens the post's full individual AI breakdown page.
 */
function LabeledPosts({
    posts,
    thumbMap,
    onOpenPost,
    kind,
}: {
    posts: AnalyticsPost[];
    thumbMap: Record<string, string>;
    onOpenPost: (postId: string) => void;
    kind: 'top' | 'bottom';
}) {
    const { t } = useTranslation();
    if (!posts.length) return null;
    const chipColors = kind === 'top'
        ? { color: '#1f7a3a', background: 'rgba(52,199,89,0.14)', border: 'rgba(52,199,89,0.35)' }
        : { color: '#a35a00', background: 'rgba(255,159,10,0.16)', border: 'rgba(255,159,10,0.35)' };
    return (
        <div className="strategy-posts">
            {posts.map((p, i) => (
                <div key={p.id} style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
                    <span
                        style={{
                            alignSelf: 'flex-start',
                            fontSize: 10.5,
                            fontWeight: 800,
                            letterSpacing: 0.3,
                            padding: '3px 9px',
                            borderRadius: 999,
                            color: chipColors.color,
                            background: chipColors.background,
                            border: `1px solid ${chipColors.border}`,
                            whiteSpace: 'nowrap',
                        }}
                    >
                        {t(kind === 'top'
                            ? 'analytics.accounts.strategy.badge.top'
                            : 'analytics.accounts.strategy.badge.bottom'
                        ).replace('{n}', String(i + 1))}
                    </span>
                    <PostCard post={p} thumbnailUrl={thumbMap[p.id]} onOpen={onOpenPost} />
                </div>
            ))}
        </div>
    );
}

export default function AccountStrategyTab({
    report,
    loading,
    isRefreshing,
    posts,
    thumbMap,
    onOpenPost,
}: Props) {
    const { t } = useTranslation();
    const parsed = useMemo(() => (report ? parseStrategyReport(report) : null), [report]);

    // Rank by total engagement (== ER ranking, since followers is constant per
    // account) so the top/bottom cards mirror the report's Top/Bottom framing.
    const { topPosts, bottomPosts } = useMemo(() => {
        const sorted = [...posts].sort((a, b) => (b.total_engagement || 0) - (a.total_engagement || 0));
        const top = sorted.slice(0, PEAK);
        const bottom = sorted.length > PEAK ? sorted.slice(Math.max(PEAK, sorted.length - PEAK)) : [];
        return { topPosts: top, bottomPosts: bottom };
    }, [posts]);

    if (!report) {
        return (
            <EmptyNote>
                {loading || isRefreshing
                    ? t('analytics.accounts.strategy.loading')
                    : t('analytics.accounts.strategy.pending')}
            </EmptyNote>
        );
    }

    if (!parsed?.recognized) {
        // A scrape + re-analysis is in flight: the fresh report lands within
        // seconds in the canonical shape. Rendering the raw fallback here
        // reads as "wrong data that rewrites itself", so hold the analyzing
        // state until the real report arrives.
        if (loading || isRefreshing) {
            return <EmptyNote>{t('analytics.accounts.strategy.loading')}</EmptyNote>;
        }
        // Genuinely unexpected shape → generic renderer, never blank.
        return <StructuredStrategyReport source={report} />;
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Top performers — insights left, ranked previews right */}
            {(topPosts.length > 0 || parsed.top) && (
                <Section
                    title={t('analytics.accounts.strategy.topPerformers')}
                    subtitle={t('analytics.accounts.strategy.topSubtitle')}
                >
                    <div className="strategy-split">
                        {parsed.top && (
                            <Panel style={{ borderColor: 'rgba(52,199,89,0.30)', background: 'rgba(52,199,89,0.04)', minWidth: 0 }}>
                                <div style={{ fontSize: 12, fontWeight: 700, color: '#1f7a3a', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 8 }}>
                                    {t('analytics.accounts.strategy.whyWork')}
                                </div>
                                <StrategyReportMarkdown source={parsed.top} dense />
                            </Panel>
                        )}
                        <LabeledPosts posts={topPosts} thumbMap={thumbMap} onOpenPost={onOpenPost} kind="top" />
                    </div>
                </Section>
            )}

            {/* Needs work — insights left, ranked previews right */}
            {(bottomPosts.length > 0 || parsed.bottom) && (
                <Section
                    title={t('analytics.accounts.strategy.bottomPerformers')}
                    subtitle={t('analytics.accounts.strategy.bottomSubtitle')}
                >
                    <div className="strategy-split">
                        {parsed.bottom && (
                            <Panel style={{ borderColor: 'rgba(255,159,10,0.30)', background: 'rgba(255,159,10,0.05)', minWidth: 0 }}>
                                <div style={{ fontSize: 12, fontWeight: 700, color: '#a35a00', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 8 }}>
                                    {t('analytics.accounts.strategy.whatHolds')}
                                </div>
                                <StrategyReportMarkdown source={parsed.bottom} dense />
                            </Panel>
                        )}
                        <LabeledPosts posts={bottomPosts} thumbMap={thumbMap} onOpenPost={onOpenPost} kind="bottom" />
                    </div>
                </Section>
            )}

            {/* Diagnosis — its own card, like Do next (not folded into a section) */}
            {parsed.diagnosis && (
                <Section title={t('analytics.accounts.strategy.diagnosis')}>
                    <Panel>
                        <StrategyReportMarkdown source={parsed.diagnosis} dense />
                    </Panel>
                </Section>
            )}

            {/* Do next — ranked action checklist */}
            {(parsed.actionItems.length > 0 || parsed.actionsBody) && (
                <Section title={t('analytics.accounts.strategy.doNext')}>
                    {parsed.actionItems.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                            {parsed.actionItems.map((item, i) => (
                                <div
                                    key={i}
                                    style={{
                                        display: 'flex', gap: 12, alignItems: 'flex-start',
                                        background: 'white',
                                        border: '1px solid var(--border)',
                                        borderRadius: 12,
                                        padding: '12px 14px',
                                    }}
                                >
                                    <span
                                        aria-hidden
                                        style={{
                                            flexShrink: 0,
                                            width: 22, height: 22, borderRadius: '50%',
                                            background: 'var(--blue)', color: 'white',
                                            fontSize: 12, fontWeight: 800,
                                            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                                            marginTop: 1,
                                        }}
                                    >
                                        {i + 1}
                                    </span>
                                    <span style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--text-2)', minWidth: 0 }}>
                                        {renderInlineBold(item, `act-${i}`)}
                                    </span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <Panel>
                            <StrategyReportMarkdown source={parsed.actionsBody as string} dense />
                        </Panel>
                    )}
                </Section>
            )}

            <style>{`
                .strategy-split {
                    display: grid;
                    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
                    gap: 14px;
                    align-items: start;
                }
                .strategy-posts {
                    display: grid;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    gap: 10px;
                    align-content: start;
                }
                @media (max-width: 1000px) {
                    .strategy-split {
                        grid-template-columns: 1fr;
                    }
                }
                @media (max-width: 560px) {
                    .strategy-posts {
                        grid-template-columns: repeat(2, minmax(0, 1fr));
                    }
                }
            `}</style>
        </div>
    );
}
