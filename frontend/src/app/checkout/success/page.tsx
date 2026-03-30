'use client';

import { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { useApp } from '@/providers/AppProvider';
import Link from 'next/link';

function SuccessContent() {
  const { refreshWallet, refreshSubscription } = useApp();
  const searchParams = useSearchParams();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // Give Stripe webhooks a moment to process, then refresh local state
    const timer = setTimeout(() => {
      refreshWallet();
      refreshSubscription();
      setReady(true);
    }, 2500);
    return () => clearTimeout(timer);
  }, [refreshWallet, refreshSubscription]);

  return (
    <div className="content-area" style={{ textAlign: 'center', paddingTop: '4rem' }}>
      <div style={{
        width: '64px', height: '64px', borderRadius: '50%', margin: '0 auto 20px',
        background: 'linear-gradient(135deg, #22c55e, #16a34a)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <svg viewBox="0 0 24 24" style={{ width: 32, height: 32, stroke: 'white', fill: 'none', strokeWidth: 2.5, strokeLinecap: 'round', strokeLinejoin: 'round' }}>
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </div>
      <h1 style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-1)', marginBottom: '8px', letterSpacing: '-0.02em' }}>
        Payment Successful
      </h1>
      <p style={{ fontSize: '14px', color: 'var(--text-3)', marginBottom: '32px', maxWidth: '400px', margin: '0 auto 32px', lineHeight: 1.6 }}>
        {ready
          ? 'Your account has been updated. Credits are ready to use.'
          : 'Processing your payment... This will take just a moment.'}
      </p>
      {!ready && (
        <div style={{ marginBottom: '24px' }}>
          <div style={{ width: '24px', height: '24px', border: '3px solid var(--border)', borderTop: '3px solid var(--blue)', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto' }} />
        </div>
      )}
      <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
        <Link
          href="/manage"
          style={{
            padding: '10px 24px', borderRadius: '8px', fontSize: '13px', fontWeight: 700,
            color: 'var(--text-1)', border: '1.5px solid var(--border)', textDecoration: 'none',
            transition: 'all 0.2s', display: 'inline-flex', alignItems: 'center',
          }}
        >
          View Account
        </Link>
        <Link
          href="/create"
          style={{
            padding: '10px 24px', borderRadius: '8px', fontSize: '13px', fontWeight: 700,
            color: 'white', background: 'linear-gradient(135deg, var(--blue), #667eea)', textDecoration: 'none',
            transition: 'all 0.2s', display: 'inline-flex', alignItems: 'center',
            boxShadow: '0 4px 14px rgba(51,122,255,0.3)',
          }}
        >
          Start Creating
        </Link>
      </div>

      <style jsx>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

export default function CheckoutSuccessPage() {
  return (
    <Suspense fallback={<div className="content-area" style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-3)' }}>Processing...</div>}>
      <SuccessContent />
    </Suspense>
  );
}
