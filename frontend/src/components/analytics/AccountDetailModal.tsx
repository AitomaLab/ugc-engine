'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import StructuredStrategyReport from './StructuredStrategyReport';
import {
    analyticsFetch,
    pollScrapeJob,
    timeAgo,
    useAccountStrategyReport,
    useCreativeGuidelines,
    type TrackedAccountAggregate,
    type TrackedAccountWithJob,
} from './analytics-types';

interface Props {
    account: TrackedAccountAggregate;
    onClose: () => void;
    /** Kept for call-site compatibility (By Video / post deep-links). */
    onOpenPost?: (postId: string) => void;
    /** Called after a fresh scrape/sync completes so parent KPIs update. */
    onRefreshed?: () => void;
    /**
     * Resolved profile photo URL — caller (AnalyticsTab) should pass a
     * Connections `profilePic` for Studio accounts and fall back to the
     * tracked-account `avatar_url` for External accounts. Undefined means
     * we render a coloured initial circle.
     */
    avatarUrl?: string;
}

/**
 * Full-page account detail — destination from the Accounts grid (`?account=`).
 *
 *   • Sticky Back bar + identity / refresh
 *   • Inner tabs: AI Strategy · AI Learnings
 */
type AccountDetailTab = 'strategy' | 'learnings';

const PLATFORM_ACCENT: Record<string, string> = {
    instagram: '#E1306C',
    tiktok:    '#000000',
    youtube:   '#FF0000',
    facebook:  '#1877F2',
};

/**
 * Compact avatar puck rendered above the summary metrics so external
 * accounts get the same visual identity treatment as Studio-connected
 * ones. Falls back to a platform-tinted initial circle when no photo
 * URL is available (e.g. a freshly-added @handle whose BrightData scrape
 * didn't surface `profile_pic_url`).
 */
function AvatarPuck({ url, platform, pulsing }: { url?: string; platform: string; pulsing?: boolean }) {
    const accent = PLATFORM_ACCENT[platform] || 'var(--text-3)';
    const [broken, setBroken] = useState(false);
    const ringStyle = pulsing
        ? { boxShadow: `0 0 0 3px ${accent}33`, animation: 'accountRefreshPulse 1.2s ease-in-out infinite' }
        : {};
    if (url && !broken) {
        return (
            // eslint-disable-next-line @next/next/no-img-element
            <img
                src={url}
                alt=""
                loading="lazy"
                referrerPolicy="no-referrer"
                onError={() => setBroken(true)}
                style={{
                    width: 56, height: 56, borderRadius: '50%',
                    objectFit: 'cover',
                    border: '2px solid var(--border)',
                    background: 'var(--blue-light)',
                    flexShrink: 0,
                    ...ringStyle,
                }}
            />
        );
    }
    return (
        <div
            aria-hidden
            style={{
                width: 56, height: 56, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: `${accent}18`,
                color: accent,
                fontSize: 22, fontWeight: 800,
                border: '2px solid var(--border)',
                flexShrink: 0,
                ...ringStyle,
            }}
        >
            {platform.slice(0, 1).toUpperCase()}
        </div>
    );
}

function RefreshSpinner() {
    return (
        <span
            aria-hidden
            style={{
                width: 14,
                height: 14,
                borderRadius: '50%',
                border: '2px solid rgba(51,122,255,0.25)',
                borderTopColor: 'var(--blue)',
                animation: 'accountRefreshSpin 0.8s linear infinite',
                flexShrink: 0,
            }}
        />
    );
}

