'use client';

import { type BillingInterval } from '@/lib/pricing';

interface BillingToggleProps {
  interval: BillingInterval;
  onChange: (interval: BillingInterval) => void;
  savingsPct: number;
  disabled?: boolean;
  monthlyLabel: string;
  annualLabel: string;
  saveLabel: string;
}

export default function BillingToggle({
  interval,
  onChange,
  savingsPct,
  disabled,
  monthlyLabel,
  annualLabel,
  saveLabel,
}: BillingToggleProps) {
  const isAnnual = interval === 'yearly';

  return (
    <div className={'upgrade-billing-toggle' + (disabled ? ' upgrade-billing-toggle--disabled' : '')}>
      <span className={!isAnnual ? 'upgrade-billing-label upgrade-billing-label--active' : 'upgrade-billing-label'}>
        {monthlyLabel}
      </span>
      <button
        type="button"
        className="upgrade-billing-switch"
        role="switch"
        aria-checked={isAnnual}
        disabled={disabled}
        onClick={() => onChange(isAnnual ? 'monthly' : 'yearly')}
      >
        <span className={'upgrade-billing-track' + (isAnnual ? ' upgrade-billing-track--on' : '')}>
          <span className={'upgrade-billing-thumb' + (isAnnual ? ' upgrade-billing-thumb--on' : '')} />
        </span>
      </button>
      <span className={isAnnual ? 'upgrade-billing-label upgrade-billing-label--active' : 'upgrade-billing-label'}>
        {annualLabel}
      </span>
      {savingsPct > 0 && (
        <span className="upgrade-billing-save">{saveLabel.replace('{pct}', String(savingsPct))}</span>
      )}
    </div>
  );
}
