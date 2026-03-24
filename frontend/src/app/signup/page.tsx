'use client';

import { useState } from 'react';
import { supabase } from '@/lib/supabaseClient';
import Link from 'next/link';

export default function SignupPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { name },
      },
    });

    if (error) {
      setError(error.message);
      setLoading(false);
    } else {
      setSuccess(true);
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <div className="auth-header">
            <img src="/StudioLogo_Black.svg" alt="Aitoma Studio" style={{ height: '36px' }} />
            <h1>Check your email</h1>
            <p>We sent a confirmation link to <strong>{email}</strong>. Click it to activate your account.</p>
          </div>
          <div className="auth-footer">
            Already confirmed? <Link href="/login">Sign In</Link>
          </div>
        </div>
        <style jsx>{`
          .auth-page { display: flex; align-items: center; justify-content: center; min-height: 100vh; background: var(--bg-app, #f7f8fa); padding: 2rem; }
          .auth-card { background: white; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); padding: 2.5rem; width: 100%; max-width: 420px; }
          .auth-header { text-align: center; margin-bottom: 1rem; }
          .auth-header h1 { font-size: 1.5rem; font-weight: 700; margin: 1rem 0 0.5rem; color: #1a1a2e; }
          .auth-header p { color: #6b7280; font-size: 0.9rem; line-height: 1.5; }
          .auth-footer { text-align: center; margin-top: 1.5rem; color: #6b7280; font-size: 0.9rem; }
          .auth-footer a { color: #6366f1; font-weight: 600; text-decoration: none; }
        `}</style>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <img src="/StudioLogo_Black.svg" alt="Aitoma Studio" style={{ height: '36px' }} />
          <h1>Create your account</h1>
          <p>Start generating UGC videos today</p>
        </div>

        <form onSubmit={handleSignup} className="auth-form">
          {error && <div className="auth-error">{error}</div>}

          <div className="auth-field">
            <label htmlFor="name">Full Name</label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Your name"
            />
          </div>

          <div className="auth-field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </div>

          <div className="auth-field">
            <label htmlFor="password">Password</label>
            <div className="password-wrapper">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Minimum 6 characters"
                minLength={6}
                required
              />
              <button type="button" className="pw-toggle" onClick={() => setShowPassword(v => !v)} tabIndex={-1}>
                {showPassword ? (
                  <svg viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" /><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" /><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" /><line x1="1" y1="1" x2="23" y2="23" /></svg>
                ) : (
                  <svg viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>
                )}
              </button>
            </div>
          </div>

          <button type="submit" className="auth-submit" disabled={loading}>
            {loading ? 'Creating account...' : 'Create Account'}
          </button>
        </form>

        <div className="auth-footer">
          Already have an account? <Link href="/login">Sign In</Link>
        </div>
      </div>

      <style jsx>{`
        .auth-page { display: flex; align-items: center; justify-content: center; min-height: 100vh; background: var(--bg-app, #f7f8fa); padding: 2rem; }
        .auth-card { background: white; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); padding: 2.5rem; width: 100%; max-width: 420px; }
        .auth-header { text-align: center; margin-bottom: 2rem; }
        .auth-header h1 { font-size: 1.5rem; font-weight: 700; margin: 1rem 0 0.25rem; color: #1a1a2e; }
        .auth-header p { color: #6b7280; font-size: 0.9rem; }
        .auth-form { display: flex; flex-direction: column; gap: 1rem; }
        .auth-field label { display: block; font-size: 0.85rem; font-weight: 500; color: #374151; margin-bottom: 0.35rem; }
        .auth-field input { width: 100%; padding: 0.65rem 0.85rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.95rem; outline: none; transition: border-color 0.2s; box-sizing: border-box; }
        .auth-field input:focus { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1); }
        .password-wrapper { position: relative; }
        .password-wrapper input { padding-right: 2.5rem; }
        .pw-toggle { position: absolute; right: 8px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; padding: 4px; display: flex; align-items: center; justify-content: center; }
        .pw-toggle svg { width: 18px; height: 18px; stroke: #9ca3af; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
        .pw-toggle:hover svg { stroke: #6b7280; }
        .auth-submit { padding: 0.7rem; background: #6366f1; color: white; border: none; border-radius: 8px; font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: background 0.2s; margin-top: 0.5rem; }
        .auth-submit:hover:not(:disabled) { background: #4f46e5; }
        .auth-submit:disabled { opacity: 0.6; cursor: not-allowed; }
        .auth-error { background: #fef2f2; color: #dc2626; padding: 0.65rem 0.85rem; border-radius: 8px; font-size: 0.85rem; border: 1px solid #fecaca; }
        .auth-footer { text-align: center; margin-top: 1.5rem; color: #6b7280; font-size: 0.9rem; }
        .auth-footer a { color: #6366f1; font-weight: 600; text-decoration: none; }
      `}</style>
    </div>
  );
}
