'use client';

import { useTranslation } from '@/lib/i18n';
import {
    ANALYTICS_CTA_ORANGE,
    ANALYTICS_CTA_ORANGE_HOVER,
    SORT_OPTIONS,
    type AccountFilter,
    type AnalyticsPlatform,
    type PlatformFilter,
    type SortKey,
    type SourceFilter,
    type TrackedAccount,
} from './analytics-types';

interface Props {
    platform: PlatformFilter;
    setPlatform: (p: PlatformFilter) => void;
    source: SourceFilter;
    setSource: (s: SourceFilter) => void;
    sort: SortKey;
    setSort: (s: SortKey) => void;
    q: string;
    setQ: (v: string) => void;
    accounts: TrackedAccount[];
    account: AccountFilter;
    setAccount: (a: AccountFilter) => void;
    /**
     * Called when the user clicks the red X on an account chip — the parent
     * is expected to DELETE /tracked-accounts/{id}, re-fetch the chip list,
     * and refetch posts. Provided as a prop (instead of fetching here)
     * because the same handler is also wired into TrackedAccountsManager
     * and account-list reloads happen at the page level.
     */
    onRemoveAccount?: (account: TrackedAccount) => void;
    /**
     * URL of the CSV export endpoint with current filters baked in
     * (built by buildCsvExportUrl in analytics-types). When present we
     * render an orange "Export CSV" CTA in the toolbar.
     */
    csvHref?: string;
}

const PLATFORMS: PlatformFilter[] = ['all', 'tiktok', 'instagram', 'youtube', 'facebook'];
const SOURCES: SourceFilter[] = ['all', 'internal', 'external'];

function Pill({
    active, label, onClick,
}: {
    active: boolean;
    label: string;
    onClick: () => void;
}) {
    return (
        <button
            onClick={onClick}
            style={{
                padding: '6px 12px',
                borderRadius: '999px',
                border: active ? '1px solid var(--blue)' : '1px solid var(--border)',
                background: active ? 'var(--blue-light)' : 'white',
                color: active ? 'var(--blue)' : 'var(--text-2)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                whiteSpace: 'nowrap',
            }}
        >
            {label}
        </button>
    );
}

