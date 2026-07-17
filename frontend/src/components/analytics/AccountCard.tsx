'use client';

import { useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import {
    ANALYTICS_CTA_ORANGE,
    ANALYTICS_CTA_ORANGE_HOVER,
    analyticsFetch,
    pollScrapeJob,
    formatCount,
    timeAgo,
    type TrackedAccountAggregate,
    type TrackedAccountWithJob,
} from './analytics-types';

const PLATFORM_COLORS: Record<string, string> = {
    instagram: '#E1306C',
    tiktok:    '#000000',
    youtube:   '#FF0000',
    facebook:  '#1877F2',
};

interface Props {
    account: TrackedAccountAggregate;
    onOpen: (accountId: string) => void;
    /** Refetch parent state after Analyze Now completes. */
    onScraped: () => void;
    /**
     * Optional remove handler. When provided, a subtle trash button
     * appears in the card header — the parent should optimistically
     * drop the row from its grid (the DELETE response 404s if we re-issue
     * the call, so we lean on the optimistic state instead of a refetch).
     */
    onDelete?: (accountId: string) => void;
    /**
     * When true the card shows a small "Studio" pill next to the platform tag
     * — driven by the parent's Studio/External classification (intersection
     * with `/api/connections`).
     */
    isStudio?: boolean;
    /** Resolved profile photo — tracked account avatar or Connections profilePic. */
    avatarUrl?: string;
    /**
     * Full-width horizontal layout used when the Accounts list has ≤2 rows.
     * With 3+ accounts the parent grid switches to compact cards and this
     * stays false.
     */
    wide?: boolean;
}

function AccountAvatar({ url, platform }: { url?: string; platform: string }) {
    const accent = PLATFORM_COLORS[platform] || 'var(--text-3)';
    const initial = platform.slice(0, 1).toUpperCase();
    const [broken, setBroken] = useState(false);

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
                    width: 48,
                    height: 48,
                    borderRadius: '50%',
                    objectFit: 'cover',
                    flexShrink: 0,
                    border: '2px solid var(--border)',
                    background: 'var(--blue-light)',
                }}
            />
        );
    }

    return (
        <div
            aria-hidden
            style={{
                width: 48,
                height: 48,
                borderRadius: '50%',
                flexShrink: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: `${accent}18`,
                color: accent,
                fontSize: '18px',
                fontWeight: 800,
                border: '2px solid var(--border)',
            }}
        >
            {initial}
        </div>
    );
}

