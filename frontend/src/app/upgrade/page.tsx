'use client';

import { useState, useEffect } from 'react';
import { useApp } from '@/providers/AppProvider';
import { apiFetch } from '@/lib/utils';
import Link from 'next/link';

interface Plan {
  id: string;
  name: string;
  price_monthly: number;
  credits_monthly: number;
  is_active: boolean;
  stripe_price_id?: string | null;
}

const PLAN_META: Record<string, { tagline: string; features: string[]; cta: string }> = {
  Starter: {
    tagline: 'Perfect for getting started with AI-generated content.',
    features: ['1,000 Credits/month', 'Generate up to 10 videos/month', '15s & 30s video formats', '3 AI Influencers', 'Auto-burned captions', 'Background music', 'Auto-post to 1 social platform'],
    cta: 'Get Started',
  },
  Creator: {
    tagline: 'For creators and brands that need consistent, high-volume content.',
    features: ['3,000 Credits/month', 'Generate up to 30 videos/month', 'Everything in Starter, plus:', 'Unlock all AI Influencers', 'Physical & Digital Products', 'UGC & Cinematic Product Shots', 'Content calendar & scheduling', 'Auto-post to 3 social platforms', 'Bulk campaign generation'],
    cta: 'Start Free Trial',
  },
  Business: {
    tagline: 'For established businesses scaling their content production.',
    features: ['6,000 Credits/month', 'Generate up to 60 videos/month', 'Everything in Creator, plus:', 'Create Custom AI Influencers', 'Dedicated Support', 'Priority generation queue'],
    cta: 'Contact Sales',
  },
  Agency: {
    tagline: 'For agencies and power users managing multiple brands.',
    features: ['Unlimited videos', 'Everything in Business, plus:', 'Dedicated Account Manager', 'API Access'],
    cta: 'Contact Sales',
  },
};

