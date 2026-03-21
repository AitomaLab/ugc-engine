/**
 * UGC Engine SaaS — TypeScript Types for the SaaS layer
 */

/** User profile from public.profiles */
export interface UserProfile {
  id: string;
  name: string | null;
  email: string;
  avatar_url: string | null;
  created_at?: string;
  updated_at?: string;
}

/** Subscription with joined plan data */
export interface Subscription {
  id: string;
  user_id: string;
  plan_id: string;
  status: 'active' | 'past_due' | 'canceled';
  current_period_start: string;
  current_period_end: string;
  plan: {
    name: string;
    credits_monthly: number;
    price_monthly: number;
  };
}

/** Credit wallet */
export interface CreditWallet {
  id: string;
  user_id: string;
  balance: number;
  updated_at?: string;
}

/** Credit transaction from the ledger */
export interface CreditTransaction {
  id: string;
  wallet_id: string;
  amount: number;
  type: 'monthly_allotment' | 'top_up' | 'generation_deduction' | 'refund' | 'admin_adjustment';
  description: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

/** Project container */
export interface Project {
  id: string;
  user_id: string;
  name: string;
  is_default: boolean;
  created_at?: string;
  updated_at?: string;
}

/** Credit cost table */
export interface CreditCosts {
  digital_15s: number;
  digital_30s: number;
  physical_15s: number;
  physical_30s: number;
  cinematic_image_1k: number;
  cinematic_image_2k: number;
  cinematic_image_4k: number;
  cinematic_video_8s: number;
}
