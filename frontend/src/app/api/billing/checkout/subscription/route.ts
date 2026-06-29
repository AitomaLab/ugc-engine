import { NextRequest } from 'next/server';
import { POST as proxyBillingPost } from '@/app/api/billing/_proxy';

export async function POST(request: NextRequest) {
  return proxyBillingPost(request, '/api/stripe/checkout/subscription');
}
