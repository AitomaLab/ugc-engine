'use client';

import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import { apiFetch } from '@/lib/utils';
import BillingToggle from '@/components/pricing/BillingToggle';
import PricingPlanCard from '@/components/pricing/PricingPlanCard';
import {
  annualSavingsPct,
  anyPlanHasYearly,
  type BillingInterval,
  type SubscriptionPlan,
} from '@/lib/pricing';

interface SubscribeGateProps {
  confirmingPayment?: boolean;
  confirmTimedOut?: boolean;
}

function GateLangToggle() {
  const { lang, setLang } = useTranslation();
  return (
    <button
      type="button"
      onClick={() => setLang(lang === 'en' ? 'es' : 'en')}
      title={lang === 'en' ? 'Switch to Spanish' : 'Cambiar a Inglés'}
      style={{
        position: 'absolute',
        top: 24,
        right: 24,
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        padding: '4px 8px',
        borderRadius: 6,
        border: '1px solid #E5E9F2',
        background: '#FFFFFF',
        cursor: 'pointer',
        fontSize: 12,
        fontWeight: 600,
        color: '#64748B',
        transition: 'all 0.15s ease',
        whiteSpace: 'nowrap' as const,
        zIndex: 1,
      }}
    >
      <span
        style={{
          padding: '2px 6px',
          borderRadius: 4,
          background: lang === 'en' ? '#337AFF' : 'transparent',
          color: lang === 'en' ? '#fff' : '#94A3B8',
          fontWeight: lang === 'en' ? 700 : 500,
        }}
      >
        EN
      </span>
      <span
        style={{
          padding: '2px 6px',
          borderRadius: 4,
          background: lang === 'es' ? '#337AFF' : 'transparent',
          color: lang === 'es' ? '#fff' : '#94A3B8',
          fontWeight: lang === 'es' ? 700 : 500,
        }}
      >
        ES
      </span>
    </button>
  );
}

export function SubscribeGate({ confirmingPayment = false, confirmTimedOut = false }: SubscribeGateProps) {
  const { t } = useTranslation();
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [billingInterval, setBillingInterval] = useState<BillingInterval>('monthly');

  useEffect(() => {
    apiFetch<SubscriptionPlan[]>('/api/plans')
      .then((data) => setPlans(Array.isArray(data) ? data : []))
      .catch(() => setPlans([]))
      .finally(() => setLoading(false));
  }, []);

  const sortedPlans = useMemo(
    () => [...plans].sort((a, b) => a.price_monthly - b.price_monthly),
    [plans],
  );
  const displayPlans = sortedPlans.filter((p) => p.name !== 'Agency');
  const highlightIndex = displayPlans.length >= 2 ? 1 : -1;
  const starterPlan = displayPlans.find((p) => p.name === 'Starter') || displayPlans[0];
  const starterCredits = starterPlan?.credits_monthly ?? 1000;
  const yearlyEnabled = anyPlanHasYearly(displayPlans);
  const savingsPct = starterPlan
    ? annualSavingsPct(starterPlan.price_monthly, starterPlan.price_yearly || 0)
    : 0;

  const handleCheckout = async (plan: SubscriptionPlan) => {
    try {
      setCheckoutLoading(plan.id);
      const { checkout_url } = await apiFetch<{ checkout_url: string }>(
        '/api/billing/checkout/subscription',
        {
          method: 'POST',
          body: JSON.stringify({
            plan_id: plan.id,
            billing_interval: billingInterval,
            flow: 'onboarding',
          }),
        },
      );
      window.location.href = checkout_url;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to start checkout';
      alert(message);
      setCheckoutLoading(null);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'var(--bg-app, #f7f8fa)',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '32px 24px 48px',
      }}
    >
      <GateLangToggle />

      {confirmingPayment && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 10000,
            background: 'rgba(247, 248, 250, 0.92)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 16,
            padding: 24,
          }}
        >
          <div
            style={{
              width: 32,
              height: 32,
              border: '3px solid #E5E9F2',
              borderTopColor: '#337AFF',
              borderRadius: '50%',
              animation: 'subscribeGateSpin 0.8s linear infinite',
            }}
          />
          <p style={{ margin: 0, fontSize: 15, fontWeight: 600, color: '#0D1B3E', textAlign: 'center' }}>
            {t('onboarding.subscribe.confirming')}
          </p>
        </div>
      )}

      <header style={{ textAlign: 'center', marginBottom: 24, flexShrink: 0, maxWidth: 560 }}>
        <img
          src="/StudioLogo_Black.svg"
          alt="Aitoma Studio"
          style={{ width: 130, height: 'auto', objectFit: 'contain' }}
        />
        <h1
          style={{
            margin: '20px 0 8px',
            fontSize: 22,
            fontWeight: 700,
            color: '#0D1B3E',
            lineHeight: 1.35,
          }}
        >
          {t('onboarding.subscribe.title')}
        </h1>
        <p style={{ margin: 0, fontSize: 14, color: '#8A93B0', lineHeight: 1.5 }}>
          {t('onboarding.subscribe.subtitle')}
        </p>
        {confirmTimedOut && (
          <p style={{ margin: '12px 0 0', fontSize: 13, color: '#B91C1C', lineHeight: 1.5 }}>
            {t('onboarding.subscribe.confirmTimeout')}
          </p>
        )}
      </header>

      {!loading && yearlyEnabled && (
        <div style={{ marginBottom: 20 }}>
          <BillingToggle
            interval={billingInterval}
            onChange={setBillingInterval}
            savingsPct={savingsPct}
            monthlyLabel={t('upgrade.billing.monthly')}
            annualLabel={t('upgrade.billing.annual')}
            saveLabel={t('upgrade.billing.save')}
          />
        </div>
      )}

      {loading ? (
        <p style={{ color: '#94A3B8', fontSize: 14 }}>{t('upgrade.loadingPlans')}</p>
      ) : (
        <div
          style={{
            width: '100%',
            maxWidth: 960,
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: 16,
          }}
        >
          {displayPlans.map((plan, idx) => (
            <PricingPlanCard
              key={plan.id}
              plan={plan}
              starterCredits={starterCredits}
              billingInterval={billingInterval}
              isHighlight={idx === highlightIndex}
              isCurrent={false}
              ctaText={
                checkoutLoading === plan.id ? t('manage.redirecting') : t('onboarding.subscribe.choosePlan')
              }
              ctaLoading={checkoutLoading === plan.id}
              onCheckout={() => handleCheckout(plan)}
              onContactSales={() => {}}
              t={t}
            />
          ))}
        </div>
      )}

      <style jsx global>{`
        @keyframes subscribeGateSpin {
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </div>
  );
}