/** Full-page account detail (filename kept for import stability). */
export default function AccountDetailView({ account, onClose, onRefreshed, avatarUrl }: Props) {
    const { t, lang } = useTranslation();
    const [refreshKey, setRefreshKey] = useState(0);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [lastScrapedAt, setLastScrapedAt] = useState<string | null>(account.last_scraped_at ?? null);
    const [justUpdated, setJustUpdated] = useState(false);
    const [tab, setTab] = useState<AccountDetailTab>('strategy');
    const justUpdatedTimer = useRef<number | null>(null);
    const refreshInFlight = useRef(false);

    const { data: strategy, loading: strategyLoading } = useAccountStrategyReport(account.id, refreshKey, lang);
    const { data: guidelines, loading: guidelinesLoading } = useCreativeGuidelines(refreshKey);

    useEffect(() => {
        setLastScrapedAt(account.last_scraped_at ?? null);
    }, [account.id, account.last_scraped_at]);

    useEffect(() => {
        setTab('strategy');
    }, [account.id]);

    const markJustUpdated = useCallback(() => {
        setJustUpdated(true);
        if (justUpdatedTimer.current) window.clearTimeout(justUpdatedTimer.current);
        justUpdatedTimer.current = window.setTimeout(() => setJustUpdated(false), 5000);
    }, []);

    const startBackgroundRefresh = useCallback(async () => {
        if (refreshInFlight.current) return;
        refreshInFlight.current = true;
        setIsRefreshing(true);
        try {
            const res = await analyticsFetch<TrackedAccountWithJob>(
                `/api/analytics/tracked-accounts/${account.id}/refresh`,
                { method: 'POST', skipProjectScope: true },
            );
            if (res.account?.last_scraped_at) {
                setLastScrapedAt(res.account.last_scraped_at);
            }
            if (res.job_id) {
                const polled = await pollScrapeJob(res.job_id);
                if (polled.status === 'completed') {
                    setRefreshKey((n) => n + 1);
                    markJustUpdated();
                    setLastScrapedAt(new Date().toISOString());
                    onRefreshed?.();
                } else if (polled.status === 'failed') {
                    console.warn('[AccountDetailModal] refresh failed:', polled.error_message);
                }
            }
        } catch (err) {
            console.warn('[AccountDetailModal] refresh error:', err);
        } finally {
            setIsRefreshing(false);
            refreshInFlight.current = false;
        }
    }, [account.id, markJustUpdated, onRefreshed]);

    /* Kick off a background refresh on open — cached posts render immediately. */
    useEffect(() => {
        startBackgroundRefresh();
        return () => {
            if (justUpdatedTimer.current) window.clearTimeout(justUpdatedTimer.current);
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh once per account open
    }, [account.id]);

    const resolvedAvatar = avatarUrl || account.avatar_url || undefined;

    const refreshStatusLabel = (() => {
        if (isRefreshing) return t('analytics.accounts.refreshingPostsStatus');
        if (justUpdated) return t('analytics.accounts.updatedJustNow');
        if (lastScrapedAt) {
            return `${t('analytics.accounts.lastUpdated')} ${timeAgo(lastScrapedAt)}`;
        }
        return t('analytics.accounts.neverScraped');
    })();

    return (
        <div className="analytics-account-detail">
            <style>{`
                @keyframes accountRefreshSpin {
                    to { transform: rotate(360deg); }
                }
                @keyframes accountRefreshPulse {
                    0%, 100% { box-shadow: 0 0 0 3px rgba(51,122,255,0.15); }
                    50% { box-shadow: 0 0 0 5px rgba(51,122,255,0.35); }
                }
            `}</style>

            <div
                style={{
                    position: 'sticky',
                    top: 0,
                    zIndex: 5,
                    background: 'rgba(255,255,255,0.96)',
                    backdropFilter: 'blur(8px)',
                    border: '1px solid var(--border)',
                    borderRadius: 12,
                    padding: '10px 12px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12,
                    flexWrap: 'wrap',
                    marginBottom: 14,
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0, flex: 1 }}>
                    <button
                        type="button"
                        onClick={onClose}
                        aria-label="Back"
                        style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                            padding: '7px 12px',
                            borderRadius: 8,
                            border: '1px solid var(--border)',
                            background: 'white',
                            color: 'var(--text-1)',
                            fontSize: 13,
                            fontWeight: 600,
                            cursor: 'pointer',
                            flexShrink: 0,
                        }}
                    >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} aria-hidden>
                            <path d="M15 18l-6-6 6-6" />
                        </svg>
                        Back
                    </button>
                    <AvatarPuck url={resolvedAvatar} platform={account.platform} pulsing={isRefreshing} />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                        <span style={{
                            fontSize: 16, fontWeight: 800, color: 'var(--text-1)',
                            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                        }}>
                            @{account.username}
                        </span>
                        <span style={{
                            fontSize: 11, fontWeight: 700,
                            color: PLATFORM_ACCENT[account.platform] || 'var(--text-3)',
                            textTransform: 'uppercase', letterSpacing: 0.4,
                        }}>
                            {account.platform}
                            {account.linked_via_connections && (
                                <span style={{
                                    marginLeft: 8,
                                    color: 'var(--blue)',
                                    background: 'rgba(51,122,255,0.12)',
                                    padding: '2px 8px', borderRadius: 999,
                                    fontSize: 10,
                                }}>
                                    {t('analytics.accounts.ownership.studioBadge')}
                                </span>
                            )}
                        </span>
                    </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    {isRefreshing && <RefreshSpinner />}
                    <span style={{ fontSize: 12, color: 'var(--text-3)', fontWeight: 500 }}>
                        {refreshStatusLabel}
                    </span>
                    <button
                        type="button"
                        onClick={() => startBackgroundRefresh()}
                        disabled={isRefreshing}
                        style={{
                            padding: '6px 12px',
                            borderRadius: 8,
                            border: '1px solid var(--border)',
                            background: isRefreshing ? 'var(--surface)' : 'white',
                            color: 'var(--text-2)',
                            fontSize: 12,
                            fontWeight: 600,
                            cursor: isRefreshing ? 'default' : 'pointer',
                            opacity: isRefreshing ? 0.6 : 1,
                        }}
                    >
                        {isRefreshing ? t('analytics.accounts.analyzing') : t('analytics.tracked.refresh')}
                    </button>
                </div>
            </div>

            <AccountDetailTabs tab={tab} onChange={setTab} />

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {tab === 'strategy' && (
                    <Section
                        title={t('analytics.accounts.strategy.title')}
                        action={
                            strategy?.generated_at ? (
                                <span style={{ fontSize: 11, color: 'var(--text-3)' }}>
                                    {t('analytics.accounts.strategy.updated').replace('{when}', timeAgo(strategy.generated_at))}
                                </span>
                            ) : null
                        }
                    >
                        {strategy?.report
                            ? <StructuredStrategyReport source={strategy.report} />
                            : (
                                <div
                                    style={{
                                        background: 'rgba(51,122,255,0.06)',
                                        border: '1px dashed #E2E8F0',
                                        borderRadius: 12,
                                        padding: '16px 18px',
                                        fontSize: 13,
                                        color: 'var(--text-2)',
                                        lineHeight: 1.5,
                                    }}
                                >
                                    {strategyLoading
                                        ? t('analytics.accounts.strategy.loading')
                                        : t('analytics.accounts.strategy.pending')}
                                </div>
                            )
                        }
                    </Section>
                )}

                {tab === 'learnings' && (
                    <Section
                        title={t('analytics.accounts.guidelines.title')}
                        action={
                            guidelines?.updated_at ? (
                                <span style={{ fontSize: 11, color: 'var(--text-3)' }}>
                                    {t('analytics.accounts.guidelines.updated').replace('{when}', timeAgo(guidelines.updated_at))}
                                </span>
                            ) : null
                        }
                    >
                        {guidelines?.guidelines
                            ? <StructuredStrategyReport source={guidelines.guidelines} learnings />
                            : (
                                <div
                                    style={{
                                        background: 'rgba(51,122,255,0.06)',
                                        border: '1px dashed #E2E8F0',
                                        borderRadius: 12,
                                        padding: '16px 18px',
                                        fontSize: 13,
                                        color: 'var(--text-2)',
                                        lineHeight: 1.5,
                                    }}
                                >
                                    {guidelinesLoading
                                        ? t('analytics.accounts.guidelines.loading')
                                        : t('analytics.accounts.guidelines.empty')}
                                </div>
                            )
                        }
                    </Section>
                )}
            </div>
        </div>
    );
}

