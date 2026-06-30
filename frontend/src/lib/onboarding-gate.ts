import type { Subscription } from '@/lib/saas-types';

/** Beta: require Stripe subscription before ICP onboarding. */
export const REQUIRE_PAID_PLAN = process.env.NEXT_PUBLIC_REQUIRE_PAID_PLAN === 'true';

export function hasActivePaidPlan(sub: Subscription | null | undefined): boolean {
  if (!sub?.id) return false;
  return sub.status === 'active';
}