export default function AccountCard({ account, onOpen, onScraped, onDelete, isStudio, avatarUrl, wide = false }: Props) {
    const { t } = useTranslation();
    const [scraping, setScraping] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [removeHover, setRemoveHover] = useState(false);
    const accent = PLATFORM_COLORS[account.platform] || 'var(--text-2)';
    const followers = account.follower_count ?? account.followers;
    // TikTok is the only major platform whose public scrape reliably surfaces
    // view counts; we render "—" elsewhere so we don't imply we have data we
    // don't. (IG hides views, YT exposes them per-video but not per-account
    // aggregate, FB doesn't expose them at all.)
    const showViews =
        account.platform === 'tiktok'
        || isStudio
        || (account.total_views ?? 0) > 0;

    const handleRemove = (e: React.MouseEvent | React.KeyboardEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (!onDelete) return;
        const ok = typeof window === 'undefined'
            ? true
            : window.confirm(
                t('analytics.accounts.removeConfirm').replace('{handle}', `@${account.username}`),
            );
        if (ok) onDelete(account.id);
    };

    const scrapeNow = async (e: React.MouseEvent) => {
        e.stopPropagation();
        if (scraping) return;
        setScraping(true);
        setError(null);
        try {
            const res = await analyticsFetch<TrackedAccountWithJob>(
                `/api/analytics/tracked-accounts/${account.id}/refresh`,
                { method: 'POST', skipProjectScope: true },
            );
            if (
                (res.status === 'pending' || res.status === 'running')
                && res.job_id
            ) {
                const polled = await pollScrapeJob(res.job_id);
                if (polled.status === 'failed') {
                    throw new Error(polled.error_message || 'Scrape failed');
                }
                if (polled.status === 'pending' || polled.status === 'running') {
                    throw new Error('Scrape is still running — try again in a minute.');
                }
            } else if (res.status === 'failed') {
                throw new Error(res.error_message || 'Scrape failed');
            }
            onScraped();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Scrape failed');
        } finally {
            setScraping(false);
        }
    };

    return (
        <div
            onClick={() => onOpen(account.id)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onOpen(account.id);
                }
            }}
            style={{
                background: 'white',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: wide ? '14px 18px' : '16px',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: wide ? 'row' : 'column',
                alignItems: wide ? 'center' : 'stretch',
                gap: wide ? 20 : 14,
                transition: 'transform 0.18s ease, box-shadow 0.18s ease, border-color 0.15s ease',
                boxShadow: '0 1px 2px rgba(13,27,62,0.04)',
                width: '100%',
                minWidth: 0,
            }}
            onMouseEnter={(e) => {
                if (wide) {
                    e.currentTarget.style.borderColor = '#CBD5E1';
                    return;
                }
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.boxShadow = 'var(--shadow)';
            }}
            onMouseLeave={(e) => {
                if (wide) {
                    e.currentTarget.style.borderColor = '';
                    return;
                }
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 1px 2px rgba(13,27,62,0.04)';
            }}
        >
            {/* Header — avatar + platform + handle */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '10px', flex: wide ? '1 1 240px' : undefined, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', minWidth: 0, flex: 1 }}>
                    <AccountAvatar url={avatarUrl || account.avatar_url} platform={account.platform} />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', minWidth: 0, flex: 1 }}>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                        <span
                            style={{
                                fontSize: '10px', fontWeight: 700,
                                padding: '2px 8px', borderRadius: '999px',
                                background: `${accent}1F`, color: accent,
                                textTransform: 'uppercase',
                                letterSpacing: 0.4,
                            }}
                        >
                            {account.platform}
                        </span>
                        {isStudio && (
                            <span
                                title={t('analytics.accounts.ownership.studioTooltip')}
                                style={{
                                    fontSize: '10px', fontWeight: 700,
                                    padding: '2px 8px', borderRadius: '999px',
                                    background: 'rgba(51,122,255,0.12)', color: 'var(--blue)',
                                    textTransform: 'uppercase',
                                    letterSpacing: 0.4,
                                }}
                            >
                                {t('analytics.accounts.ownership.studioBadge')}
                            </span>
                        )}
                    </div>
                    <span
                        style={{
                            fontSize: '15px', fontWeight: 700, color: 'var(--text-1)',
                            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                        }}
                    >
                        @{account.username}
                    </span>
                    {wide && (
                        <span style={{ fontSize: 11, color: 'var(--text-3)' }}>
                            {isStudio
                                ? (account.last_scraped_at
                                    ? `${t('analytics.tracked.lastScraped')} ${timeAgo(account.last_scraped_at)}`
                                    : t('analytics.accounts.studioAutoAnalyzing'))
                                : (account.last_scraped_at
                                    ? `${t('analytics.tracked.lastScraped')} ${timeAgo(account.last_scraped_at)}`
                                    : t('analytics.accounts.neverScraped'))}
                        </span>
                    )}
                    </div>
                </div>
                {/* Compact cards: delete stays top-right of the header */}
                {!wide && onDelete && (
                    <DeleteButton
                        removeHover={removeHover}
                        setRemoveHover={setRemoveHover}
                        onRemove={handleRemove}
                        label={t('analytics.accounts.removeAria').replace('{handle}', `@${account.username}`)}
                    />
                )}
            </div>

            {/* Stat grid */}
            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: showViews ? 'repeat(3, 1fr)' : 'repeat(2, 1fr)',
                    gap: '8px',
                    paddingTop: wide ? 0 : '8px',
                    borderTop: wide ? 'none' : '1px solid var(--border)',
                    flex: wide ? '1.2 1 280px' : undefined,
                    minWidth: wide ? 200 : 0,
                }}
            >
                {showViews && (
                    <Stat label={t('analytics.accounts.metrics.views')} value={formatCount(account.total_views)} />
                )}
                <Stat label={t('analytics.accounts.metrics.engagement')} value={formatCount(account.total_engagement)} accent />
                <Stat
                    label={t('analytics.accounts.metrics.followers')}
                    value={followers != null ? formatCount(followers) : '—'}
                />
            </div>

            {/* Footer — last scraped (compact only); external accounts get manual Analyze */}
            {(!wide || !isStudio) && (
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: wide ? 'flex-end' : (isStudio ? 'flex-start' : 'space-between'),
                    gap: '10px',
                    marginTop: wide ? 0 : 'auto',
                    flexShrink: 0,
                }}
            >
                {!wide && (
                <span style={{ fontSize: '11px', color: 'var(--text-3)' }}>
                    {isStudio
                        ? (account.last_scraped_at
                            ? `${t('analytics.tracked.lastScraped')} ${timeAgo(account.last_scraped_at)}`
                            : t('analytics.accounts.studioAutoAnalyzing'))
                        : (account.last_scraped_at
                            ? `${t('analytics.tracked.lastScraped')} ${timeAgo(account.last_scraped_at)}`
                            : t('analytics.accounts.neverScraped'))}
                </span>
                )}
                {!isStudio && (
                <button
                    type="button"
                    onClick={scrapeNow}
                    disabled={scraping}
                    style={{
                        padding: '7px 14px',
                        borderRadius: '8px',
                        border: 'none',
                        background: scraping ? 'var(--text-3)' : ANALYTICS_CTA_ORANGE,
                        color: 'white',
                        fontSize: '12px',
                        fontWeight: 700,
                        cursor: scraping ? 'not-allowed' : 'pointer',
                        whiteSpace: 'nowrap',
                        transition: 'background 0.15s ease',
                    }}
                    onMouseEnter={(e) => {
                        if (scraping) return;
                        e.currentTarget.style.background = ANALYTICS_CTA_ORANGE_HOVER;
                    }}
                    onMouseLeave={(e) => {
                        if (scraping) return;
                        e.currentTarget.style.background = ANALYTICS_CTA_ORANGE;
                    }}
                >
                    {scraping ? t('analytics.accounts.analyzing') : t('analytics.accounts.analyzeNow')}
                </button>
                )}
            </div>
            )}

            {error && (
                <div style={{ fontSize: '11px', color: '#FF3B30' }}>
                    {error}
                </div>
            )}

            {/* Wide cards: delete sits on the far right, after metrics */}
            {wide && onDelete && (
                <DeleteButton
                    removeHover={removeHover}
                    setRemoveHover={setRemoveHover}
                    onRemove={handleRemove}
                    label={t('analytics.accounts.removeAria').replace('{handle}', `@${account.username}`)}
                />
            )}
        </div>
    );
}

