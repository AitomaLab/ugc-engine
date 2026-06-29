'use client';

import {
  type BillingInterval,
  type SubscriptionPlan,
  creditsMultiplier,
  estimateOutputs,
  formatCredits,
  formatPrice,
  planCanCheckoutYearly,
  planDisplayPrice,
  planHasYearlyPrice,
} from '@/lib/pricing';

function fill(template: string, vars: Record<string, string | number>) {
  return Object.entries(vars).reduce(
    (s, [k, v]) => s.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v)),
    template,
  );
}

interface PricingPlanCardProps {
  plan: SubscriptionPlan;
  starterCredits: number;
  billingInterval: BillingInterval;
  isHighlight: boolean;
  isCurrent: boolean;
  ctaText: string;
  ctaLoading: boolean;
  onCheckout: () => void;
  onContactSales: () => void;
  t: (key: string) => string;
}

export default function PricingPlanCard({
  plan,
  starterCredits,
  billingInterval,
  isHighlight,
  isCurrent,
  ctaText,
  ctaLoading,
  onCheckout,
  onContactSales,
  t,
}: PricingPlanCardProps) {
  const estimates = estimateOutputs(plan.credits_monthly);
  const multiplier = creditsMultiplier(plan.credits_monthly, starterCredits);
  const isAnnualView = billingInterval === 'yearly';
  const showAnnualPrice = isAnnualView && planHasYearlyPrice(plan);
  const displayPrice = planDisplayPrice(plan, billingInterval);
  const checkoutBlockedAnnual = isAnnualView && !planCanCheckoutYearly(plan);

  const pillSub =
    plan.name === 'Starter'
      ? t('upgrade.creditsFixedAllowance')
      : fill(t('upgrade.creditsMultiplier'), { n: multiplier });

  const featureSectionLabel =
    plan.name === 'Starter'
      ? t('upgrade.features.included')
      : plan.name === 'Creator'
        ? t('upgrade.features.plusStarter')
        : t('upgrade.features.plusCreator');

  const starterFeatures = [
    t('plan.starter.f3'),
    t('plan.starter.f4'),
    t('plan.starter.f5'),
    t('plan.starter.f6'),
    t('plan.starter.f7'),
    t('plan.starter.f8'),
    t('plan.starter.f9'),
  ];

  const tierFeatures: string[] = [];
  if (plan.name === 'Creator') {
    tierFeatures.push(fill(t('upgrade.features.multiplierLine'), { n: multiplier }));
    tierFeatures.push(t('upgrade.features.allStarterIncluded'));
  } else if (plan.name === 'Business') {
    tierFeatures.push(fill(t('upgrade.features.multiplierLine'), { n: multiplier }));
    tierFeatures.push(t('plan.business.f5'));
    tierFeatures.push(t('plan.business.f6'));
    tierFeatures.push(t('upgrade.features.allStarterIncluded'));
  }

  const cardClass = [
    'upgrade-card',
    isHighlight ? 'upgrade-card--popular' : '',
    isCurrent ? 'upgrade-card--current' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={cardClass}>
      {isHighlight && <div className="upgrade-badge">{t('upgrade.mostPopular')}</div>}
      <div className="upgrade-card-body">
        <span className="upgrade-plan-label">{plan.name}</span>
        <div className="upgrade-price-block">
          <div className="upgrade-price-row">
            {showAnnualPrice ? (
              <>
                <span className="upgrade-price-strike">${formatPrice(plan.price_monthly)}</span>
                <span className="upgrade-price">${formatPrice(displayPrice)}</span>
                <span className="upgrade-price-period">{t('upgrade.month')}</span>
              </>
            ) : (
              <>
                <span className="upgrade-price">${formatPrice(displayPrice)}</span>
                <span className="upgrade-price-period">{t('upgrade.month')}</span>
              </>
            )}
          </div>
          {showAnnualPrice && (
            <p className="upgrade-price-billed">{t('upgrade.billedAnnually')}</p>
          )}
        </div>
        <p className="upgrade-tagline">
          {plan.name === 'Starter'
            ? t('plan.starter.tagline')
            : plan.name === 'Creator'
              ? t('plan.creator.tagline')
              : t('plan.business.tagline')}
        </p>

        <div className="upgrade-credit-pill">
          <img
            src="/studio-star-blue.svg"
            alt=""
            aria-hidden="true"
            className="upgrade-credit-icon"
          />
          <div>
            <div className="upgrade-credit-main">
              {fill(t('upgrade.creditsPerMonth'), { count: formatCredits(plan.credits_monthly) })}
            </div>
            <div className="upgrade-credit-sub">{pillSub}</div>
          </div>
        </div>

        <div className="upgrade-estimates">
          <div className="upgrade-estimate-row">
            <strong>{fill(t('upgrade.estimates.ugc'), { count: estimates.ugc })}</strong>
          </div>
          <div className="upgrade-estimate-row">
            <strong>{fill(t('upgrade.estimates.cinematic'), { count: estimates.cinematic })}</strong>
          </div>
          <div className="upgrade-estimate-row">
            <strong>{fill(t('upgrade.estimates.clone'), { count: estimates.clone })}</strong>
            <span className="upgrade-estimate-tip" title={t('upgrade.estimates.tooltip')}>ⓘ</span>
          </div>
        </div>

        <div className="upgrade-feature-label">{featureSectionLabel}</div>
        <ul className="upgrade-features">
          {(plan.name === 'Starter' ? starterFeatures : tierFeatures).map((feature) => {
            const muted = feature === t('upgrade.features.allStarterIncluded');
            return (
              <li key={feature} className={muted ? 'upgrade-feature-muted' : undefined}>
                <svg viewBox="0 0 24 24" aria-hidden="true"><polyline points="20 6 9 17 4 12" /></svg>
                {feature}
              </li>
            );
          })}
        </ul>

        <div className="upgrade-card-footer">
          {isCurrent ? (
            <button type="button" className="upgrade-btn upgrade-btn-current" disabled>
              {t('upgrade.currentPlan')}
            </button>
          ) : !plan.stripe_price_id ? (
            <button type="button" className="upgrade-btn upgrade-btn-outline" onClick={onContactSales}>
              {t('upgrade.contactSales')}
            </button>
          ) : (
            <button
              type="button"
              className={'upgrade-btn ' + (isHighlight ? 'upgrade-btn-primary' : 'upgrade-btn-outline')}
              disabled={ctaLoading || checkoutBlockedAnnual}
              onClick={onCheckout}
            >
              {checkoutBlockedAnnual ? t('upgrade.yearlyUnavailable') : ctaText}
            </button>
          )}
          <p className="upgrade-topup-note">{t('upgrade.topUpNote')}</p>
        </div>
      </div>
    </div>
  );
}
