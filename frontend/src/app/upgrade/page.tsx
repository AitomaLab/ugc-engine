'use client';

import { useState, useEffect, useMemo } from 'react';
import { useApp } from '@/providers/AppProvider';
import { useTranslation } from '@/lib/i18n';
import { apiFetch } from '@/lib/utils';
import Link from 'next/link';
import BillingToggle from '@/components/pricing/BillingToggle';
import PricingPlanCard from '@/components/pricing/PricingPlanCard';
import CreditBreakdownPanel from '@/components/pricing/CreditBreakdownPanel';
import AgencyBar from '@/components/pricing/AgencyBar';
import {
  annualSavingsPct,
  anyPlanHasYearly,
  type BillingInterval,
  type SubscriptionPlan,
} from '@/lib/pricing';

const AGENCY_MAIL = 'mailto:max@aitoma.ai?subject=Agency Plan Inquiry';

export default function UpgradePage() {
  const { subscription } = useApp();
  const { t } = useTranslation();
  const currentPlan = subscription?.plan?.name || 'Free';
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [billingInterval, setBillingInterval] = useState<BillingInterval>('monthly');

  useEffect(() => {
    apiFetch<SubscriptionPlan[]>('/api/plans')
      .then((data) => setPlans(data))
      .catch(() => {})
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

  const currentPrice = sortedPlans.find((p) => p.name === currentPlan)?.price_monthly || 0;

  const handleCheckout = async (plan: SubscriptionPlan) => {
    try {
      setCheckoutLoading(plan.id);
      const { checkout_url } = await apiFetch<{ checkout_url: string }>(
        '/api/stripe/checkout/subscription',
        {
          method: 'POST',
          body: JSON.stringify({ plan_id: plan.id, billing_interval: billingInterval }),
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
    <div className="content-area upgrade-page">
      <div className="upgrade-header">
        <h1>{t('upgrade.title')}</h1>
        <p>{t('upgrade.subtitle')}</p>
        {!loading && yearlyEnabled && (
          <BillingToggle
            interval={billingInterval}
            onChange={setBillingInterval}
            savingsPct={savingsPct}
            monthlyLabel={t('upgrade.billing.monthly')}
            annualLabel={t('upgrade.billing.annual')}
            saveLabel={t('upgrade.billing.save')}
          />
        )}
      </div>

      {loading ? (
        <div className="upgrade-loading">{t('upgrade.loadingPlans')}</div>
      ) : (
        <div className="upgrade-wrapper">
          <div className="upgrade-grid">
            {displayPlans.map((plan, idx) => {
              const isCurrent = plan.name === currentPlan;
              const isHighlight = idx === highlightIndex;

              let ctaText = t('upgrade.select');
              if (checkoutLoading === plan.id) {
                ctaText = t('manage.redirecting');
              } else if (currentPlan === 'Free' || !currentPlan) {
                ctaText = t('upgrade.startNow');
              } else if (plan.price_monthly > currentPrice) {
                ctaText = t('upgrade.upgradeNow');
              } else {
                ctaText = t('upgrade.downgrade');
              }

              return (
                <PricingPlanCard
                  key={plan.id}
                  plan={plan}
                  starterCredits={starterCredits}
                  billingInterval={billingInterval}
                  isHighlight={isHighlight}
                  isCurrent={isCurrent}
                  ctaText={ctaText}
                  ctaLoading={checkoutLoading === plan.id}
                  onCheckout={() => handleCheckout(plan)}
                  onContactSales={() => { window.location.href = AGENCY_MAIL; }}
                  t={t}
                />
              );
            })}
          </div>

          <p className="upgrade-footnote">{t('upgrade.videoEstimateFootnote')}</p>

          <CreditBreakdownPanel
            title={t('upgrade.breakdown.title')}
            colVideoType={t('upgrade.breakdown.colType')}
            colDuration={t('upgrade.breakdown.colDuration')}
            colCredits={t('upgrade.breakdown.colCredits')}
            colPlanGets={t('upgrade.breakdown.colGets').replace('{plan}', starterPlan?.name || 'Starter')}
            referenceCredits={starterCredits}
            t={t}
          />

          <AgencyBar
            title={t('upgrade.agency.title')}
            subtitle={t('upgrade.agency.subtitle')}
            cta={t('upgrade.contactSales')}
            onContact={() => { window.location.href = AGENCY_MAIL; }}
          />
        </div>
      )}

      {subscription?.plan?.name && subscription.plan.name !== 'Free' && (
        <div className="upgrade-manage-wrap">
          <button
            type="button"
            className="upgrade-btn upgrade-btn-outline upgrade-manage-btn"
            onClick={async () => {
              try {
                const { portal_url } = await apiFetch<{ portal_url: string }>(
                  '/api/stripe/portal',
                  { method: 'POST' },
                );
                window.location.href = portal_url;
              } catch (err: unknown) {
                const message = err instanceof Error ? err.message : 'Failed to open billing portal';
                alert(message);
              }
            }}
          >
            {t('upgrade.manageBilling')}
          </button>
        </div>
      )}

      <div className="upgrade-back-wrap">
        <Link href="/manage" className="upgrade-back">{t('upgrade.backToSettings')}</Link>
      </div>
    </div>
  );
}
