'use client';

import { useMemo } from 'react';
import { useTranslation } from '@/lib/i18n';
import AccountCard from './AccountCard';
import {
    ACCOUNT_OWNERSHIP_OPTIONS,
    ANALYTICS_CTA_ORANGE,
    ANALYTICS_CTA_ORANGE_HOVER,
    type AccountOwnership,
    type Period,
    type TrackedAccountAggregate,
} from './analytics-types';

interface Props {
    accounts: TrackedAccountAggregate[];
    totalAccounts: number;
    totalPosts: number;
    avgHealth: number | null;
    loading: boolean;
    period: Period;
    onOpenAccount: (accountId: string) => void;
    onScraped: () => void;
    onOpenAdd: () => void;
    /** Optional remove handler — forwarded to each AccountCard. */
    onDelete?: (accountId: string) => void;
    /**
     * Studio / External classifier. Receives `(platform, username)` and
     * returns true when the account is owned by the user (i.e. linked
     * under /connections). Default returns false → every account treated
     * as External.
     */
    isStudio?: (platform: string, username: string) => boolean;
    /** Profile photo resolver — Connections profilePic with tracked avatar fallback. */
    profilePicFor?: (platform: string, username: string) => string | undefined;
    /** Active ownership filter — controlled by the parent. */
    ownership: AccountOwnership;
    setOwnership: (next: AccountOwnership) => void;
}

/**
 * Accounts dashboard — the "Accounts" leg of the Accounts ⇄ Posts toggle.
 *
 *   • Aggregate strip: Total Accounts · Scraped Posts · Avg Health
 *   • Header CTAs: Add Account (orange primary) + Settings (secondary)
 *   • Responsive grid of AccountCard rows
 *
 * Mobile-first layout: on narrow viewports the CTAs sit beneath the
 * aggregate strip (info-first per v2 UX guidelines); on desktop they
 * float right of the header.
 */
export default function AccountsView({
    accounts, totalAccounts, totalPosts, avgHealth, loading, period,
    onOpenAccount, onScraped, onOpenAdd, onDelete,
    isStudio, profilePicFor, ownership, setOwnership,
}: Props) {
    const { t } = useTranslation();
    const periodLabel = t(`analytics.filters.period.${period === 'all' ? 'all' : period}`);

    /** Pre-compute studio flags once per render so the filter + each card
     *  don't have to call `isStudio` twice for the same account. */
    const tagged = useMemo(
        () =>
            accounts.map((a) => ({
                account: a,
                studio:
                    Boolean(a.linked_via_connections)
                    || (isStudio ? isStudio(a.platform, a.username) : false),
            })),
        [accounts, isStudio],
    );

    const visible = useMemo(() => {
        if (ownership === 'all') return tagged;
        if (ownership === 'studio') return tagged.filter((x) => x.studio);
        return tagged.filter((x) => !x.studio);
    }, [tagged, ownership]);

    const counts = useMemo(() => {
        const studio = tagged.filter((x) => x.studio).length;
        return { all: tagged.length, studio, external: tagged.length - studio };
    }, [tagged]);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <header className="analytics-accounts-header">
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', minWidth: 0 }}>
                    <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 700, color: 'var(--text-1)' }}>
                        {t('analytics.accounts.title')}
                    </h2>
                    <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-3)' }}>
                        {t('analytics.accounts.subtitle').replace('{period}', periodLabel)}
                    </p>
                </div>

                <div className="analytics-accounts-actions">
                    <button
                        type="button"
                        onClick={onOpenAdd}
                        style={{
                            padding: '9px 16px', borderRadius: '8px',
                            border: 'none',
                            background: ANALYTICS_CTA_ORANGE,
                            color: 'white', fontSize: '13px', fontWeight: 700,
                            cursor: 'pointer', whiteSpace: 'nowrap',
                            transition: 'background 0.15s ease',
                            display: 'inline-flex', alignItems: 'center', gap: '6px',
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = ANALYTICS_CTA_ORANGE_HOVER; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = ANALYTICS_CTA_ORANGE; }}
                    >
                        <PlusIcon /> {t('analytics.add.cta')}
                    </button>
                </div>
            </header>

            {/* Aggregate strip */}
            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                    gap: '12px',
                }}
            >
                <Agg label={t('analytics.accounts.aggregate.totalAccounts')} value={String(totalAccounts)} />
                <Agg label={t('analytics.accounts.aggregate.scrapedPosts')} value={String(totalPosts)} />
                <Agg
                    label={t('analytics.accounts.aggregate.avgHealth')}
                    value={avgHealth != null ? `${avgHealth}/100` : '—'}
                    accent
                />
            </div>

            {/* Ownership filter — only useful once we actually have accounts. */}
            {accounts.length > 0 && (
                <div
                    role="tablist"
                    aria-label={t('analytics.accounts.ownership.label')}
                    style={{
                        display: 'inline-flex',
                        alignSelf: 'flex-start',
                        background: 'white',
                        border: '1px solid var(--border)',
                        borderRadius: '999px',
                        padding: 4,
                        gap: 2,
                        boxShadow: '0 1px 2px rgba(13,27,62,0.04)',
                    }}
                >
                    {ACCOUNT_OWNERSHIP_OPTIONS.map((opt) => {
                        const selected = ownership === opt;
                        const count = counts[opt];
                        return (
                            <button
                                key={opt}
                                role="tab"
                                aria-selected={selected}
                                type="button"
                                onClick={() => setOwnership(opt)}
                                style={{
                                    padding: '6px 14px',
                                    borderRadius: '999px',
                                    border: 'none',
                                    background: selected ? 'var(--blue)' : 'transparent',
                                    color: selected ? 'white' : 'var(--text-2)',
                                    fontSize: '12px',
                                    fontWeight: 700,
                                    cursor: 'pointer',
                                    transition: 'background 0.15s ease, color 0.15s ease',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: 6,
                                }}
                            >
                                {t(`analytics.accounts.ownership.${opt}`)}
                                <span
                                    style={{
                                        fontSize: '10px',
                                        padding: '1px 7px',
                                        borderRadius: '999px',
                                        background: selected ? 'rgba(255,255,255,0.22)' : 'var(--blue-light)',
                                        color: selected ? 'white' : 'var(--text-3)',
                                        fontWeight: 700,
                                    }}
                                >
                                    {count}
                                </span>
                            </button>
                        );
                    })}
                </div>
            )}

            {/* Account grid */}
            {loading && accounts.length === 0 ? (
                <div
                    style={{
                        padding: '60px 20px',
                        textAlign: 'center',
                        color: 'var(--text-3)',
                        fontSize: '13px',
                    }}
                >
                    {t('common.loading')}
                </div>
            ) : accounts.length === 0 ? (
                <EmptyState onOpenAdd={onOpenAdd} />
            ) : visible.length === 0 ? (
                <div
                    style={{
                        background: 'white',
                        border: '1px dashed var(--border)',
                        borderRadius: 'var(--radius)',
                        padding: '32px 24px',
                        textAlign: 'center',
                        color: 'var(--text-3)',
                        fontSize: '13px',
                    }}
                >
                    {t(`analytics.accounts.ownership.empty.${ownership}`)}
                </div>
            ) : (
                <div
                    style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                        gap: '14px',
                    }}
                >
                    {visible.map(({ account: a, studio }) => (
                        <AccountCard
                            key={a.id}
                            account={a}
                            onOpen={onOpenAccount}
                            onScraped={onScraped}
                            onDelete={onDelete}
                            isStudio={studio}
                            avatarUrl={
                                a.avatar_url
                                || (studio && profilePicFor
                                    ? profilePicFor(a.platform, a.username)
                                    : undefined)
                            }
                        />
                    ))}
                </div>
            )}

            <style>{`
                .analytics-accounts-header {
                    display: flex;
                    align-items: flex-start;
                    justify-content: space-between;
                    gap: 16px;
                    flex-wrap: wrap;
                }
                .analytics-accounts-actions {
                    display: flex;
                    gap: 8px;
                    flex-wrap: wrap;
                }
                @media (max-width: 640px) {
                    .analytics-accounts-header {
                        flex-direction: column;
                    }
                    .analytics-accounts-actions {
                        width: 100%;
                    }
                    .analytics-accounts-actions > button {
                        flex: 1;
                        justify-content: center;
                    }
                }
            `}</style>
        </div>
    );
}

