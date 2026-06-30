'use client';

import { useEffect, Suspense } from 'react';
import { useApp } from '@/providers/AppProvider';
import { useTopUp } from '@/providers/TopUpProvider';
import { useTranslation } from '@/lib/i18n';
import { apiFetch } from '@/lib/utils';
import { supabase } from '@/lib/supabaseClient';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useState } from 'react';

const BILLING_PORTAL_URL =
  process.env.NEXT_PUBLIC_STRIPE_BILLING_PORTAL_URL ||
  'https://checkout.aitoma.studio/p/login/9B628r9LS1xa0o63hv0Ny00';

export default function ManagePageWrapper() {
  return (
    <Suspense fallback={<div className="content-area"><p>Loading...</p></div>}>
      <ManagePage />
    </Suspense>
  );
}

function ManagePage() {
  const { profile, subscription, wallet } = useApp();
  const { openTopUp } = useTopUp();
  const { t } = useTranslation();
  const [portalLoading, setPortalLoading] = useState(false);
  const searchParams = useSearchParams();

  useEffect(() => {
    if (searchParams.get('topup') === '1') {
      openTopUp();
      window.history.replaceState({}, '', '/manage');
    }
  }, [searchParams, openTopUp]);

  const planName = subscription?.plan?.name || 'Free';
  const balance = wallet?.balance ?? 0;
  const monthlyCredits = subscription?.plan?.credits_monthly ?? 0;
  const periodEnd = subscription?.current_period_end
    ? new Date(subscription.current_period_end).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
    : '—';

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    window.location.href = '/login';
  };

  const pct = monthlyCredits > 0 ? Math.min(100, (balance / monthlyCredits) * 100) : 0;

  const handleOpenBillingPortal = async () => {
    try {
      setPortalLoading(true);
      const { portal_url } = await apiFetch<{ portal_url: string }>(
        '/api/billing/portal',
        { method: 'POST' },
      );
      window.location.href = portal_url;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : t('manage.billingPortalError');
      alert(message);
      setPortalLoading(false);
    }
  };

  return (
    <div className="content-area" style={{ display: 'block' }}>
      <div className="page-header">
        <h1>{t('manage.title')}</h1>
        <p>{t('manage.subtitle')}</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '16px', maxWidth: '900px', alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '16px 20px', boxShadow: 'var(--shadow)' }}>
            <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-1)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <svg viewBox="0 0 24 24" style={{ width: 16, height: 16, stroke: 'var(--text-3)', fill: 'none', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' }}><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
              {t('manage.account')}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border-soft)' }}>
              <span style={{ fontSize: '13px', color: 'var(--text-3)', width: '140px', flexShrink: 0, fontWeight: 500 }}>{t('profile.email')}</span>
              <span style={{ fontSize: '13px', color: 'var(--text-1)', fontWeight: 500 }}>{profile?.email || '—'}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', padding: '8px 0' }}>
              <span style={{ fontSize: '13px', color: 'var(--text-3)', width: '140px', flexShrink: 0, fontWeight: 500 }}>{t('manage.name')}</span>
              <span style={{ fontSize: '13px', color: 'var(--text-1)', fontWeight: 500, flex: 1 }}>{profile?.name || t('manage.notSet')}</span>
              <Link href="/profile" style={{ fontSize: '12px', color: 'var(--blue)', fontWeight: 600, textDecoration: 'none' }}>{t('manage.edit')}</Link>
            </div>
          </div>

          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '16px 20px', boxShadow: 'var(--shadow)' }}>
            <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-1)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <svg viewBox="0 0 24 24" style={{ width: 16, height: 16, stroke: 'var(--blue)', fill: 'none', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' }}><rect x="1" y="4" width="22" height="16" rx="2" ry="2" /><line x1="1" y1="10" x2="23" y2="10" /></svg>
              {t('manage.subscription')}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--border-soft)' }}>
              <span style={{ fontSize: '13px', color: 'var(--text-3)', width: '140px', flexShrink: 0, fontWeight: 500 }}>{t('manage.currentPlan')}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1 }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', padding: '4px 14px', borderRadius: '20px', fontSize: '11px', fontWeight: 700, background: 'linear-gradient(135deg, rgba(51,122,255,0.1), rgba(99,102,241,0.1))', color: 'var(--blue)', letterSpacing: '0.02em' }}>{planName}</span>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <Link href="/upgrade" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '5px 14px', fontSize: '12px', color: 'var(--blue)', fontWeight: 600, textDecoration: 'none', border: '1px solid rgba(51,122,255,0.2)', borderRadius: '6px', transition: 'all 0.15s', whiteSpace: 'nowrap' }}>{t('manage.changePlan')}</Link>
                <button
                  type="button"
                  onClick={handleOpenBillingPortal}
                  disabled={portalLoading}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '5px 14px', fontSize: '12px', color: 'var(--text-2)', fontWeight: 600, background: 'none', border: '1px solid var(--border)', borderRadius: '6px', cursor: portalLoading ? 'wait' : 'pointer', transition: 'all 0.15s', whiteSpace: 'nowrap', opacity: portalLoading ? 0.7 : 1 }}
                >
                  {portalLoading ? t('manage.billingPortalLoading') : t('manage.manageBilling')}
                </button>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--border-soft)' }}>
              <span style={{ fontSize: '13px', color: 'var(--text-3)', width: '140px', flexShrink: 0, fontWeight: 500 }}>{t('manage.billingPeriodEnds')}</span>
              <span style={{ fontSize: '13px', color: 'var(--text-1)', fontWeight: 600 }}>{periodEnd}</span>
            </div>
            <div style={{ padding: '12px 0 0' }}>
              <p style={{ fontSize: '12px', color: 'var(--text-3)', margin: '0 0 8px', lineHeight: 1.5 }}>{t('manage.billingPortalDesc')}</p>
              <a
                href={BILLING_PORTAL_URL}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: '12px', color: 'var(--blue)', fontWeight: 600, textDecoration: 'none' }}
              >
                {t('manage.billingPortalLink')} ↗
              </a>
            </div>
          </div>

          <div style={{ background: 'var(--surface)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--radius)', padding: '16px 20px', boxShadow: 'var(--shadow)' }}>
            <div style={{ fontSize: '14px', fontWeight: 700, color: '#ef4444', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <svg viewBox="0 0 24 24" style={{ width: 16, height: 16, stroke: '#ef4444', fill: 'none', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' }}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>
              {t('manage.session')}
            </div>
            <p style={{ fontSize: '12px', color: 'var(--text-3)', margin: '0 0 10px', lineHeight: 1.5 }}>{t('manage.sessionDesc')}</p>
            <button
              onClick={handleSignOut}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '7px 16px', background: 'white', color: '#ef4444', border: '1px solid rgba(239,68,68,0.25)', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#fef2f2')}
              onMouseLeave={e => (e.currentTarget.style.background = 'white')}
            >
              {t('manage.signOut')}
            </button>
          </div>
        </div>

        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '20px', boxShadow: 'var(--shadow)' }}>
          <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-1)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <img src="/studio-star-blue.svg" alt="" aria-hidden="true" style={{ width: 16, height: 16, flexShrink: 0 }} />
            {t('manage.credits')}
          </div>
          <div style={{ textAlign: 'center', padding: '8px 0 16px' }}>
            <div style={{ fontSize: '40px', fontWeight: 800, color: 'var(--text-1)', letterSpacing: '-0.03em', lineHeight: 1 }}>{balance.toLocaleString()}</div>
            <div style={{ fontSize: '12px', color: 'var(--text-3)', marginTop: '4px', fontWeight: 500 }}>{t('manage.creditsRemaining')}</div>
            <div style={{ marginTop: '12px', height: '6px', background: 'var(--bg-2)', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${pct}%`, background: 'linear-gradient(90deg, var(--blue), #a78bfa)', borderRadius: '3px', transition: 'width 0.4s ease' }} />
            </div>
          </div>
          <div style={{ borderTop: '1px solid var(--border-soft)', padding: '10px 0 0' }}>
            <div style={{ display: 'flex', alignItems: 'center', padding: '6px 0' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-3)', fontWeight: 500 }}>{t('manage.monthlyAllotment')}</span>
              <span style={{ fontSize: '12px', color: 'var(--text-1)', fontWeight: 600, marginLeft: 'auto' }}>{monthlyCredits.toLocaleString()}/mo</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', padding: '6px 0' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-3)', fontWeight: 500 }}>{t('manage.usage')}</span>
              <span style={{ fontSize: '12px', color: 'var(--text-1)', fontWeight: 600, marginLeft: 'auto' }}>{Math.round(pct)}%</span>
            </div>
          </div>
          <button
            onClick={() => openTopUp()}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', width: '100%', padding: '9px', marginTop: '12px', border: '1.5px solid var(--blue)', color: 'var(--blue)', background: 'transparent', borderRadius: '8px', fontSize: '12px', fontWeight: 700, cursor: 'pointer', transition: 'all 0.2s', boxSizing: 'border-box' }}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--blue)'; e.currentTarget.style.color = 'white'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--blue)'; }}
          >
            <svg viewBox="0 0 24 24" style={{ width: 14, height: 14, stroke: 'currentColor', fill: 'none', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }}><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
            {t('manage.topUpCredits')}
          </button>
        </div>
      </div>
    </div>
  );
}