function DeleteButton({
    removeHover,
    setRemoveHover,
    onRemove,
    label,
}: {
    removeHover: boolean;
    setRemoveHover: (next: boolean) => void;
    onRemove: (e: React.MouseEvent | React.KeyboardEvent) => void;
    label: string;
}) {
    return (
        <span
            role="button"
            tabIndex={0}
            aria-label={label}
            title={label}
            onClick={onRemove}
            onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') onRemove(e);
            }}
            onMouseEnter={() => setRemoveHover(true)}
            onMouseLeave={() => setRemoveHover(false)}
            style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 28,
                height: 28,
                borderRadius: 6,
                color: removeHover ? '#b3261e' : 'var(--text-3)',
                background: removeHover ? 'rgba(255,59,48,0.10)' : 'transparent',
                cursor: 'pointer',
                transition: 'background 0.15s ease, color 0.15s ease',
                flexShrink: 0,
                marginLeft: 'auto',
            }}
        >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                <path d="M10 11v6" />
                <path d="M14 11v6" />
                <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
            </svg>
        </span>
    );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <span style={{ fontSize: '15px', fontWeight: 700, color: accent ? 'var(--blue)' : 'var(--text-1)' }}>
                {value}
            </span>
            <span style={{ fontSize: '10px', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: 0.4 }}>
                {label}
            </span>
        </div>
    );
}