function Agg({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
    return (
        <div
            style={{
                background: 'white',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: '14px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
            }}
        >
            <span style={{ fontSize: '11px', color: 'var(--text-3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.4 }}>
                {label}
            </span>
            <span style={{ fontSize: '20px', fontWeight: 700, color: accent ? 'var(--blue)' : 'var(--text-1)' }}>
                {value}
            </span>
        </div>
    );
}

function EmptyState({ onOpenAdd }: { onOpenAdd: () => void }) {
    const { t } = useTranslation();
    return (
        <div
            style={{
                background: 'white',
                border: '1px dashed var(--border)',
                borderRadius: 'var(--radius)',
                padding: '40px 24px',
                textAlign: 'center',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                alignItems: 'center',
            }}
        >
            <div
                style={{
                    width: 48, height: 48, borderRadius: '12px',
                    background: 'var(--blue-light)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: 'var(--blue)',
                }}
            >
                <PlusIcon />
            </div>
            <div>
                <p style={{ margin: 0, fontWeight: 700, color: 'var(--text-1)', fontSize: '14px' }}>
                    {t('analytics.accounts.empty.title')}
                </p>
                <p style={{ margin: '4px 0 0', color: 'var(--text-3)', fontSize: '12px' }}>
                    {t('analytics.accounts.empty.subtitle')}
                </p>
            </div>
            <button
                type="button"
                onClick={onOpenAdd}
                style={{
                    padding: '9px 18px', borderRadius: '8px',
                    border: 'none', background: ANALYTICS_CTA_ORANGE,
                    color: 'white', fontSize: '13px', fontWeight: 700,
                    cursor: 'pointer',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = ANALYTICS_CTA_ORANGE_HOVER; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = ANALYTICS_CTA_ORANGE; }}
            >
                {t('analytics.add.cta')}
            </button>
        </div>
    );
}

function PlusIcon() {
    return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
    );
}