export default function AnalyticsFilters({
    platform, setPlatform,
    source, setSource,
    sort, setSort,
    q, setQ,
    accounts, account, setAccount,
    onRemoveAccount,
    csvHref,
}: Props) {
    const { t } = useTranslation();

    const accountKey = account ? `${account.platform}:${account.username}` : null;

    return (
        <div
            style={{
                background: 'white',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: '14px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
            }}
        >
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {PLATFORMS.map((p) => (
                    <Pill
                        key={p}
                        active={p === platform}
                        label={t(`analytics.filters.platform.${p}`)}
                        onClick={() => {
                            // Changing the platform invalidates an active
                            // account chip — clear it so the filter pair
                            // stays consistent.
                            if (account && account.platform !== p) setAccount(null);
                            setPlatform(p);
                        }}
                    />
                ))}
                <span style={{ flex: 1 }} />
                {SOURCES.map((s) => (
                    <Pill
                        key={s}
                        active={s === source}
                        label={t(`analytics.filters.source.${s}`)}
                        onClick={() => setSource(s)}
                    />
                ))}
            </div>

            {accounts.length > 0 && (
                <div
                    style={{
                        display: 'flex', gap: '14px', flexWrap: 'wrap',
                        borderTop: '1px dashed var(--border)', paddingTop: '12px',
                    }}
                >
                    <Pill
                        active={accountKey === null}
                        label={t('analytics.filters.account.all')}
                        onClick={() => setAccount(null)}
                    />
                    {accounts.map((a) => {
                        const key = `${a.platform}:${a.username}`;
                        const isActive = accountKey === key;
                        return (
                            /* Wrapper carries the X badge so it sits outside
                             * the pill's pill-shaped clip (a top-right X
                             * inside a fully-rounded pill would otherwise
                             * sit inside the colored fill and look heavy).
                             * `paddingTop: 6` reserves room for the badge
                             * so it doesn't overlap the row above. */
                            <div
                                key={a.id}
                                style={{ position: 'relative', paddingTop: 6 }}
                            >
                                <Pill
                                    active={isActive}
                                    label={`@${a.username} · ${a.platform}`}
                                    onClick={() => {
                                        setAccount({
                                            platform: a.platform as AnalyticsPlatform,
                                            username: a.username,
                                        });
                                    }}
                                />
                                {onRemoveAccount && (
                                    <button
                                        type="button"
                                        aria-label={t('analytics.tracked.removeAccount').replace('{username}', a.username)}
                                        title={t('analytics.tracked.removeAccount').replace('{username}', a.username)}
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            // If the user removes the
                                            // currently-active filter we
                                            // also clear the chip — leaving
                                            // it active would request a
                                            // username that no longer
                                            // exists in the list.
                                            if (isActive) setAccount(null);
                                            onRemoveAccount(a);
                                        }}
                                        style={{
                                            position: 'absolute',
                                            top: 0,
                                            right: -4,
                                            width: 16,
                                            height: 16,
                                            borderRadius: '50%',
                                            border: 'none',
                                            background: 'rgba(255,59,48,0.55)',
                                            color: 'white',
                                            cursor: 'pointer',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            padding: 0,
                                            fontSize: '10px',
                                            lineHeight: 1,
                                            boxShadow: '0 1px 2px rgba(0,0,0,0.15)',
                                            transition: 'background 0.15s ease, transform 0.15s ease',
                                        }}
                                        onMouseEnter={(e) => {
                                            e.currentTarget.style.background = 'rgba(255,59,48,0.95)';
                                            e.currentTarget.style.transform = 'scale(1.1)';
                                        }}
                                        onMouseLeave={(e) => {
                                            e.currentTarget.style.background = 'rgba(255,59,48,0.55)';
                                            e.currentTarget.style.transform = 'scale(1)';
                                        }}
                                    >
                                        <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3} strokeLinecap="round">
                                            <line x1="6" y1="6" x2="18" y2="18" />
                                            <line x1="18" y1="6" x2="6" y2="18" />
                                        </svg>
                                    </button>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
                    <svg
                        viewBox="0 0 24 24"
                        style={{
                            width: 14, height: 14,
                            position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)',
                            stroke: 'var(--text-3)', fill: 'none', strokeWidth: 2,
                        }}
                    >
                        <circle cx="11" cy="11" r="7" />
                        <line x1="21" y1="21" x2="16.65" y2="16.65" />
                    </svg>
                    <input
                        type="text"
                        value={q}
                        onChange={(e) => setQ(e.target.value)}
                        placeholder={t('analytics.filters.captionPlaceholder')}
                        style={{
                            width: '100%',
                            padding: '8px 12px 8px 34px',
                            border: '1px solid var(--border)',
                            borderRadius: '10px',
                            background: 'white',
                            color: 'var(--text-1)',
                            fontSize: '13px',
                            outline: 'none',
                        }}
                    />
                </div>

                <select
                    value={sort}
                    onChange={(e) => setSort(e.target.value as SortKey)}
                    style={{
                        padding: '8px 12px',
                        border: '1px solid var(--border)',
                        borderRadius: '10px',
                        background: 'white',
                        color: 'var(--text-1)',
                        fontSize: '13px',
                        fontWeight: 600,
                        cursor: 'pointer',
                    }}
                >
                    {SORT_OPTIONS.map((s) => (
                        <option key={s} value={s}>
                            {t(`analytics.filters.sort.${s}`)}
                        </option>
                    ))}
                </select>

                {csvHref && (
                    <a
                        href={csvHref}
                        // Browser handles auth via the existing session cookie;
                        // `download` is a hint — the backend Content-Disposition
                        // header carries the final filename.
                        download
                        style={{
                            padding: '8px 14px',
                            borderRadius: '10px',
                            background: ANALYTICS_CTA_ORANGE,
                            color: 'white',
                            fontSize: '13px',
                            fontWeight: 700,
                            cursor: 'pointer',
                            textDecoration: 'none',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px',
                            border: 'none',
                            whiteSpace: 'nowrap',
                            transition: 'background 0.15s ease',
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = ANALYTICS_CTA_ORANGE_HOVER; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = ANALYTICS_CTA_ORANGE; }}
                    >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                            <polyline points="7 10 12 15 17 10" />
                            <line x1="12" y1="15" x2="12" y2="3" />
                        </svg>
                        {t('analytics.filters.exportCsv')}
                    </a>
                )}
            </div>
        </div>
    );
}
