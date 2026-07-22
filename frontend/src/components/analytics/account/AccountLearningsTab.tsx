'use client';

import { useMemo } from 'react';
import { useTranslation } from '@/lib/i18n';
import StructuredStrategyReport from '../StructuredStrategyReport';
import StrategyReportMarkdown from '../StrategyReportMarkdown';
import { timeAgo } from '../analytics-types';
import { parseLearnings } from './parseAccountReport';
import { Section, EmptyNote, LightbulbIcon, renderInlineBold } from './AccountUiKit';

interface Props {
    guidelines: string | null;
    updatedAt: string | null;
    loading: boolean;
}

function RuleCard({ text, kind, index }: { text: string; kind: 'confirmed' | 'hypothesis'; index: number }) {
    const confirmed = kind === 'confirmed';
    return (
        <div
            style={{
                display: 'flex', gap: 10, alignItems: 'flex-start',
                background: 'white',
                border: `1px solid ${confirmed ? 'rgba(52,199,89,0.30)' : 'rgba(255,159,10,0.30)'}`,
                borderRadius: 12,
                padding: '12px 14px',
            }}
        >
            <span
                aria-hidden
                style={{
                    flexShrink: 0,
                    width: 22, height: 22, borderRadius: '50%',
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    background: confirmed ? 'rgba(52,199,89,0.14)' : 'rgba(255,159,10,0.16)',
                    marginTop: 1,
                }}
            >
                {confirmed ? (
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#1f7a3a" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                    </svg>
                ) : (
                    <LightbulbIcon size={13} color="#a35a00" />
                )}
            </span>
            <span style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--text-2)', minWidth: 0 }}>
                {renderInlineBold(text, `${kind}-${index}`)}
            </span>
        </div>
    );
}

export default function AccountLearningsTab({ guidelines, updatedAt, loading }: Props) {
    const { t } = useTranslation();
    const parsed = useMemo(() => (guidelines ? parseLearnings(guidelines) : null), [guidelines]);

    if (!guidelines) {
        return <EmptyNote>{loading ? t('analytics.accounts.guidelines.loading') : t('analytics.accounts.guidelines.empty')}</EmptyNote>;
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Global framing — these learnings span all of the user's content. */}
            <div
                style={{
                    display: 'flex', gap: 12, alignItems: 'flex-start',
                    background: 'linear-gradient(180deg, rgba(51,122,255,0.07), rgba(51,122,255,0.02))',
                    border: '1px solid rgba(51,122,255,0.18)',
                    borderRadius: 14,
                    padding: '14px 16px',
                }}
            >
                <span aria-hidden style={{ fontSize: 20, lineHeight: 1 }}>🧠</span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-1)' }}>
                        {t('analytics.accounts.learnings.globalNote')}
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.5 }}>
                        {t('analytics.accounts.learnings.loopNote')}
                        {` · ${t('analytics.accounts.aiWindowNote')}`}
                        {updatedAt ? ` · ${t('analytics.accounts.guidelines.updated').replace('{when}', timeAgo(updatedAt))}` : ''}
                    </span>
                </div>
            </div>

            {parsed?.recognized ? (
                <>
                    {parsed.summary && (
                        <Section title={t('analytics.accounts.learnings.summary')}>
                            <StrategyReportMarkdown source={parsed.summary} dense />
                        </Section>
                    )}

                    {parsed.confirmed.length > 0 && (
                        <Section
                            title={t('analytics.accounts.learnings.confirmedRules')}
                            subtitle={t('analytics.accounts.learnings.confirmedSubtitle')}
                        >
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                {parsed.confirmed.map((rule, i) => (
                                    <RuleCard key={i} text={rule} kind="confirmed" index={i} />
                                ))}
                            </div>
                        </Section>
                    )}

                    {parsed.hypotheses.length > 0 && (
                        <Section
                            title={t('analytics.accounts.learnings.hypotheses')}
                            subtitle={t('analytics.accounts.learnings.hypothesesSubtitle')}
                        >
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                {parsed.hypotheses.map((h, i) => (
                                    <RuleCard key={i} text={h} kind="hypothesis" index={i} />
                                ))}
                            </div>
                        </Section>
                    )}
                </>
            ) : (
                // Unexpected guidelines shape → generic renderer, never blank.
                <StructuredStrategyReport source={guidelines} learnings />
            )}
        </div>
    );
}
