'use client';

import { useTranslation } from '@/lib/i18n';

export type AnalyticsView = 'accounts' | 'posts';

interface Props {
    view: AnalyticsView;
    setView: (v: AnalyticsView) => void;
}

/**
 * Accounts ⇄ Posts segmented control. Pure controlled component — the
 * parent (`AnalyticsTab`) owns the URL sync via `useSearchParams` so
 * deep-links like `/schedule?tab=analytics&view=accounts` work without
 * this component having to know about routing.
 */
export default function ViewToggle({ view, setView }: Props) {
    const { t } = useTranslation();

    const Item = ({ id, label }: { id: AnalyticsView; label: string }) => {
        const active = view === id;
        return (
            <button
                type="button"
                onClick={() => setView(id)}
                aria-pressed={active}
                style={{
                    padding: '8px 18px',
                    borderRadius: '8px',
                    border: 'none',
                    background: active ? 'white' : 'transparent',
                    color: active ? 'var(--text-1)' : 'var(--text-3)',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    transition: 'background 0.15s ease, color 0.15s ease',
                    boxShadow: active ? '0 1px 3px rgba(13,27,62,0.10)' : 'none',
                    minWidth: 110,
                }}
            >
                {label}
            </button>
        );
    };

    return (
        <div
            role="tablist"
            style={{
                display: 'inline-flex',
                gap: '4px',
                padding: '4px',
                background: 'var(--blue-light)',
                borderRadius: '10px',
                border: '1px solid var(--border)',
                width: 'fit-content',
            }}
        >
            <Item id="accounts" label={t('analytics.view.accounts')} />
            <Item id="posts" label={t('analytics.view.posts')} />
        </div>
    );
}
