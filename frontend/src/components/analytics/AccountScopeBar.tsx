'use client';

import { useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import {
    ANALYTICS_PRIMARY,
    ANALYTICS_PRIMARY_HOVER,
    type TrackedAccountAggregate,
} from './analytics-types';

const PLATFORM_ACCENT: Record<string, string> = {
    instagram: '#E1306C',
    tiktok:    '#000000',
    youtube:   '#FF0000',
    facebook:  '#1877F2',
};

interface Props {
    accounts: TrackedAccountAggregate[];
    /** 'all' or a tracked-account id. */
    scope: string;
    onScopeChange: (scope: string) => void;
    profilePicFor?: (platform: string, username: string) => string | undefined;
    isStudioAccount?: (platform: string, username: string) => boolean;
    onAddAccount: () => void;
}

/**
 * Persistent account-scope switcher — the core control of the Analytics
 * surface. "All accounts" plus one pill per connected/tracked account.
 * Every tab (Overview / Videos / AI Strategy / AI Learnings) re-scopes to
 * the selected pill, so global and per-account analytics are the same
 * surface instead of separate pages.
 */
export default function AccountScopeBar({
    accounts,
    scope,
    onScopeChange,
    profilePicFor,
    isStudioAccount,
    onAddAccount,
}: Props) {
    const { t } = useTranslation();

    return (
        <div
            role="tablist"
            aria-label={t('analytics.scope.label')}
            style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: 4,
                borderRadius: 12,
                background: '#F8FAFC',
                border: '1px solid var(--border, #E2E8F0)',
                overflowX: 'auto',
                scrollbarWidth: 'thin',
            }}
        >
            <ScopePill
                active={scope === 'all'}
                onClick={() => onScopeChange('all')}
                icon={<GlobeIcon />}
                label={t('analytics.scope.all')}
            />

            {accounts.map((acct) => {
                const studio = Boolean(acct.linked_via_connections)
                    || (isStudioAccount ? isStudioAccount(acct.platform, acct.username) : false);
                const avatar = (studio && profilePicFor
                    ? profilePicFor(acct.platform, acct.username)
                    : undefined) || acct.avatar_url || undefined;
                return (
                    <ScopePill
                        key={acct.id}
                        active={scope === acct.id}
                        onClick={() => onScopeChange(acct.id)}
                        icon={<PillAvatar url={avatar} platform={acct.platform} />}
                        label={`@${acct.username}`}
                        tag={acct.platform}
                        studio={studio}
                    />
                );
            })}

            <button
                type="button"
                onClick={onAddAccount}
                style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    padding: '6px 12px',
                    borderRadius: 9,
                    border: 'none',
                    background: 'transparent',
                    color: ANALYTICS_PRIMARY,
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    flexShrink: 0,
                    marginLeft: 'auto',
                    transition: 'color 0.15s ease',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.color = ANALYTICS_PRIMARY_HOVER; }}
                onMouseLeave={(e) => { e.currentTarget.style.color = ANALYTICS_PRIMARY; }}
            >
                <PlusIcon /> {t('analytics.add.cta')}
            </button>
        </div>
    );
}

function ScopePill({
    active,
    onClick,
    icon,
    label,
    tag,
    studio,
}: {
    active: boolean;
    onClick: () => void;
    icon: React.ReactNode;
    label: string;
    tag?: string;
    studio?: boolean;
}) {
    const { t } = useTranslation();
    return (
        <button
            type="button"
            role="tab"
            aria-selected={active}
            onClick={onClick}
            style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 7,
                padding: '5px 12px 5px 7px',
                borderRadius: 9,
                // Every pill reads as a button — white container + border —
                // so accounts are obviously selectable, not bar decoration.
                border: active ? '1.5px solid #337AFF' : '1px solid var(--border, #E2E8F0)',
                background: active ? 'rgba(51,122,255,0.08)' : '#FFFFFF',
                boxShadow: active
                    ? '0 1px 3px rgba(51,122,255,0.25)'
                    : '0 1px 2px rgba(13,27,62,0.05)',
                color: active ? 'var(--text-1, #0F172A)' : '#475569',
                fontSize: 12,
                fontWeight: 700,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                flexShrink: 0,
                transition: 'background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease',
            }}
            onMouseEnter={(e) => {
                if (!active) e.currentTarget.style.borderColor = '#9EC0FF';
            }}
            onMouseLeave={(e) => {
                if (!active) e.currentTarget.style.borderColor = 'var(--border, #E2E8F0)';
            }}
        >
            {icon}
            {label}
            {tag && (
                <span style={{ fontSize: 9, fontWeight: 600, opacity: 0.6, textTransform: 'uppercase' }}>
                    {tag}
                </span>
            )}
            {studio && (
                <span
                    style={{
                        fontSize: 9,
                        fontWeight: 700,
                        color: 'var(--blue)',
                        background: 'rgba(51,122,255,0.12)',
                        padding: '1px 6px',
                        borderRadius: 999,
                    }}
                >
                    {t('analytics.accounts.ownership.studioBadge')}
                </span>
            )}
        </button>
    );
}

function PillAvatar({ url, platform }: { url?: string; platform: string }) {
    const accent = PLATFORM_ACCENT[platform] || 'var(--text-3)';
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
                    width: 20, height: 20, borderRadius: '50%',
                    objectFit: 'cover',
                    border: '1px solid var(--border)',
                    background: 'var(--blue-light)',
                    flexShrink: 0,
                }}
            />
        );
    }
    return (
        <span
            aria-hidden
            style={{
                width: 20, height: 20, borderRadius: '50%',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                background: `${accent}18`,
                color: accent,
                fontSize: 10, fontWeight: 800,
                flexShrink: 0,
            }}
        >
            {platform.slice(0, 1).toUpperCase()}
        </span>
    );
}

function GlobeIcon() {
    return (
        <span
            aria-hidden
            style={{
                width: 20, height: 20, borderRadius: '50%',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                background: 'rgba(51,122,255,0.12)',
                color: 'var(--blue)',
                flexShrink: 0,
            }}
        >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <circle cx="12" cy="12" r="10" />
                <line x1="2" y1="12" x2="22" y2="12" />
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
            </svg>
        </span>
    );
}

function PlusIcon() {
    return (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.6} strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
    );
}
