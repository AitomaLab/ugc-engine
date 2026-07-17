'use client';

import { useMemo, useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import {
    analyticsFetch,
    pollScrapeJob,
    ANALYTICS_PRIMARY,
    type AnalyticsPlatform,
    type ScrapeResponse,
} from './analytics-types';

type Stage = 'idle' | 'detecting' | 'scraping' | 'analyzing' | 'done' | 'error';

interface Props {
    onAnalyzed: () => void;
    /**
     * Which Analytics tab is open. Drives the placeholder copy AND
     * surfaces a platform picker in `accounts` mode — the backend's
     * URL parser can't infer a platform from a bare `@handle`, so we
     * forward an explicit `platform` field when none can be detected.
     * For post URLs the platform falls out of the domain so the picker
     * stays hidden.
     */
    mode?: 'posts' | 'accounts';
    /** Denser single-line styling when nested inside the dashboard toolbar. */
    compact?: boolean;
}

const ACCOUNT_PLATFORMS: AnalyticsPlatform[] = ['tiktok', 'instagram', 'youtube', 'facebook'];

/**
 * Cheap, parser-equivalent check: "does this input look like a bare handle
 * the backend won't be able to map to a platform on its own?" Mirrors
 * `ugc_backend/analytics/url_parser.detect`'s bare-handle branch — anything
 * with no scheme, slash, or whitespace falls through to needing an
 * explicit `platform`.
 */
function needsPlatformHint(raw: string): boolean {
    const s = raw.trim();
    if (!s) return false;
    const lower = s.toLowerCase();
    if (lower.startsWith('http://') || lower.startsWith('https://')) return false;
    if (s.includes('/') || /\s/.test(s)) return false;
    return true;
}

export default function AnalyzeSearchBar({ onAnalyzed, mode = 'posts', compact = false }: Props) {
    const { t } = useTranslation();
    const placeholderKey =
        mode === 'accounts' ? 'analytics.search.placeholderAccounts' : 'analytics.search.placeholderPosts';
    const [value, setValue] = useState('');
    const [platform, setPlatform] = useState<AnalyticsPlatform>('tiktok');
    const [stage, setStage] = useState<Stage>('idle');
    const [message, setMessage] = useState<string | null>(null);

    const submitting = stage === 'detecting' || stage === 'scraping' || stage === 'analyzing';
    // Show the picker whenever the user is in Accounts mode, OR they typed a
    // bare handle while in Posts mode (defensive — the parser would 400 too).
    const showPlatformPicker = mode === 'accounts' || needsPlatformHint(value);

    const handleSubmit = async (e?: React.FormEvent) => {
        e?.preventDefault();
        const input = value.trim();
        if (!input || submitting) return;
        setStage('detecting');
        setMessage(null);
        try {
            setStage('scraping');
            // Only forward `platform` when the backend genuinely needs it —
            // otherwise it'd shadow the URL-derived platform for post URLs
            // (which could mis-classify e.g. a TikTok URL submitted while
            // the Instagram radio happens to be selected).
            const payload: { input: string; platform?: AnalyticsPlatform } = { input };
            if (needsPlatformHint(input)) payload.platform = platform;

            const res = await analyticsFetch<ScrapeResponse>('/api/analytics/scrape', {
                method: 'POST',
                body: JSON.stringify(payload),
                skipProjectScope: true,
            });
            let finalStatus = res.status;
            let finalError = res.error_message;
            if ((res.status === 'pending' || res.status === 'running') && res.job_id) {
                setStage('analyzing');
                const polled = await pollScrapeJob(res.job_id);
                finalStatus = polled.status;
                finalError = polled.error_message ?? undefined;
            }
            if (finalStatus === 'failed') {
                setStage('error');
                setMessage(finalError || 'Scrape failed');
                return;
            }
            if (finalStatus === 'pending' || finalStatus === 'running') {
                setStage('error');
                setMessage('Scrape is still running — try again in a minute.');
                return;
            }
            setStage('done');
            setValue('');
            onAnalyzed();
            setTimeout(() => setStage('idle'), 1800);
        } catch (err) {
            setStage('error');
            setMessage(err instanceof Error ? err.message : 'Scrape failed');
        }
    };

    const platformChips = useMemo(
        () =>
            ACCOUNT_PLATFORMS.map((p) => ({
                value: p,
                label: t(`analytics.search.platform.${p}`),
            })),
        [t],
    );

    const trimmedLower = value.trim().toLowerCase();
    const looksLikePostUrl =
        /^https?:\/\//.test(trimmedLower) &&
        /\/(?:video|reel|reels|shorts|watch|p|posts|tv|share)\b/.test(trimmedLower);
    const subject: 'account' | 'post' =
        looksLikePostUrl ? 'post' : (mode === 'accounts' ? 'account' : 'post');

    const stageLabel: Record<Stage, string | null> = {
        idle: null,
        detecting: t('analytics.search.detecting'),
        scraping:  t(`analytics.search.capturing.${subject}`),
        analyzing: t('analytics.search.analyzing'),
        done:      t('analytics.search.done'),
        error:     null,
    };

    const platformPicker = showPlatformPicker ? (
        <div
            role="radiogroup"
            aria-label={t('analytics.search.platform.label')}
            style={{
                display: 'inline-flex',
                padding: 2,
                gap: 2,
                borderRadius: 8,
                background: 'white',
                border: '1px solid var(--border)',
                flexShrink: 0,
                flexWrap: compact ? 'nowrap' : 'wrap',
            }}
        >
            {platformChips.map((p) => {
                const selected = platform === p.value;
                return (
                    <button
                        key={p.value}
                        type="button"
                        role="radio"
                        aria-checked={selected}
                        onClick={() => setPlatform(p.value)}
                        disabled={submitting}
                        style={{
                            padding: compact ? '5px 10px' : '6px 14px',
                            borderRadius: 6,
                            border: 'none',
                            background: selected ? ANALYTICS_PRIMARY : 'transparent',
                            color: selected ? 'white' : 'var(--text-2)',
                            fontSize: compact ? 11 : 12,
                            fontWeight: 700,
                            cursor: submitting ? 'not-allowed' : 'pointer',
                            transition: 'background 0.15s ease, color 0.15s ease',
                            whiteSpace: 'nowrap',
                        }}
                    >
                        {p.label}
                    </button>
                );
            })}
        </div>
    ) : null;

    const statusBlock = (
        <>
            {(stage !== 'idle' && stageLabel[stage]) && (
                <div
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        fontSize: 12,
                        color: stage === 'done' ? '#34C759' : ANALYTICS_PRIMARY,
                        fontWeight: 600,
                    }}
                >
                    {submitting && (
                        <span
                            aria-hidden
                            style={{
                                display: 'inline-block',
                                width: 80,
                                height: 4,
                                borderRadius: 2,
                                background:
                                    'linear-gradient(90deg, rgba(51,122,255,0.12) 0%, rgba(51,122,255,0.55) 50%, rgba(51,122,255,0.12) 100%)',
                                backgroundSize: '200% 100%',
                                animation: 'shimmer 1.6s ease-in-out infinite',
                            }}
                        />
                    )}
                    {stageLabel[stage]}
                </div>
            )}
            {stage === 'error' && message && (
                <div style={{ fontSize: 12, color: '#FF3B30', fontWeight: 600 }}>{message}</div>
            )}
        </>
    );

    if (compact) {
        return (
            <form
                onSubmit={handleSubmit}
                style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6,
                    width: '100%',
                }}
            >
                <div
                    className="analyze-search-compact-row"
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        width: '100%',
                        flexWrap: 'nowrap',
                    }}
                >
                    <div style={{ position: 'relative', flex: '1 1 auto', minWidth: 0 }}>
                        <svg
                            viewBox="0 0 24 24"
                            style={{
                                width: 16,
                                height: 16,
                                position: 'absolute',
                                left: 12,
                                top: '50%',
                                transform: 'translateY(-50%)',
                                stroke: 'var(--text-3)',
                                fill: 'none',
                                strokeWidth: 2,
                                pointerEvents: 'none',
                            }}
                        >
                            <circle cx="11" cy="11" r="7" />
                            <line x1="21" y1="21" x2="16.65" y2="16.65" />
                        </svg>
                        <input
                            type="text"
                            value={value}
                            onChange={(e) => setValue(e.target.value)}
                            placeholder={t(placeholderKey)}
                            disabled={submitting}
                            style={{
                                width: '100%',
                                padding: '8px 12px 8px 36px',
                                border: '1px solid var(--border)',
                                borderRadius: 8,
                                background: 'white',
                                color: 'var(--text-1)',
                                fontSize: 13,
                                outline: 'none',
                                boxSizing: 'border-box',
                            }}
                        />
                    </div>
                    {platformPicker}
                    <button
                        type="submit"
                        disabled={submitting || !value.trim()}
                        style={{
                            padding: '8px 14px',
                            borderRadius: 8,
                            border: 'none',
                            background: submitting || !value.trim() ? 'var(--text-3)' : ANALYTICS_PRIMARY,
                            color: 'white',
                            fontSize: 12,
                            fontWeight: 600,
                            cursor: submitting || !value.trim() ? 'not-allowed' : 'pointer',
                            whiteSpace: 'nowrap',
                            flexShrink: 0,
                        }}
                    >
                        {submitting ? '…' : t('analytics.search.cta')}
                    </button>
                </div>
                {statusBlock}
                <style>{`
                    @media (max-width: 720px) {
                        .analyze-search-compact-row {
                            flex-wrap: wrap !important;
                        }
                    }
                `}</style>
            </form>
        );
    }

    return (
        <form
            onSubmit={handleSubmit}
            style={{
                background: '#F8FAFC',
                borderRadius: 'var(--radius)',
                border: '1px solid var(--border)',
                padding: 16,
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
            }}
        >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, position: 'relative' }}>
                <svg
                    viewBox="0 0 24 24"
                    style={{
                        width: 18,
                        height: 18,
                        position: 'absolute',
                        left: 14,
                        top: '50%',
                        transform: 'translateY(-50%)',
                        stroke: 'var(--text-3)',
                        fill: 'none',
                        strokeWidth: 2,
                    }}
                >
                    <circle cx="11" cy="11" r="7" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                <input
                    type="text"
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    placeholder={t(placeholderKey)}
                    disabled={submitting}
                    style={{
                        flex: 1,
                        padding: '12px 14px 12px 42px',
                        border: '1px solid var(--border)',
                        borderRadius: 10,
                        background: 'white',
                        color: 'var(--text-1)',
                        fontSize: 14,
                        outline: 'none',
                        transition: 'border-color 0.15s ease',
                    }}
                />
                <button
                    type="submit"
                    disabled={submitting || !value.trim()}
                    style={{
                        padding: '10px 20px',
                        borderRadius: 10,
                        border: 'none',
                        background: submitting || !value.trim() ? 'var(--text-3)' : ANALYTICS_PRIMARY,
                        color: 'white',
                        fontSize: 13,
                        fontWeight: 600,
                        cursor: submitting || !value.trim() ? 'not-allowed' : 'pointer',
                        whiteSpace: 'nowrap',
                        transition: 'background 0.15s ease',
                    }}
                >
                    {submitting ? '…' : t('analytics.search.cta')}
                </button>
            </div>

            {showPlatformPicker && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span
                        style={{
                            fontSize: 11,
                            fontWeight: 700,
                            color: 'var(--text-3)',
                            textTransform: 'uppercase',
                            letterSpacing: 0.4,
                        }}
                    >
                        {t('analytics.search.platform.label')}
                    </span>
                    {platformPicker}
                </div>
            )}

            {statusBlock}
        </form>
    );
}
