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
 * Accounts dashboard — header, ownership filter, AccountCard grid.
 */
export default function AccountsView({
    accounts, loading, period,
    onOpenAccount, onScraped, onOpenAdd, onDelete,
    isStudio, profilePicFor, ownership, setOwnership,
}: Props) {
    const { t } = useTranslation();
    const periodLabel = t(`analytics.filters.period.${period === 'all' ? 'all' : period}`);

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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <header className="analytics-accounts-header">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
                    <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--text-1)' }}>
                        {t('analytics.accounts.title')}
                    </h2>
                    <p style={{ margin: 0, fontSize: 12, color: 'var(--text-3)' }}>
                        {t('analytics.accounts.subtitle').replace('{period}', periodLabel)}
                    </p>
                </div>
            </header>

            {accounts.length > 0 && (
                <div
                    role="tablist"
                    aria-label={t('analytics.accounts.ownership.label')}
                    style={{
                        display: 'inline-flex',
                        alignSelf: 'flex-start',
                        background: 'white',
                        border: '1px solid var(--border)',
                        borderRadius: 999,
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
                                    borderRadius: 999,
                                    border: 'none',
                                    background: selected ? 'var(--blue)' : 'transparent',
                                    color: selected ? 'white' : 'var(--text-2)',
                                    fontSize: 12,
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
                                        fontSize: 10,
                                        padding: '1px 7px',
                                        borderRadius: 999,
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

            {loading && accounts.length === 0 ? (
                <div
                    style={{
                        padding: '60px 20px',
                        textAlign: 'center',
                        color: 'var(--text-3)',
                        fontSize: 13,
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
                        fontSize: 13,
                    }}
                >
                    {t(`analytics.accounts.ownership.empty.${ownership}`)}
                </div>
            ) : (
                <div
                    style={{
                        display: 'grid',
                        // ≤2 accounts: full-width rows; 3+: compact grid
                        gridTemplateColumns: visible.length <= 2
                            ? '1fr'
                            : 'repeat(auto-fill, minmax(280px, 1fr))',
                        gap: 14,
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
                            wide={visible.length <= 2}
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
                    gap: 16px;
                }
            `}</style>
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
                gap: 12,
                alignItems: 'center',
            }}
        >
            <div
                style={{
                    width: 48, height: 48, borderRadius: 12,
                    background: 'var(--blue-light)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: 'var(--blue)',
                }}
            >
                <PlusIcon />
            </div>
            <div>
                <p style={{ margin: 0, fontWeight: 700, color: 'var(--text-1)', fontSize: 14 }}>
                    {t('analytics.accounts.empty.title')}
                </p>
                <p style={{ margin: '4px 0 0', color: 'var(--text-3)', fontSize: 12 }}>
                    {t('analytics.accounts.empty.subtitle')}
                </p>
            </div>
            <button
                type="button"
                onClick={onOpenAdd}
                style={{
                    padding: '9px 18px', borderRadius: 8,
                    border: 'none', background: ANALYTICS_CTA_ORANGE,
                    color: 'white', fontSize: 13, fontWeight: 700,
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
