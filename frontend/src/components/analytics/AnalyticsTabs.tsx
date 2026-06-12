'use client';

import { useTranslation } from '@/lib/i18n';
import { ANALYTICS_PRIMARY } from './analytics-types';

export type PublishTabKey = 'calendar' | 'analytics';

interface Props {
    value: PublishTabKey;
    onChange: (next: PublishTabKey) => void;
}

const TABS: { key: PublishTabKey; labelKey: string }[] = [
    { key: 'calendar',  labelKey: 'publish.tabs.calendar' },
    { key: 'analytics', labelKey: 'publish.tabs.analytics' },
];

export default function AnalyticsTabs({ value, onChange }: Props) {
    const { t } = useTranslation();

    return (
        <div
            role="tablist"
            style={{
                display: 'inline-flex',
                gap: '4px',
                padding: '4px',
                borderRadius: '12px',
                background: 'white',
                border: '1px solid var(--border)',
                boxShadow: '0 1px 2px rgba(13,27,62,0.04)',
                overflowX: 'auto',
                maxWidth: '100%',
            }}
        >
            {TABS.map((tab) => {
                const active = tab.key === value;
                return (
                    <button
                        key={tab.key}
                        role="tab"
                        aria-selected={active}
                        onClick={() => onChange(tab.key)}
                        style={{
                            padding: '8px 18px',
                            borderRadius: '8px',
                            border: 'none',
                            background: active ? ANALYTICS_PRIMARY : 'transparent',
                            color: active ? 'white' : 'var(--text-2)',
                            fontSize: '13px',
                            fontWeight: 600,
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                            whiteSpace: 'nowrap',
                        }}
                    >
                        {t(tab.labelKey)}
                    </button>
                );
            })}
        </div>
    );
}
