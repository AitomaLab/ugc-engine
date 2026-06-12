'use client';

import { useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import Modal from './Modal';
import {
    ANALYTICS_CTA_ORANGE,
    ANALYTICS_CTA_ORANGE_HOVER,
    analyticsFetch,
    type AnalyticsPlatform,
    type TrackedAccountWithJob,
} from './analytics-types';

interface Props {
    onClose: () => void;
    onAdded: () => void;
}

const TOGGLE_PLATFORMS: AnalyticsPlatform[] = ['tiktok', 'instagram'];

export default function AddAccountModal({ onClose, onAdded }: Props) {
    const { t } = useTranslation();
    const [platform, setPlatform] = useState<AnalyticsPlatform>('tiktok');
    const [username, setUsername] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        const u = username.trim().replace(/^@/, '').toLowerCase();
        if (!u || submitting) return;
        setSubmitting(true);
        setError(null);
        try {
            const res = await analyticsFetch<TrackedAccountWithJob>(
                '/api/analytics/tracked-accounts',
                {
                    method: 'POST',
                    body: JSON.stringify({ platform, username: u }),
                    skipProjectScope: true,
                },
            );
            if (res.status === 'failed' && res.error_message) {
                setError(res.error_message);
                return;
            }
            onAdded();
            onClose();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to add account');
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <Modal
            title={t('analytics.add.title')}
            onClose={onClose}
            footer={
                <>
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={submitting}
                        style={{
                            padding: '9px 16px',
                            borderRadius: '8px',
                            border: '1px solid var(--border)',
                            background: 'white',
                            color: 'var(--text-2)',
                            fontSize: '13px',
                            fontWeight: 600,
                            cursor: 'pointer',
                        }}
                    >
                        {t('common.cancel')}
                    </button>
                    <button
                        type="submit"
                        form="add-account-form"
                        disabled={submitting || !username.trim()}
                        style={{
                            padding: '9px 18px',
                            borderRadius: '8px',
                            border: 'none',
                            background: submitting || !username.trim()
                                ? 'var(--text-3)' : ANALYTICS_CTA_ORANGE,
                            color: 'white',
                            fontSize: '13px',
                            fontWeight: 700,
                            cursor: submitting || !username.trim() ? 'not-allowed' : 'pointer',
                            transition: 'background 0.15s ease',
                        }}
                        onMouseEnter={(e) => {
                            if (submitting || !username.trim()) return;
                            e.currentTarget.style.background = ANALYTICS_CTA_ORANGE_HOVER;
                        }}
                        onMouseLeave={(e) => {
                            if (submitting || !username.trim()) return;
                            e.currentTarget.style.background = ANALYTICS_CTA_ORANGE;
                        }}
                    >
                        {submitting ? t('common.loading') : t('analytics.add.submit')}
                    </button>
                </>
            }
        >
            <form id="add-account-form" onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <p style={{ margin: 0, fontSize: 13, color: 'var(--text-2)', lineHeight: 1.5 }}>
                    {t('analytics.add.autoAnalyzeHint')}
                </p>

                <div style={{ display: 'flex', gap: 8 }}>
                    {TOGGLE_PLATFORMS.map((p) => {
                        const active = platform === p;
                        return (
                            <button
                                key={p}
                                type="button"
                                onClick={() => setPlatform(p)}
                                style={{
                                    flex: 1,
                                    padding: '10px 12px',
                                    borderRadius: 8,
                                    border: active ? '2px solid var(--blue)' : '1px solid var(--border)',
                                    background: active ? 'rgba(51,122,255,0.08)' : 'white',
                                    color: 'var(--text-1)',
                                    fontSize: 13,
                                    fontWeight: 700,
                                    cursor: 'pointer',
                                    textTransform: 'capitalize',
                                }}
                            >
                                {p}
                            </button>
                        );
                    })}
                </div>

                <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-2)' }}>
                        {t('analytics.add.username')}
                    </span>
                    <input
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        placeholder="@handle"
                        autoFocus
                        style={{
                            padding: '10px 12px',
                            borderRadius: 8,
                            border: '1px solid var(--border)',
                            fontSize: 14,
                        }}
                    />
                </label>

                {error && (
                    <p style={{ margin: 0, fontSize: 12, color: '#b3261e' }}>{error}</p>
                )}
            </form>
        </Modal>
    );
}
