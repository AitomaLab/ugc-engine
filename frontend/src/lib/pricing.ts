/** Keep in sync with ugc_backend/credit_cost_service.py CREDIT_COSTS */
export const PRICING_REFERENCE_COSTS = {
  ugcDigital15: 67,
  ugcDigital30: 134,
  cinematicShot: 54,
  clone15: 53,
  physicalUgc15: 101,
  cinematicAdAnimate15: 210,
  cinematicAdStoryboard: 20,
} as const;

export function estimateCount(credits: number, costPerUnit: number): number {
  if (costPerUnit <= 0) return 0;
  return Math.floor(credits / costPerUnit);
}

export function estimateOutputs(credits: number) {
  return {
    ugc: estimateCount(credits, PRICING_REFERENCE_COSTS.ugcDigital15),
    cinematic: estimateCount(credits, PRICING_REFERENCE_COSTS.cinematicShot),
    clone: estimateCount(credits, PRICING_REFERENCE_COSTS.clone15),
  };
}

export function annualSavingsPct(priceMonthly: number, priceYearly: number): number {
  if (!priceMonthly || !priceYearly) return 0;
  const fullYear = priceMonthly * 12;
  if (fullYear <= 0) return 0;
  return Math.round(((fullYear - priceYearly) / fullYear) * 100);
}

export function formatPrice(amount: number): string {
  const rounded = Math.round(amount * 100) / 100;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(2);
}

export function formatCredits(n: number): string {
  return n.toLocaleString('en-US');
}

export function creditsMultiplier(planCredits: number, starterCredits: number): number {
  if (!starterCredits) return 1;
  return Math.round(planCredits / starterCredits);
}

export interface BreakdownRow {
  key: string;
  duration: string;
  credits: number;
}

export const PRICING_BREAKDOWN_ROWS: BreakdownRow[] = [
  { key: 'ugc15', duration: '15s', credits: PRICING_REFERENCE_COSTS.ugcDigital15 },
  { key: 'ugc30', duration: '30s', credits: PRICING_REFERENCE_COSTS.ugcDigital30 },
  { key: 'cinematicShot', duration: 'full', credits: PRICING_REFERENCE_COSTS.cinematicShot },
  { key: 'clone15', duration: '15s', credits: PRICING_REFERENCE_COSTS.clone15 },
  { key: 'physical15', duration: '15s', credits: PRICING_REFERENCE_COSTS.physicalUgc15 },
  { key: 'cinematicAd15', duration: '15s', credits: PRICING_REFERENCE_COSTS.cinematicAdAnimate15 },
  { key: 'cinematicAdSb', duration: 'sheet', credits: PRICING_REFERENCE_COSTS.cinematicAdStoryboard },
];

export type BillingInterval = 'monthly' | 'yearly';

export interface SubscriptionPlan {
  id: string;
  name: string;
  price_monthly: number;
  price_yearly?: number | null;
  credits_monthly: number;
  is_active: boolean;
  stripe_price_id?: string | null;
  stripe_price_id_yearly?: string | null;
}

export function planDisplayPrice(plan: SubscriptionPlan, interval: BillingInterval): number {
  if (interval === 'yearly' && plan.price_yearly) {
    return plan.price_yearly / 12;
  }
  return plan.price_monthly;
}

/** DB has an annual price — show discounted UI */
export function planHasYearlyPrice(plan: SubscriptionPlan): boolean {
  return Boolean(plan.price_yearly && plan.price_yearly > 0);
}

/** Stripe yearly price configured — allow annual checkout */
export function planCanCheckoutYearly(plan: SubscriptionPlan): boolean {
  return Boolean(plan.price_yearly && plan.stripe_price_id_yearly);
}

export function anyPlanHasYearly(plans: SubscriptionPlan[]): boolean {
  return plans.some(planHasYearlyPrice);
}