function AccountDetailTabs({
    tab,
    onChange,
}: {
    tab: AccountDetailTab;
    onChange: (next: AccountDetailTab) => void;
}) {
    const { t } = useTranslation();
    const tabs: Array<{ id: AccountDetailTab; label: string }> = [
        { id: 'strategy', label: t('analytics.accounts.tabs.strategy') },
        { id: 'learnings', label: t('analytics.accounts.tabs.learnings') },
    ];

    return (
        <div
            role="tablist"
            aria-label="Account sections"
            style={{
                display: 'inline-flex',
                flexWrap: 'wrap',
                gap: 4,
                padding: 4,
                borderRadius: 12,
                background: '#F1F5F9',
                border: '1px solid #E2E8F0',
                alignSelf: 'flex-start',
                marginBottom: 14,
            }}
        >
            {tabs.map((item) => {
                const active = item.id === tab;
                return (
                    <button
                        key={item.id}
                        type="button"
                        role="tab"
                        aria-selected={active}
                        onClick={() => onChange(item.id)}
                        style={{
                            padding: '6px 12px',
                            borderRadius: 8,
                            border: 'none',
                            background: active ? '#337AFF' : 'transparent',
                            color: active ? '#FFFFFF' : '#475569',
                            fontSize: 12,
                            fontWeight: 700,
                            cursor: 'pointer',
                            transition: 'background 0.15s ease, color 0.15s ease',
                            boxShadow: active ? '0 1px 2px rgba(51,122,255,0.30)' : 'none',
                            whiteSpace: 'nowrap',
                        }}
                    >
                        {item.label}
                    </button>
                );
            })}
        </div>
    );
}

function Section({
    title, action, children,
}: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
    return (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <h3 style={{ margin: 0, fontSize: '12px', fontWeight: 700, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                    {title}
                </h3>
                {action}
            </div>
            {children}
        </section>
    );
}
