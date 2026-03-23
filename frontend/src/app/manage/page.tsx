'use client';

import { useState, useEffect, Suspense } from 'react';
import { useApp } from '@/providers/AppProvider';
import { supabase } from '@/lib/supabaseClient';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';

const CREDIT_PACKAGES = [
  { name: 'Small Top-Up',  credits: 250,  price: 9,   perCredit: '3.6¢' },
  { name: 'Medium Top-Up', credits: 750,  price: 24,  perCredit: '3.2¢', popular: true },
  { name: 'Large Top-Up',  credits: 2000, price: 59,  perCredit: '2.9¢' },
  { name: 'XL Top-Up',     credits: 5000, price: 139, perCredit: '2.8¢' },
];

export default function ManagePageWrapper() {
  return (
    <Suspense fallback={<div className="content-area"><p>Loading...</p></div>}>
      <ManagePage />
    </Suspense>
  );
}

function ManagePage() {
  const { profile, subscription, wallet } = useApp();
  const [topUpOpen, setTopUpOpen] = useState(false);
  const searchParams = useSearchParams();

  // Auto-open modal when arriving from profile dropdown (?topup=1)
  useEffect(() => {
    if (searchParams.get('topup') === '1') {
      setTopUpOpen(true);
      // Clean URL without reload
      window.history.replaceState({}, '', '/manage');
    }
  }, [searchParams]);

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

  return (
    <div className="content-area" style={{ display: 'block' }}>
      <div className="page-header">
        <h1>Account Settings</h1>
        <p>Manage your subscription, credits, and preferences</p>
      </div>

      {/* Two-column layout: left info cards, right credits */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '16px', maxWidth: '900px', alignItems: 'start' }}>
        {/* Left column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Account */}
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '16px 20px', boxShadow: 'var(--shadow)' }}>
            <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-1)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <svg viewBox="0 0 24 24" style={{ width: 16, height: 16, stroke: 'var(--text-3)', fill: 'none', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' }}><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
              Account
            </div>
            <div style={{ display: 'flex', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border-soft)' }}>
              <span style={{ fontSize: '13px', color: 'var(--text-3)', width: '140px', flexShrink: 0, fontWeight: 500 }}>Email</span>
              <span style={{ fontSize: '13px', color: 'var(--text-1)', fontWeight: 500 }}>{profile?.email || '—'}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', padding: '8px 0' }}>
              <span style={{ fontSize: '13px', color: 'var(--text-3)', width: '140px', flexShrink: 0, fontWeight: 500 }}>Name</span>
              <span style={{ fontSize: '13px', color: 'var(--text-1)', fontWeight: 500, flex: 1 }}>{profile?.name || 'Not set'}</span>
              <Link href="/profile" style={{ fontSize: '12px', color: 'var(--blue)', fontWeight: 600, textDecoration: 'none' }}>Edit</Link>
            </div>
          </div>

          {/* Subscription */}
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '16px 20px', boxShadow: 'var(--shadow)' }}>
            <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-1)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <svg viewBox="0 0 24 24" style={{ width: 16, height: 16, stroke: 'var(--blue)', fill: 'none', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' }}><rect x="1" y="4" width="22" height="16" rx="2" ry="2" /><line x1="1" y1="10" x2="23" y2="10" /></svg>
              Subscription
            </div>
            <div style={{ display: 'flex', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--border-soft)' }}>
              <span style={{ fontSize: '13px', color: 'var(--text-3)', width: '140px', flexShrink: 0, fontWeight: 500 }}>Current Plan</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1 }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', padding: '4px 14px', borderRadius: '20px', fontSize: '11px', fontWeight: 700, background: 'linear-gradient(135deg, rgba(51,122,255,0.1), rgba(99,102,241,0.1))', color: 'var(--blue)', letterSpacing: '0.02em' }}>{planName}</span>
              </div>
              <Link href="/upgrade" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '5px 14px', fontSize: '12px', color: 'var(--blue)', fontWeight: 600, textDecoration: 'none', border: '1px solid rgba(51,122,255,0.2)', borderRadius: '6px', transition: 'all 0.15s', whiteSpace: 'nowrap' }}>Change Plan</Link>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', padding: '10px 0' }}>
              <span style={{ fontSize: '13px', color: 'var(--text-3)', width: '140px', flexShrink: 0, fontWeight: 500 }}>Billing Period Ends</span>
              <span style={{ fontSize: '13px', color: 'var(--text-1)', fontWeight: 600 }}>{periodEnd}</span>
            </div>
          </div>

          {/* Session */}
          <div style={{ background: 'var(--surface)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--radius)', padding: '16px 20px', boxShadow: 'var(--shadow)' }}>
            <div style={{ fontSize: '14px', fontWeight: 700, color: '#ef4444', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <svg viewBox="0 0 24 24" style={{ width: 16, height: 16, stroke: '#ef4444', fill: 'none', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' }}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>
              Session
            </div>
            <p style={{ fontSize: '12px', color: 'var(--text-3)', margin: '0 0 10px', lineHeight: 1.5 }}>Sign out of your current session on this device.</p>
            <button
              onClick={handleSignOut}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '7px 16px', background: 'white', color: '#ef4444', border: '1px solid rgba(239,68,68,0.25)', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#fef2f2')}
              onMouseLeave={e => (e.currentTarget.style.background = 'white')}
            >
              Sign Out
            </button>
          </div>
        </div>

        {/* Right column — Credits widget */}
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '20px', boxShadow: 'var(--shadow)' }}>
          <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-1)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <svg viewBox="0 0 24 24" style={{ width: 16, height: 16, stroke: '#22c55e', fill: 'none', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' }}><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>
            Credits
          </div>
          <div style={{ textAlign: 'center', padding: '8px 0 16px' }}>
            <div style={{ fontSize: '40px', fontWeight: 800, color: 'var(--text-1)', letterSpacing: '-0.03em', lineHeight: 1 }}>{balance.toLocaleString()}</div>
            <div style={{ fontSize: '12px', color: 'var(--text-3)', marginTop: '4px', fontWeight: 500 }}>credits remaining</div>
            <div style={{ marginTop: '12px', height: '6px', background: 'var(--bg-2)', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${pct}%`, background: 'linear-gradient(90deg, var(--blue), #a78bfa)', borderRadius: '3px', transition: 'width 0.4s ease' }} />
            </div>
          </div>
          <div style={{ borderTop: '1px solid var(--border-soft)', padding: '10px 0 0' }}>
            <div style={{ display: 'flex', alignItems: 'center', padding: '6px 0' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-3)', fontWeight: 500 }}>Monthly Allotment</span>
              <span style={{ fontSize: '12px', color: 'var(--text-1)', fontWeight: 600, marginLeft: 'auto' }}>{monthlyCredits.toLocaleString()}/mo</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', padding: '6px 0' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-3)', fontWeight: 500 }}>Usage</span>
              <span style={{ fontSize: '12px', color: 'var(--text-1)', fontWeight: 600, marginLeft: 'auto' }}>{Math.round(pct)}%</span>
            </div>
          </div>
          <button
            onClick={() => setTopUpOpen(true)}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', width: '100%', padding: '9px', marginTop: '12px', border: '1.5px solid var(--blue)', color: 'var(--blue)', background: 'transparent', borderRadius: '8px', fontSize: '12px', fontWeight: 700, cursor: 'pointer', transition: 'all 0.2s', boxSizing: 'border-box' }}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--blue)'; e.currentTarget.style.color = 'white'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--blue)'; }}
          >
            <svg viewBox="0 0 24 24" style={{ width: 14, height: 14, stroke: 'currentColor', fill: 'none', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }}><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
            Top Up Credits
          </button>
        </div>
      </div>

      {/* ═══ TOP UP CREDITS MODAL ═══ */}
      {topUpOpen && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(4px)' }}
          onClick={() => setTopUpOpen(false)}
        >
          <div
            style={{ background: 'var(--surface)', borderRadius: '16px', width: '100%', maxWidth: '820px', padding: '32px', boxShadow: '0 20px 60px rgba(0,0,0,0.2)', position: 'relative', animation: 'fadeInUp 0.2s ease' }}
            onClick={e => e.stopPropagation()}
          >
            {/* Close button */}
            <button
              onClick={() => setTopUpOpen(false)}
              style={{ position: 'absolute', top: '16px', right: '16px', background: 'none', border: 'none', cursor: 'pointer', padding: '4px', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            >
              <svg viewBox="0 0 24 24" style={{ width: 20, height: 20, stroke: 'var(--text-3)', fill: 'none', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }}><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
            </button>

            {/* Header */}
            <div style={{ textAlign: 'center', marginBottom: '28px' }}>
              <h2 style={{ fontSize: '22px', fontWeight: 800, color: 'var(--text-1)', margin: '0 0 6px', letterSpacing: '-0.02em' }}>Top Up Credits</h2>
              <p style={{ fontSize: '13px', color: 'var(--text-2)', margin: 0 }}>Buy extra credits instantly — added to your current balance</p>
            </div>

            {/* Package grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px' }}>
              {CREDIT_PACKAGES.map((pkg) => (
                <div
                  key={pkg.name}
                  style={{
                    background: 'var(--surface)',
                    border: pkg.popular ? '2px solid var(--blue)' : '1px solid var(--border)',
                    borderRadius: '14px',
                    padding: pkg.popular ? '24px 18px' : '22px 16px',
                    display: 'flex',
                    flexDirection: 'column',
                    position: 'relative',
                    transition: 'transform 0.2s, box-shadow 0.2s',
                    boxShadow: pkg.popular ? '0 6px 24px rgba(51,122,255,0.12)' : 'var(--shadow)',
                    transform: pkg.popular ? 'scale(1.03)' : 'none',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.transform = pkg.popular ? 'scale(1.03) translateY(-2px)' : 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 8px 28px rgba(0,0,0,0.1)'; }}
                  onMouseLeave={e => { e.currentTarget.style.transform = pkg.popular ? 'scale(1.03)' : 'none'; e.currentTarget.style.boxShadow = pkg.popular ? '0 6px 24px rgba(51,122,255,0.12)' : 'var(--shadow)'; }}
                >
                  {/* Popular badge */}
                  {pkg.popular && (
                    <div style={{ position: 'absolute', top: '-11px', left: '50%', transform: 'translateX(-50%)', background: 'linear-gradient(135deg, var(--blue), #a78bfa)', color: 'white', fontSize: '10px', fontWeight: 700, padding: '3px 14px', borderRadius: '20px', textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>
                      Best Value
                    </div>
                  )}

                  {/* Package name */}
                  <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-1)', marginBottom: '12px' }}>{pkg.name}</div>

                  {/* Price */}
                  <div style={{ fontSize: '32px', fontWeight: 800, color: 'var(--text-1)', letterSpacing: '-0.03em', lineHeight: 1, marginBottom: '4px' }}>
                    <span style={{ fontSize: '16px', verticalAlign: 'super', fontWeight: 700 }}>$</span>{pkg.price}
                  </div>

                  {/* Credits */}
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--blue)', marginBottom: '4px' }}>{pkg.credits.toLocaleString()} credits</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-2)', marginBottom: '18px' }}>{pkg.perCredit}/credit</div>

                  {/* Buy button */}
                  <button
                    onClick={() => alert(`Purchase ${pkg.name} ($${pkg.price}) — coming soon!`)}
                    style={{
                      width: '100%',
                      padding: '10px',
                      borderRadius: '8px',
                      fontSize: '13px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      border: 'none',
                      marginTop: 'auto',
                      background: pkg.popular ? 'linear-gradient(135deg, var(--blue), #667eea)' : 'transparent',
                      color: pkg.popular ? 'white' : 'var(--text-1)',
                      ...(pkg.popular ? {} : { border: '1.5px solid var(--border)' }),
                      boxShadow: pkg.popular ? '0 4px 12px rgba(51,122,255,0.25)' : 'none',
                    }}
                    onMouseEnter={e => {
                      if (!pkg.popular) { e.currentTarget.style.borderColor = 'var(--blue)'; e.currentTarget.style.color = 'var(--blue)'; }
                      else { e.currentTarget.style.boxShadow = '0 6px 18px rgba(51,122,255,0.35)'; }
                    }}
                    onMouseLeave={e => {
                      if (!pkg.popular) { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-1)'; }
                      else { e.currentTarget.style.boxShadow = '0 4px 12px rgba(51,122,255,0.25)'; }
                    }}
                  >
                    Buy Now
                  </button>
                </div>
              ))}
            </div>

            {/* Footer note */}
            <div style={{ textAlign: 'center', marginTop: '20px', fontSize: '12px', color: '#6b7280' }}>
              Credits are added instantly and never expire. Valid on all plans.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
