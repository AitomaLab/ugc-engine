'use client';

import { useState } from 'react';
import { supabase } from '@/lib/supabaseClient';
import Link from 'next/link';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const { error } = await supabase.auth.signInWithPassword({ email, password });

    if (error) {
      setError(error.message);
      setLoading(false);
    } else {
      window.location.href = '/';
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <img src="/StudioLogo_Black.svg" alt="Aitoma Studio" style={{ height: '36px' }} />
          <h1>Welcome back</h1>
          <p>Sign in to your account</p>
        </div>

        <form onSubmit={handleLogin} className="auth-form">
          {error && <div className="auth-error">{error}</div>}

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
            <input
              id="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Your password"
              required
            />
          </div>

          <button type="submit" className="auth-submit" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div className="auth-footer">
          Don&apos;t have an account? <Link href="/signup">Sign Up</Link>
        </div>
      </div>

      <style jsx>{`
        .auth-page {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 100vh;
          background: var(--bg-app, #f7f8fa);
          padding: 2rem;
        }
        .auth-card {
          background: white;
          border-radius: 16px;
          box-shadow: 0 4px 24px rgba(0,0,0,0.08);
          padding: 2.5rem;
          width: 100%;
          max-width: 420px;
        }
        .auth-header {
          text-align: center;
          margin-bottom: 2rem;
        }
        .auth-header h1 {
          font-size: 1.5rem;
          font-weight: 700;
          margin: 1rem 0 0.25rem;
          color: #1a1a2e;
        }
        .auth-header p {
          color: #6b7280;
          font-size: 0.9rem;
        }
        .auth-form {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }
        .auth-field label {
          display: block;
          font-size: 0.85rem;
          font-weight: 500;
          color: #374151;
          margin-bottom: 0.35rem;
        }
        .auth-field input {
          width: 100%;
          padding: 0.65rem 0.85rem;
          border: 1px solid #d1d5db;
          border-radius: 8px;
          font-size: 0.95rem;
          outline: none;
          transition: border-color 0.2s;
          box-sizing: border-box;
        }
        .auth-field input:focus {
          border-color: #6366f1;
          box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }
        .auth-submit {
          padding: 0.7rem;
          background: #6366f1;
          color: white;
          border: none;
          border-radius: 8px;
          font-size: 0.95rem;
          font-weight: 600;
          cursor: pointer;
          transition: background 0.2s;
          margin-top: 0.5rem;
        }
        .auth-submit:hover:not(:disabled) {
          background: #4f46e5;
        }
        .auth-submit:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
        .auth-error {
          background: #fef2f2;
          color: #dc2626;
          padding: 0.65rem 0.85rem;
          border-radius: 8px;
          font-size: 0.85rem;
          border: 1px solid #fecaca;
        }
        .auth-footer {
          text-align: center;
          margin-top: 1.5rem;
          color: #6b7280;
          font-size: 0.9rem;
        }
        .auth-footer a {
          color: #6366f1;
          font-weight: 600;
          text-decoration: none;
        }
      `}</style>
    </div>
  );
}
