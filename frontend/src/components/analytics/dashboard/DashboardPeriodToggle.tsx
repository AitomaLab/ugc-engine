'use client';

import { useTranslation } from '@/lib/i18n';
import { DASHBOARD_PERIODS, type Period } from '../analytics-types';

interface Props {
    period: Period;
    onChange: (next: Period) => void;
}

const LABEL_KEY: Record<Period, string> = {
    '7d': 'analytics.filters.period.7d',
    '30d': 'analytics.filters.period.30d',
    '90d': 'analytics.filters.period.90d',
    quarter: 'analytics.dashboard.period.quarter',
    all: 'analytics.filters.period.all',
};

export default function DashboardPeriodToggle({ period, onChange }: Props) {
    const { t } = useTranslation();
    return (
        <div
            role="radiogroup"
            aria-label="Period"
            style={{
                display: 'inline-flex',
                padding: 4,
                borderRadius: 999,
                background: '#F1F5F9',
                border: '1px solid #E2E8F0',
                gap: 4,
            }}
        >
            {DASHBOARD_PERIODS.map((p) => {
                const active = p === period;
                return (
                    <button
                        key={p}
                        type="button"
                        role="radio"
                        aria-checked={active}
                        onClick={() => onChange(p)}
                        style={{
                            padding: '7px 16px',
                            borderRadius: 999,
                            border: 'none',
                            background: active ? '#337AFF' : 'transparent',
                            color: active ? '#FFFFFF' : '#475569',
                            fontSize: 12,
                            fontWeight: 700,
                            cursor: 'pointer',
                            transition: 'background 0.15s ease, color 0.15s ease',
                        }}
                    >
                        {t(LABEL_KEY[p])}
                    </button>
                );
            })}
        </div>
    );
}