export default function UpgradePage() {
  const { subscription } = useApp();
  const currentPlan = subscription?.plan?.name || 'Free';
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Plan[]>('/api/plans')
      .then(data => setPlans(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const sortedPlans = [...plans].sort((a, b) => a.price_monthly - b.price_monthly);
  const displayPlans = sortedPlans.filter(p => p.name !== 'Agency');
  const highlightIndex = displayPlans.length >= 2 ? 1 : -1;

  return (
    <div className="content-area">
      <div className="up-header">
        <h1>Choose Your Plan</h1>
        <p>Scale your UGC video production with the right plan for your needs</p>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-3)', fontSize: '14px' }}>Loading plans...</div>
      ) : (
        <div className="up-wrapper">
          <div className="up-grid">
            {displayPlans.map((plan, idx) => {
              const isCurrent = plan.name === currentPlan;
              const isHighlight = idx === highlightIndex;
              const meta = PLAN_META[plan.name] || { tagline: '', features: [], cta: 'Select' };
              const currentPrice = sortedPlans.find(p => p.name === currentPlan)?.price_monthly || 0;

              let ctaText = 'Select';
              if (checkoutLoading === plan.id) {
                ctaText = 'Redirecting...';
              } else if (currentPlan === 'Free' || !currentPlan) {
                ctaText = 'Start Now';
              } else if (plan.price_monthly > currentPrice) {
                ctaText = 'Upgrade Now';
              } else {
                ctaText = 'Downgrade';
              }

              return (
                <div key={plan.id} className={`up-card ${isHighlight ? 'up-card-pop' : ''} ${isCurrent ? 'up-card-current' : ''}`}>
                  {isHighlight && <div className="up-badge">Most Popular</div>}
                  <div className="up-card-inner">
                    <h3>{plan.name}</h3>
                    <div className="up-price">
                      <span className="up-dollar">$</span>{plan.price_monthly}<span className="up-period">/month</span>
                    </div>
                    <p className="up-tagline">{meta.tagline}</p>
                    <ul className="up-features">
                      {meta.features.map(f => {
                        if (f.startsWith('Everything in')) {
                          return (
                            <li key={f} className="up-feature-subheader">
                              <em>{f}</em>
                            </li>
                          );
                        }
                        return (
                          <li key={f}>
                            <svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12" /></svg>
                            {f}
                          </li>
                        );
                      })}
                    </ul>
                    <div className="up-card-footer">
                      {isCurrent ? (
                        <button className="up-btn up-btn-current" disabled>Current Plan</button>
                      ) : !plan.stripe_price_id ? (
                        <button
                          className="up-btn up-btn-outline"
                          onClick={() => window.location.href = 'mailto:max@aitoma.ai?subject=Agency Plan Inquiry'}
                        >
                          Contact Sales
                        </button>
                      ) : (
                        <button
                          className={`up-btn ${isHighlight ? 'up-btn-primary' : 'up-btn-outline'}`}
                          disabled={checkoutLoading === plan.id}
                          onClick={async () => {
                            try {
                              setCheckoutLoading(plan.id);
                              const { checkout_url } = await apiFetch<{ checkout_url: string }>(
                                '/api/stripe/checkout/subscription',
                                { method: 'POST', body: JSON.stringify({ plan_id: plan.id }) }
                              );
                              window.location.href = checkout_url;
                            } catch (err: any) {
                              alert(err.message || 'Failed to start checkout');
                              setCheckoutLoading(null);
                            }
                          }}
                        >
                          {ctaText}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="up-agency-banner">
            <p>
              Are you an Agency looking to create 100+ videos per month?{' '}
              <a href="mailto:max@aitoma.ai?subject=Agency Plan Inquiry">Contact Sales</a>
            </p>
          </div>
        </div>
      )}

      {subscription?.plan?.name && subscription.plan.name !== 'Free' && (
        <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
          <button
            className="up-btn up-btn-outline"
            style={{ maxWidth: '300px', margin: '0 auto' }}
            onClick={async () => {
              try {
                const { portal_url } = await apiFetch<{ portal_url: string }>(
                  '/api/stripe/portal',
                  { method: 'POST' }
                );
                window.location.href = portal_url;
              } catch (err: any) {
                alert(err.message || 'Failed to open billing portal');
              }
            }}
          >
            Manage Billing & Payment Methods
          </button>
        </div>
      )}

      <div style={{ textAlign: 'center', marginTop: '2rem' }}>
        <Link href="/manage" className="up-back">← Back to Account Settings</Link>
      </div>

      <style jsx>{`
        .up-header {
          text-align: center;
          margin-bottom: 40px;
        }
        .up-header h1 {
          font-size: 28px;
          font-weight: 800;
          color: var(--text-1);
          margin-bottom: 8px;
          letter-spacing: -0.02em;
        }
        .up-header p {
          font-size: 15px;
          color: var(--text-3);
        }
        .up-wrapper {
          display: flex;
          flex-direction: column;
          align-items: center;
        }
        .up-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 24px;
          max-width: 960px;
          width: 100%;
          margin: 0 auto;
          align-items: start;
        }
        .up-agency-banner {
          margin-top: 48px;
          padding: 24px 32px;
          background: rgba(51,122,255,0.04);
          border: 1px solid rgba(51,122,255,0.15);
          border-radius: 12px;
          text-align: center;
          max-width: 600px;
          width: 100%;
        }
        .up-agency-banner p {
          margin: 0;
          font-size: 14.5px;
          color: var(--text-2);
          font-weight: 500;
        }
        .up-agency-banner a {
          color: var(--blue);
          font-weight: 700;
          text-decoration: none;
          margin-left: 6px;
        }
        .up-agency-banner a:hover {
          text-decoration: underline;
        }
        /* ── Card ── */
        .up-card {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 16px;
          position: relative;
          transition: transform 0.25s, box-shadow 0.25s;
          box-shadow: var(--shadow);
        }
        .up-card:hover {
          transform: translateY(-3px);
          box-shadow: 0 12px 32px rgba(0,0,0,0.08);
        }
        .up-card-inner {
          padding: 28px 24px;
        }
        /* Popular card — bigger and highlighted */
        .up-card-pop {
          border: 2px solid var(--blue);
          box-shadow: 0 8px 32px rgba(51,122,255,0.15);
          transform: scale(1.04);
          z-index: 2;
        }
        .up-card-pop:hover {
          transform: scale(1.04) translateY(-3px);
          box-shadow: 0 14px 40px rgba(51,122,255,0.2);
        }
        .up-card-pop .up-card-inner {
          padding: 36px 28px;
        }
        .up-card-current {
          border-color: #22c55e;
        }
        .up-badge {
          position: absolute;
          top: -13px;
          left: 50%;
          transform: translateX(-50%);
          background: linear-gradient(135deg, var(--blue), #a78bfa);
          color: white;
          font-size: 11px;
          font-weight: 700;
          padding: 5px 18px;
          border-radius: 20px;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          white-space: nowrap;
        }
        .up-card h3 {
          font-size: 18px;
          font-weight: 700;
          color: var(--text-1);
          margin: 0 0 12px;
        }
        .up-price {
          font-size: 40px;
          font-weight: 800;
          color: var(--text-1);
          letter-spacing: -0.03em;
          line-height: 1;
          margin-bottom: 6px;
        }
        .up-card-pop .up-price {
          font-size: 46px;
        }
        .up-dollar {
          font-size: 22px;
          vertical-align: super;
          font-weight: 700;
          margin-right: 1px;
        }
        .up-period {
          font-size: 14px;
          color: var(--text-3);
          font-weight: 400;
        }
        .up-tagline {
          font-size: 13px;
          color: var(--text-3);
          line-height: 1.5;
          margin: 8px 0 24px;
          min-height: 40px;
        }
        /* ── Features ── */
        .up-features {
          list-style: none;
          padding: 0;
          margin: 0 0 28px;
        }
        .up-features li {
          display: flex;
          align-items: flex-start;
          gap: 10px;
          font-size: 13px;
          font-weight: 500;
          color: var(--text-2);
          padding: 6px 0;
          line-height: 1.4;
        }
        .up-feature-subheader {
          color: var(--text-3) !important;
          font-style: italic;
          margin-top: 6px;
          padding-bottom: 0 !important;
        }
        .up-features svg {
          width: 16px;
          height: 16px;
          stroke: #22c55e;
          fill: none;
          stroke-width: 2.5;
          stroke-linecap: round;
          stroke-linejoin: round;
          flex-shrink: 0;
          margin-top: 1px;
        }
        /* ── Buttons ── */
        .up-card-footer {
          margin-top: auto;
        }
        .up-btn {
          width: 100%;
          padding: 12px;
          border-radius: 10px;
          font-size: 14px;
          font-weight: 700;
          cursor: pointer;
          transition: all 0.2s;
          border: none;
        }
        .up-btn-primary {
          background: linear-gradient(135deg, var(--blue), #667eea);
          color: white;
          box-shadow: 0 4px 14px rgba(51,122,255,0.3);
        }
        .up-btn-primary:hover {
          box-shadow: 0 6px 20px rgba(51,122,255,0.4);
          transform: translateY(-1px);
        }
        .up-btn-outline {
          background: transparent;
          color: var(--text-1);
          border: 1.5px solid var(--border);
        }
        .up-btn-outline:hover {
          border-color: var(--blue);
          color: var(--blue);
          background: rgba(51,122,255,0.04);
        }
        .up-btn-current {
          background: #f0fdf4;
          color: #22c55e;
          border: 1.5px solid #bbf7d0;
          cursor: default;
        }
        .up-btn-current:hover {
          background: #f0fdf4;
          transform: none;
          box-shadow: none;
        }
        .up-back {
          color: var(--text-3);
          font-size: 13px;
          font-weight: 500;
          text-decoration: none;
          transition: color 0.15s;
        }
        .up-back:hover { color: var(--blue); }
      `}</style>
    </div>
  );
}
