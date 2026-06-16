'use client';

import { useEffect, useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import Modal from './Modal';
import {
    ANALYTICS_CTA_ORANGE,
    ANALYTICS_CTA_ORANGE_HOVER,
    SCRAPE_FREQUENCY_OPTIONS,
    analyticsFetch,
    type AnalyticsSettings,
    type ScrapeFrequency,
} from './analytics-types';

interface Props {
    onClose: () => void;
    initial: AnalyticsSettings | null;
    onSaved: () => void;
}

/**
 * Tenant-level configuration for the analytics module:
 *
 *   • Default scrape frequency / top-N → applied when adding a new account
 *   • Monthly budget limit USD → soft cap for future checks
 *   • Alert threshold per scrape → ditto
 *
 * BrightData credentials stay env-managed only — no API-key UI here.
 */
export default function SettingsModal({ onClose, initial, onSaved }: Props) {
    const { t } = useTranslation();
    const [frequency, setFrequency] = useState<ScrapeFrequency>(initial?.default_scrape_frequency || 'daily');
    const [topN, setTopN] = useState<number>(initial?.default_top_n ?? 50);
    const [budget, setBudget] = useState<number>(initial?.monthly_budget_limit_usd ?? 10);
    const [alert, setAlert] = useState<number>(initial?.alert_threshold_usd ?? 0.05);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // If `initial` arrives asynchronously (parent fetched after first render),
    // rehydrate the form once.
    useEffect(() => {
        if (!initial) return;
        setFrequency(initial.default_scrape_frequency);
        setTopN(initial.default_top_n);
        setBudget(initial.monthly_budget_limit_usd);
        setAlert(initial.alert_threshold_usd);
    }, [initial]);

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError(null);
        try {
            await analyticsFetch<AnalyticsSettings>('/api/analytics/settings', {
                method: 'PUT',
                body: JSON.stringify({
                    default_scrape_frequency: frequency,
                    default_top_n: topN,
                    monthly_budget_limit_usd: budget,
                    alert_threshold_usd: alert,
                }),
                skipProjectScope: true,
            });
            onSaved();
            onClose();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to save settings');
        } finally {
            setSaving(false);
        }
    };

    return (
        <Modal
            title={t('analytics.settings.title')}
            onClose={onClose}
            maxWidth={620}
            footer={
                <>
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={saving}
                        style={{
                            padding: '9px 16px', borderRadius: '8px',
                            border: '1px solid var(--border)', background: 'white',
                            color: 'var(--text-2)', fontSize: '13px', fontWeight: 600,
                            cursor: 'pointer',
                        }}
                    >
                        {t('common.cancel')}
                    </button>
                    <button
                        type="submit"
                        form="settings-form"
                        disabled={saving}
                        style={{
                            padding: '9px 18px', borderRadius: '8px',
                            border: 'none',
                            background: saving ? 'var(--text-3)' : ANALYTICS_CTA_ORANGE,
                            color: 'white', fontSize: '13px', fontWeight: 700,
                            cursor: saving ? 'not-allowed' : 'pointer',
                        }}
                        onMouseEnter={(e) => {
                            if (saving) return;
                            e.currentTarget.style.background = ANALYTICS_CTA_ORANGE_HOVER;
                        }}
                        onMouseLeave={(e) => {
                            if (saving) return;
                            e.currentTarget.style.background = ANALYTICS_CTA_ORANGE;
                        }}
                    >
                        {saving ? t('analytics.settings.saving') : t('analytics.settings.save')}
                    </button>
                </>
            }
        >
            <form id="settings-form" onSubmit={handleSave} style={{ display: 'contents' }}>
                <Group title={t('analytics.settings.defaults.title')}>
                    <Row>
                        <Field label={t('analytics.settings.defaults.frequency')}>
                            <select
                                value={frequency}
                                onChange={(e) => setFrequency(e.target.value as ScrapeFrequency)}
                                disabled={saving}
                                style={selectStyle}
                            >
                                {SCRAPE_FREQUENCY_OPTIONS.map((f) => (
                                    <option key={f} value={f}>
                                        {t(`analytics.frequency.${f}`)}
                                    </option>
                                ))}
                            </select>
                        </Field>
                        <Field label={t('analytics.settings.defaults.topN')}>
                            <input
                                type="number"
                                min={1}
                                max={200}
                                value={topN}
                                onChange={(e) => setTopN(Math.max(1, Math.min(200, parseInt(e.target.value, 10) || 1)))}
                                disabled={saving}
                                style={inputStyle}
                            />
                        </Field>
                    </Row>
                </Group>

                <Group title={t('analytics.settings.cost.title')}>
                    <Row>
                        <Field label={t('analytics.settings.cost.budget')}>
                            <input
                                type="number"
                                min={0}
                                step={0.5}
                                value={budget}
                                onChange={(e) => setBudget(Math.max(0, parseFloat(e.target.value) || 0))}
                                disabled={saving}
                                style={inputStyle}
                            />
                        </Field>
                        <Field label={t('analytics.settings.cost.alertThreshold')}>
                            <input
                                type="number"
                                min={0}
                                step={0.01}
                                value={alert}
                                onChange={(e) => setAlert(Math.max(0, parseFloat(e.target.value) || 0))}
                                disabled={saving}
                                style={inputStyle}
                            />
                        </Field>
                    </Row>
                </Group>

                {error && (
                    <div
                        style={{
                            fontSize: '12px', color: '#FF3B30',
                            background: 'rgba(255,59,48,0.08)',
                            padding: '8px 10px', borderRadius: '8px',
                        }}
                    >
                        {error}
                    </div>
                )}
            </form>
        </Modal>
    );
}

const inputStyle: React.CSSProperties = {
    width: '100%', padding: '10px 12px',
    border: '1px solid var(--border)', borderRadius: '8px',
    fontSize: '13px', color: 'var(--text-1)', background: 'white',
    outline: 'none',
};

const selectStyle: React.CSSProperties = {
    ...inputStyle, fontWeight: 600, cursor: 'pointer',
};

function Group({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <h3 style={{ margin: 0, fontSize: '12px', fontWeight: 700, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                {title}
            </h3>
            {children}
        </section>
    );
}

function Row({ children }: { children: React.ReactNode }) {
    return (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            {children}
        </div>
    );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: 0.4 }}>
                {label}
            </label>
            {children}
        </div>
    );
}
