'use client';

import { useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import {
    timeAgo,
    useAccountStrategyReport,
    type TrackedAccountAggregate,
} from './analytics-types';
import { parseStrategyReport } from './account/parseAccountReport';
import { Section, renderInlineBold } from './account/AccountUiKit';

const PLATFORM_ACCENT: Record<string, string> = {
    instagram: '#E1306C',
    tiktok:    '#000000',
    youtube:   '#FF0000',
    facebook:  '#1877F2',
};

/** Cards rendered (and reports fetched) up-front; more via "Load more". */
const INITIAL_CARDS = 6;

interface Props {
    accounts: TrackedAccountAggregate[];
    profilePicFor?: (platform: string, username: string) => string | undefined;
    isStudioAccount?: (platform: string, username: string) => boolean;
    /** Scope to the account + switch to the full strategy view. */
    onOpenStrategy: (accountId: string) => void;
    refreshKey?: number;
    onOpenAdd: () => void;
}

/**
 * All-accounts "AI Strategy" view — one card per tracked account showing its
 * top ranked Do-Next actions, with a jump into the full per-account
 * diagnosis. Cards beyond the first page mount (and fetch) lazily.
 */
export default function StrategyHub({
    accounts,
    profilePicFor,
    isStudioAccount,
    onOpenStrategy,
    refreshKey = 0,
    onOpenAdd,
}: Props) {
    const { t } = useTranslation();
    const [visibleCount, setVisibleCount] = useState(INITIAL_CARDS);

    if (accounts.length === 0) {
        return (
            <div
                style={{
                    background: 'white',
                    border: '1px dashed var(--border)',
                    borderRadius: 12,
                    padding: '32px 24px',
                    textAlign: 'center',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 10,
                    alignItems: 'center',
                }}
            >
                <p style={{ margin: 0, fontWeight: 700, color: 'var(--text-1)', fontSize: 14 }}>
                    {t('analytics.accounts.empty.title')}
                </p>
                <p style={{ margin: 0, color: 'var(--text-3)', fontSize: 12 }}>
                    {t('analytics.accounts.empty.subtitle')}
                </p>
                <button
                    type="button"
                    onClick={onOpenAdd}
                    style={{
                        padding: '8px 16px', borderRadius: 8, border: '1px solid var(--border)',
                        background: 'white', color: 'var(--blue)', fontSize: 12, fontWeight: 700,
                        cursor: 'pointer',
                    }}
                >
                    {t('analytics.add.cta')}
                </button>
            </div>
        );
    }

    const visible = accounts.slice(0, visibleCount);

    return (
        <Section
            title={t('analytics.strategyHub.title')}
            subtitle={t('analytics.strategyHub.subtitle')}
        >
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 12 }}>
                {visible.map((acct) => (
                    <StrategyHubCard
                        key={acct.id}
                        account={acct}
                        avatarUrl={
                            ((Boolean(acct.linked_via_connections)
                                || (isStudioAccount ? isStudioAccount(acct.platform, acct.username) : false))
                                && profilePicFor
                                ? profilePicFor(acct.platform, acct.username)
                                : undefined) || acct.avatar_url || undefined
                        }
                        refreshKey={refreshKey}
                        onOpenStrategy={onOpenStrategy}
                    />
                ))}
            </div>
            {accounts.length > visible.length && (
                <button
                    type="button"
                    onClick={() => setVisibleCount((n) => n + INITIAL_CARDS)}
                    style={{
                        alignSelf: 'center',
                        padding: '7px 16px',
                        borderRadius: 8,
                        border: '1px solid var(--border)',
                        background: 'white',
                        color: 'var(--text-2)',
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: 'pointer',
                    }}
                >
                    {t('analytics.accounts.topPosts.loadMore')}
                </button>
            )}
        </Section>
    );
}

function StrategyHubCard({
    account,
    avatarUrl,
    refreshKey,
    onOpenStrategy,
}: {
    account: TrackedAccountAggregate;
    avatarUrl?: string;
    refreshKey: number;
    onOpenStrategy: (accountId: string) => void;
}) {
    const { t, lang } = useTranslation();
    const { data: strategy, loading } = useAccountStrategyReport(account.id, refreshKey, lang);
    const accent = PLATFORM_ACCENT[account.platform] || 'var(--text-3)';
    const [broken, setBroken] = useState(false);

    const parsed = strategy?.report ? parseStrategyReport(strategy.report) : null;
    const actions = parsed?.recognized ? parsed.actionItems.slice(0, 3) : [];

    return (
        <div
            style={{
                background: 'white',
                border: '1px solid var(--border)',
                borderRadius: 14,
                padding: '14px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
                minWidth: 0,
            }}
        >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                {avatarUrl && !broken ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                        src={avatarUrl}
                        alt=""
                        loading="lazy"
                        referrerPolicy="no-referrer"
                        onError={() => setBroken(true)}
                        style={{
                            width: 32, height: 32, borderRadius: '50%',
                            objectFit: 'cover', border: '1px solid var(--border)',
                            background: 'var(--blue-light)', flexShrink: 0,
                        }}
                    />
                ) : (
                    <span
                        aria-hidden
                        style={{
                            width: 32, height: 32, borderRadius: '50%',
                            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                            background: `${accent}18`, color: accent,
                            fontSize: 14, fontWeight: 800, flexShrink: 0,
                        }}
                    >
                        {account.platform.slice(0, 1).toUpperCase()}
                    </span>
                )}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 0, flex: 1 }}>
                    <span style={{
                        fontSize: 13, fontWeight: 800, color: 'var(--text-1)',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                    }}>
                        @{account.username}
                    </span>
                    <span style={{ fontSize: 10, fontWeight: 700, color: accent, textTransform: 'uppercase', letterSpacing: 0.4 }}>
                        {account.platform}
                    </span>
                </div>
                {strategy?.generated_at && (
                    <span style={{ fontSize: 10, color: 'var(--text-3)', whiteSpace: 'nowrap', flexShrink: 0 }}>
                        {t('analytics.accounts.strategy.updated').replace('{when}', timeAgo(strategy.generated_at))}
                    </span>
                )}
            </div>

            {actions.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {actions.map((item, i) => (
                        <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                            <span
                                aria-hidden
                                style={{
                                    flexShrink: 0,
                                    width: 18, height: 18, borderRadius: '50%',
                                    background: 'var(--blue)', color: 'white',
                                    fontSize: 10, fontWeight: 800,
                                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                                    marginTop: 1,
                                }}
                            >
                                {i + 1}
                            </span>
                            <span style={{ fontSize: 12, lineHeight: 1.45, color: 'var(--text-2)', minWidth: 0 }}>
                                {renderInlineBold(item, `hub-${account.id}-${i}`)}
                            </span>
                        </div>
                    ))}
                </div>
            ) : (
                <div style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.5 }}>
                    {loading
                        ? t('analytics.accounts.strategy.loading')
                        : strategy?.report
                            ? t('analytics.strategyHub.reportReady')
                            : t('analytics.accounts.strategy.pending')}
                </div>
            )}

            <button
                type="button"
                onClick={() => onOpenStrategy(account.id)}
                style={{
                    alignSelf: 'flex-start',
                    marginTop: 'auto',
                    padding: '6px 12px',
                    borderRadius: 8,
                    border: '1px solid var(--border)',
                    background: 'white',
                    color: 'var(--blue)',
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                }}
            >
                {t('analytics.accounts.overview.seeStrategy')} →
            </button>
        </div>
    );
}
