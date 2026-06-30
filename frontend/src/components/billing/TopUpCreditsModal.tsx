'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useTranslation } from '@/lib/i18n';
import { apiFetch } from '@/lib/utils';

export const CREDIT_PACKAGES = [
  { name: 'Small Top-Up', credits: 250, price: 9, perCredit: '3.6¢' },
  { name: 'Medium Top-Up', credits: 700, price: 24, perCredit: '3.4¢', popular: true },
  { name: 'Large Top-Up', credits: 2000, price: 59, perCredit: '3.0¢' },
  { name: 'XL Top-Up', credits: 5000, price: 139, perCredit: '2.8¢' },
] as const;

interface TopUpCreditsModalProps {
  open: boolean;
  onClose: () => void;
  notice?: string;
}

export function TopUpCreditsModal({ open, onClose, notice }: TopUpCreditsModalProps) {
  const { t } = useTranslation();
  const [topUpLoading, setTopUpLoading] = useState<string | null>(null);

  if (!open) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.45)',
        backdropFilter: 'blur(4px)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#FFFFFF',
          borderRadius: '16px',
          width: '100%',
          maxWidth: '820px',
          padding: '32px',
          boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
          position: 'relative',
          animation: 'fadeInUp 0.2s ease',
          border: '1px solid var(--border)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '16px',
            right: '16px',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '4px',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <svg viewBox="0 0 24 24" style={{ width: 20, height: 20, stroke: 'var(--text-3)', fill: 'none', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }}>
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>

        {notice && (
          <div
            style={{
              marginBottom: '20px',
              padding: '12px 16px',
              borderRadius: '10px',
              background: 'rgba(245, 158, 11, 0.12)',
              border: '1px solid rgba(245, 158, 11, 0.35)',
              fontSize: '13px',
              lineHeight: 1.5,
              color: 'var(--text-1)',
              textAlign: 'center',
            }}
          >
            {notice}
          </div>
        )}

        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <h2 style={{ fontSize: '22px', fontWeight: 800, color: 'var(--text-1)', margin: '0 0 6px', letterSpacing: '-0.02em' }}>
            {t('manage.topUpTitle')}
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-2)', margin: 0 }}>{t('manage.topUpDesc')}</p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px' }}>
          {CREDIT_PACKAGES.map((pkg) => {
            const isPopular = 'popular' in pkg && pkg.popular;
            return (
            <div
              key={pkg.name}
              style={{
                background: '#FFFFFF',
                border: isPopular ? '2px solid var(--blue)' : '1px solid var(--border)',
                borderRadius: '14px',
                padding: isPopular ? '24px 18px' : '22px 16px',
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
                transition: 'transform 0.2s, box-shadow 0.2s',
                boxShadow: isPopular ? '0 6px 24px rgba(51,122,255,0.12)' : 'var(--shadow)',
                transform: isPopular ? 'scale(1.03)' : 'none',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = isPopular ? 'scale(1.03) translateY(-2px)' : 'translateY(-2px)';
                e.currentTarget.style.boxShadow = '0 8px 28px rgba(0,0,0,0.1)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = isPopular ? 'scale(1.03)' : 'none';
                e.currentTarget.style.boxShadow = isPopular ? '0 6px 24px rgba(51,122,255,0.12)' : 'var(--shadow)';
              }}
            >
              {isPopular && (
                <div
                  style={{
                    position: 'absolute',
                    top: '-11px',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    background: 'linear-gradient(135deg, var(--blue), #a78bfa)',
                    color: 'white',
                    fontSize: '10px',
                    fontWeight: 700,
                    padding: '3px 14px',
                    borderRadius: '20px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {t('manage.bestValue')}
                </div>
              )}

              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-1)', marginBottom: '12px' }}>{pkg.name}</div>

              <div style={{ fontSize: '32px', fontWeight: 800, color: 'var(--text-1)', letterSpacing: '-0.03em', lineHeight: 1, marginBottom: '4px' }}>
                <span style={{ fontSize: '16px', verticalAlign: 'super', fontWeight: 700 }}>$</span>
                {pkg.price}
              </div>

              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--blue)', marginBottom: '4px' }}>
                {pkg.credits.toLocaleString()} {t('manage.credits_unit')}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-2)', marginBottom: '18px' }}>{pkg.perCredit}/credit</div>

              <button
                type="button"
                disabled={topUpLoading === pkg.name}
                onClick={async () => {
                  try {
                    setTopUpLoading(pkg.name);
                    const packageKey = pkg.name.split(' ')[0].toLowerCase();
                    const { checkout_url } = await apiFetch<{ checkout_url: string }>(
                      '/api/billing/checkout/topup',
                      { method: 'POST', body: JSON.stringify({ package: packageKey }) },
                    );
                    window.location.href = checkout_url;
                  } catch (err: unknown) {
                    alert(err instanceof Error ? err.message : 'Failed to start checkout');
                    setTopUpLoading(null);
                  }
                }}
                style={{
                  width: '100%',
                  padding: '10px',
                  borderRadius: '8px',
                  fontSize: '13px',
                  fontWeight: 700,
                  cursor: topUpLoading === pkg.name ? 'wait' : 'pointer',
                  transition: 'all 0.2s',
                  border: 'none',
                  marginTop: 'auto',
                  background: isPopular ? 'linear-gradient(135deg, var(--blue), #667eea)' : 'transparent',
                  color: isPopular ? 'white' : 'var(--text-1)',
                  ...(!isPopular ? { border: '1.5px solid var(--border)' } : {}),
                  boxShadow: isPopular ? '0 4px 12px rgba(51,122,255,0.25)' : 'none',
                  opacity: topUpLoading === pkg.name ? 0.7 : 1,
                }}
                onMouseEnter={(e) => {
                  if (!isPopular) {
                    e.currentTarget.style.borderColor = 'var(--blue)';
                    e.currentTarget.style.color = 'var(--blue)';
                  } else {
                    e.currentTarget.style.boxShadow = '0 6px 18px rgba(51,122,255,0.35)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isPopular) {
                    e.currentTarget.style.borderColor = 'var(--border)';
                    e.currentTarget.style.color = 'var(--text-1)';
                  } else {
                    e.currentTarget.style.boxShadow = '0 4px 12px rgba(51,122,255,0.25)';
                  }
                }}
              >
                {topUpLoading === pkg.name ? t('manage.redirecting') : t('manage.buyNow')}
              </button>
            </div>
            );
          })}
        </div>

        <div style={{ textAlign: 'center', marginTop: '20px', fontSize: '12px', color: 'var(--text-2)' }}>
          {t('manage.topUpFooter')}
        </div>

        <div style={{ textAlign: 'center', marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border-soft)' }}>
          <p style={{ margin: '0 0 8px', fontSize: '12px', color: 'var(--text-3)' }}>
            {t('manage.topUpUpgradeHint')}
          </p>
          <Link
            href="/upgrade"
            onClick={onClose}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '13px',
              fontWeight: 600,
              color: 'var(--blue)',
              textDecoration: 'none',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.textDecoration = 'underline'; }}
            onMouseLeave={(e) => { e.currentTarget.style.textDecoration = 'none'; }}
          >
            {t('manage.topUpUpgradeCta')} →
          </Link>
        </div>
      </div>
    </div>
  );
}
