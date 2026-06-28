# New Account Onboarding — Full Reference

Generated: 2026-06-28

This document maps the complete onboarding flow for new Aitoma Studio accounts: signup, account provisioning, post-login modal, first project launch, and free welcome video. Use it to analyze changes without hunting through the codebase.

---

## Table of contents

1. [End-to-end flow](#end-to-end-flow)
2. [File index](#file-index)
3. [Change boundaries](#change-boundaries)
4. [Known edge cases](#known-edge-cases)
5. [Testing checklist](#testing-checklist)
6. [OnboardingModal steps (summary)](#onboardingmodal-steps-summary)
7. [Common change scenarios](#common-change-scenarios)
8. [Source code by layer](#source-code-by-layer)

---

## End-to-end flow

```
Signup (signup/page.tsx)
  → Supabase validate_invite_code hook (optional)
  → handle_new_user trigger: profile + 100 credits + "My First Project"
  → Email confirmation
Login (login/page.tsx) → middleware → Dashboard (/)
  → localStorage gate: aitoma_onboarding_done_${userId}
  → hasExistingActivity check (projects/jobs/images)
  → OnboardingModal (4 steps)
  → onComplete: POST /creative-os/projects/ + router.push with brief/refs/seedance
  → projects/[id]: AgentPanel auto-submit
  → agent.py ONBOARDING_FIRST_VIDEO rules
  → generate_video.py: refund if first job in project
```

---

## File index

| Layer | File | Role |
|-------|------|------|
| 1 | `frontend/src/app/signup/page.tsx` | Signup form + email confirmation |
| 1 | `frontend/src/lib/signup-config.ts` | `REQUIRE_INVITE_CODE` env flag |
| 1 | `frontend/src/app/login/page.tsx` | Login → redirect `/` |
| 1 | `frontend/src/middleware.ts` | Auth cookie gate |
| 1 | `ugc_db/migrations/016_fix_new_user_trigger.sql` | 100 credits + default project |
| 1 | `ugc_db/migrations/051_invite_codes.sql` | Invite codes table |
| 1 | `ugc_db/migrations/053_invite_signup_optional.sql` | Open signup (current) |
| 1 | `ugc_db/migrations/057_restore_strict_invite_hook.sql` | Strict gate for production |
| 1 | `frontend/src/app/admin/InvitesTab.tsx` | Admin invite management |
| 1 | `ugc_backend/admin/router.py` | `/api/admin/invites` |
| 2 | `frontend/src/app/page.tsx` | Modal trigger + onComplete |
| 3 | `frontend/src/components/studio/OnboardingModal.tsx` | 4-step wizard UI |
| 3 | `frontend/src/locales/en.json` | `onboarding.*` strings |
| 3 | `frontend/src/locales/es.json` | Spanish strings |
| 4 | `frontend/src/app/projects/[id]/page.tsx` | brief/refs/seedance capture |
| 4 | `frontend/src/components/studio/AgentPanel.tsx` | Auto-submit + marker strip |
| 4 | `frontend/src/lib/agentLaunchDraft.ts` | sessionStorage handoff (dashboard) |
| 4 | `frontend/src/lib/launchCreativeOsProject.ts` | Alternative launch helper |
| 5 | `services/creative-os/routers/agent.py` | ONBOARDING_FIRST_VIDEO rules |
| 5 | `services/creative-os/routers/generate_video.py` | Credit refund for first job |

---

## Change boundaries

### Safe for UX-only onboarding changes
- `OnboardingModal.tsx`
- `page.tsx` onboarding blocks only (~187–213, ~741–770)
- `en.json` / `es.json` `onboarding.*` keys

### Touch only if changing first-video behavior
- `AgentPanel.tsx` (auto-submit, marker stripping)
- `projects/[id]/page.tsx` (launch params)
- `agent.py` + `generate_video.py`

### Avoid unless changing account provisioning
- `handle_new_user` migration, invite hooks
- `middleware.ts`, unrelated video pipelines
- Admin invites (signup gating only)

---

## Known edge cases

1. **Two projects on signup:** DB trigger creates `"My First Project"`; onboarding `onComplete` creates a second project `{product} × {influencer}`.
2. **Template products:** If user has no products, modal uses hardcoded `TEMPLATE_PRODUCTS` UUIDs — may not exist in user's DB (image-ads prompt uses `reference_image_urls` workaround).
3. **Free video refund:** Keyed on `<= 1 job in project`, not the `ONBOARDING_FIRST_VIDEO` marker — any first Seedance job in a new empty project gets refunded.
4. **localStorage gate:** `aitoma_onboarding_done_${userId}` — clearing it re-shows modal unless `hasExistingActivity` is true.
5. **Onboarding does not use** `launchCreativeOsProject.ts` — it passes query params directly (`?brief=&refs=&seedance=1`).

---

## Testing checklist

1. New account → confirm email → login → modal on `/`
2. Skip → modal never reappears
3. Complete → project created, agent auto-starts, Seedance on
4. First video: net 0 credits charged (100 remain)
5. Existing user with assets → no modal
6. Spanish locale → all `onboarding.*` render

---

## OnboardingModal steps (summary)

| Step | Index | Content |
|------|-------|---------|
| Welcome | 0 | Logo, title, "100 free credits" badge, Get started |
| Capabilities | 1 | 3 autoplay showcase videos (UGC, Cinematic, Ad Creatives) |
| Agent intro | 2 | Demo video + hint about @ mentions |
| First ad | 3 | Pick product → influencer → suggested prompt → Create now |

**Hardcoded in modal:**
- `SHOWCASE_VIDEOS` — Cloudinary URLs (step 1)
- `TEMPLATE_PRODUCTS` — Protein, Skincare, Apple Headphones (fallback)
- `TEMPLATE_NAMES` — Mateo, Lexi, Amelie (curated influencers)
- Agent demo video URL in step 2

**Prompt markers appended on Create** (invisible in chat UI, sent to agent):
- `[9:16 vertical]`, `[5s clip duration]`, script/product rules
- `[ONBOARDING_FIRST_VIDEO — ... FREE ...]`
- Optional `[USE reference_image_urls ...]` for image-ads prompt

---

## Common change scenarios

| Goal | Primary files |
|------|----------------|
| Redesign modal steps / copy | `OnboardingModal.tsx`, `en.json`, `es.json` |
| Change when modal appears | `page.tsx` (gate + localStorage key) |
| Different first-action (skip video, go elsewhere) | `page.tsx` `onComplete`, maybe remove `seedance=1` |
| New template products/influencers | `OnboardingModal.tsx` constants |
| Remove free first video | Modal markers + `agent.py` + `generate_video.py` |
| Re-enable invite-only signup | `signup-config.ts`, `signup/page.tsx`, run `057_restore_strict_invite_hook.sql` |
| Change welcome credits | `016_fix_new_user_trigger.sql` + modal/locale copy |

---

## Source code by layer


### Layer 1 — Signup config

**Path:** `frontend/src/lib/signup-config.ts` (full file)

```typescript
/** When true, signup requires an invite code (UI + metadata). Keep false until production launch. */
export const REQUIRE_INVITE_CODE =
  process.env.NEXT_PUBLIC_REQUIRE_INVITE_CODE === 'true';
```

### Layer 1 — Auth middleware

**Path:** `frontend/src/middleware.ts` (full file)

```typescript
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Auth middleware — checks for Supabase session cookies.
 * 
 * Supabase stores its auth tokens in cookies prefixed with "sb-".
 * We check for the presence of these cookies to determine if the user is logged in.
 * This avoids the complexity of @supabase/ssr server-side session validation
 * and works reliably with the client-side signInWithPassword() flow.
 */
export async function middleware(req: NextRequest) {
  const path = req.nextUrl.pathname;

  // Public routes that don't require auth
  const publicRoutes = ['/login', '/signup', '/forgot-password', '/reset-password', '/logout'];
  // Server-to-server callback routes (no auth cookies)
  const serverRoutes = ['/api/editor/render/'];
  // API routes that don't require auth (internal editor resources)
  const noAuthApiRoutes = ['/api/fonts/'];
  const isPublicRoute = publicRoutes.some(route => path.startsWith(route));
  const isServerRoute = serverRoutes.some(route => path.startsWith(route) && path.includes('/callback'));
  const isNoAuthApi = noAuthApiRoutes.some(route => path.startsWith(route));

  // Check for Supabase auth cookie (set by @supabase/supabase-js client)
  // Supabase stores tokens in cookies like "sb-<project-ref>-auth-token"
  const cookies = req.cookies.getAll();
  const hasAuthCookie = cookies.some(c => 
    c.name.includes('sb-') && c.name.includes('auth-token')
  );

  // If not logged in and not on a public route, redirect to login
  if (!hasAuthCookie && !isPublicRoute && !isServerRoute && !isNoAuthApi) {
    const loginUrl = new URL('/login', req.url);
    loginUrl.searchParams.set('redirectTo', path);
    return NextResponse.redirect(loginUrl);
  }

  // If logged in and on login/signup, redirect to home
  // (but NOT forgot-password/reset-password — recovery sessions need those pages)
  const redirectAuthRoutes = ['/login', '/signup'];
  const shouldRedirectAuth = redirectAuthRoutes.some(route => path.startsWith(route));
  if (hasAuthCookie && shouldRedirectAuth) {
    return NextResponse.redirect(new URL('/', req.url));
  }

  // Legacy standalone pages — bare URLs only (contextual ?query deep links are
  // migrated on source pages or handled by /create launcher fallback).
  const isBareCreate = path === '/create' && !req.nextUrl.search;
  const isBareVideos = path === '/videos' && !req.nextUrl.search;
  if (isBareCreate || isBareVideos) {
    return NextResponse.redirect(new URL(isBareVideos ? '/projects' : '/', req.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Match all routes except static files and Next.js internals
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)',
  ],
};
```

### Layer 1 — Signup page

**Path:** `frontend/src/app/signup/page.tsx` (full file)

```typescript
'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { supabase } from '@/lib/supabaseClient';
import { REQUIRE_INVITE_CODE } from '@/lib/signup-config';
import Link from 'next/link';

export default function SignupPage() {
  return (
    <Suspense fallback={null}>
      <SignupForm />
    </Suspense>
  );
}

function SignupForm() {
  const searchParams = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [name, setName] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [inviteLocked, setInviteLocked] = useState(false);
  const [error, setError] = useState<{ title?: string; text: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!REQUIRE_INVITE_CODE) return;
    const code = searchParams.get('invite');
    if (code) {
      setInviteCode(code.trim());
      setInviteLocked(true);
    }
  }, [searchParams]);

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const metadata: Record<string, string> = { name };
    if (REQUIRE_INVITE_CODE) {
      metadata.invite_code = inviteCode.trim();
    }

    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: metadata },
    });

    if (error) {
      const raw = error.message || '';
      const isRawHookError = /running hook|validate_invite_code|pg-functions/i.test(raw);
      const isInviteReject = /invite[_ ]?code/i.test(raw);
      if (isRawHookError) {
        setError({
          title: 'We couldn’t verify your invite code',
          text: 'Please sign up using your invitation link and the email address the code was assigned to. If this keeps happening, contact support.',
        });
      } else if (isInviteReject) {
        setError({ title: 'Invite code problem', text: raw });
      } else {
        setError({ text: raw });
      }
      setLoading(false);
    } else {
      await supabase.auth.signOut();
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
          {error && (
            <div className="auth-error" role="alert">
              <svg className="auth-error-icon" viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <div className="auth-error-body">
                {error.title && <strong>{error.title}</strong>}
                <span>{error.text}</span>
              </div>
            </div>
          )}

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

          {REQUIRE_INVITE_CODE && (
            <div className="auth-field">
              <label htmlFor="invite">Invite Code</label>
              <input
                id="invite"
                type="text"
                value={inviteCode}
                onChange={e => setInviteCode(e.target.value)}
                placeholder="Enter your invite code"
                readOnly={inviteLocked}
                required
                className={inviteLocked ? 'invite-locked' : undefined}
              />
              {inviteLocked && (
                <span className="invite-hint">Invite code applied from your link.</span>
              )}
            </div>
          )}

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
        .auth-field input.invite-locked { background: #f3f4f6; color: #6b7280; cursor: not-allowed; }
        .invite-hint { display: block; margin-top: 0.35rem; font-size: 0.75rem; color: #059669; font-weight: 500; }
        .password-wrapper { position: relative; }
        .password-wrapper input { padding-right: 2.5rem; }
        .pw-toggle { position: absolute; right: 8px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; padding: 4px; display: flex; align-items: center; justify-content: center; }
        .pw-toggle svg { width: 18px; height: 18px; stroke: #9ca3af; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
        .pw-toggle:hover svg { stroke: #6b7280; }
        .auth-submit { padding: 0.7rem; background: #6366f1; color: white; border: none; border-radius: 8px; font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: background 0.2s; margin-top: 0.5rem; }
        .auth-submit:hover:not(:disabled) { background: #4f46e5; }
        .auth-submit:disabled { opacity: 0.6; cursor: not-allowed; }
        .auth-error { display: flex; gap: 0.6rem; align-items: flex-start; background: #fef2f2; color: #b91c1c; padding: 0.8rem 0.9rem; border-radius: 10px; font-size: 0.85rem; border: 1px solid #fecaca; }
        .auth-error-icon { width: 18px; height: 18px; flex-shrink: 0; margin-top: 1px; stroke: #dc2626; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
        .auth-error-body { display: flex; flex-direction: column; gap: 0.2rem; line-height: 1.45; }
        .auth-error-body strong { font-weight: 700; color: #991b1b; font-size: 0.9rem; }
        .auth-footer { text-align: center; margin-top: 1.5rem; color: #6b7280; font-size: 0.9rem; }
        .auth-footer a { color: #6366f1; font-weight: 600; text-decoration: none; }
      `}</style>
    </div>
  );
}
```

### Layer 1 — Login page (auth handler)

**Path:** `frontend/src/app/login/page.tsx` (lines 1–37)

```typescript
'use client';

import { useState, useEffect } from 'react';
import { supabase } from '@/lib/supabaseClient';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';

export default function LoginPage() {
  const searchParams = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [sessionNotice, setSessionNotice] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (searchParams.get('reason') === 'session_expired') {
      setSessionNotice('Your session expired. Please sign in again.');
    }
  }, [searchParams]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const { error } = await supabase.auth.signInWithPassword({ email, password });

    if (error) {
      setError(error.message);
      setLoading(false);
    } else {
      const redirectTo = searchParams.get('redirectTo');
      window.location.href = redirectTo && redirectTo.startsWith('/') ? redirectTo : '/';
    }
  };
```

### Layer 1 — New user DB trigger

**Path:** `ugc_db/migrations/016_fix_new_user_trigger.sql` (full file)

```sql
-- Fix for the handle_new_user trigger
-- The previous trigger automatically forced users into the 'Starter' plan with 1000 credits.
-- This updated trigger fixes it so users are placed on the 'Free' plan (by not inserting a subscription)
-- and gives them exactly 100 welcome credits.

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_wallet_id UUID;
BEGIN
  -- Create user profile (using 'name' and 'email' as per the live schema)
  INSERT INTO public.profiles (id, name, email)
  VALUES (NEW.id, split_part(NEW.email, '@', 1), NEW.email);

  -- Create wallet with exactly 100 credits (No subscription attached)
  INSERT INTO public.credit_wallets (user_id, balance)
  VALUES (NEW.id, 100)
  RETURNING id INTO v_wallet_id;

  -- Create default project
  INSERT INTO public.projects (user_id, name)
  VALUES (NEW.id, 'My First Project');

  -- Log the 100 free credits as a welcome bonus transaction
  INSERT INTO public.credit_transactions (wallet_id, amount, type, description)
  VALUES (v_wallet_id, 100, 'welcome_bonus', '100 Free Credits on Sign-up');

  RETURN NEW;
END;
$$;
```

### Layer 1 — Invite codes table

**Path:** `ugc_db/migrations/051_invite_codes.sql` (full file)

```sql
-- 042_invite_codes.sql
-- Gated beta: one single-use invite code per waitlist email. A user can only
-- sign up by supplying the code generated for their exact email address. No
-- multi-use or referral sharing at this stage.
--
-- NOTE: The canonical invite_codes migration + before-user-created auth hook
-- are maintained separately and run manually in the Supabase SQL Editor. This
-- file is an additive, IF-NOT-EXISTS fallback that documents the minimal shape
-- the backend admin router relies on; it is a no-op if the table already exists.

CREATE TABLE IF NOT EXISTS public.invite_codes (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT,
    code          TEXT NOT NULL UNIQUE,
    label         TEXT,
    -- Flipped true (with used_at) by the before-user-created auth hook once consumed.
    is_used       BOOLEAN NOT NULL DEFAULT FALSE,
    used_at       TIMESTAMPTZ,
    -- True once the code has been written to the Brevo contact's INVITE_CODE.
    brevo_synced  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One code per email (case-insensitive) + fast filtering of the sync backlog.
CREATE UNIQUE INDEX IF NOT EXISTS invite_codes_email_lower_idx
    ON public.invite_codes (LOWER(email))
    WHERE email IS NOT NULL;

CREATE INDEX IF NOT EXISTS invite_codes_brevo_synced_idx
    ON public.invite_codes (brevo_synced);
```

### Layer 1 — Open signup hook (current)

**Path:** `ugc_db/migrations/053_invite_signup_optional.sql` (full file)

```sql
-- Temporarily disable invite-code gating on signup.
-- Run in Supabase SQL Editor while NEXT_PUBLIC_REQUIRE_INVITE_CODE=false.
-- Before production launch, restore the strict empty-code rejection in 052.

create or replace function public.validate_invite_code(event jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_email text;
  v_code  text;
  v_row   public.invite_codes%rowtype;
begin
  v_email := lower(trim(event -> 'user' ->> 'email'));

  v_code := upper(trim(coalesce(
    event -> 'user' -> 'raw_user_meta_data' ->> 'invite_code',
    event -> 'user' -> 'user_metadata'      ->> 'invite_code',
    event -> 'claims' -> 'user_metadata'     ->> 'invite_code',
    event ->> 'invite_code',
    ''
  )));

  -- Open signup while invite gate is disabled. Codes are still validated when provided.
  if v_code is null or v_code = '' then
    return '{}'::jsonb;
  end if;

  select * into v_row
  from public.invite_codes
  where upper(trim(code)) = v_code
  limit 1;

  if not found then
    return jsonb_build_object('error', jsonb_build_object(
      'http_code', 403,
      'message', 'This invite code is invalid. Please check your invitation email.'
    ));
  end if;

  if coalesce(v_row.is_used, false) then
    return jsonb_build_object('error', jsonb_build_object(
      'http_code', 403,
      'message', 'This invite code has already been used.'
    ));
  end if;

  if v_row.email is null or lower(trim(v_row.email)) <> v_email then
    return jsonb_build_object('error', jsonb_build_object(
      'http_code', 403,
      'message', 'This invite code does not match this email address. Please use the email the code was assigned to.'
    ));
  end if;

  update public.invite_codes set is_used = true, used_at = now() where id = v_row.id;
  return '{}'::jsonb;
end;
$$;

grant usage on schema public to supabase_auth_admin;
grant execute on function public.validate_invite_code(jsonb) to supabase_auth_admin;
grant select, update on table public.invite_codes to supabase_auth_admin;
revoke execute on function public.validate_invite_code(jsonb) from authenticated, anon, public;
```

### Layer 2 — Dashboard lazy import

**Path:** `frontend/src/app/page.tsx` (lines 17–22)

```typescript
// Only new users ever see onboarding — keep its bundle (and its autoplay
// walkthrough videos) out of the dashboard's initial chunk.
const OnboardingModal = dynamic(
  () => import("@/components/studio/OnboardingModal").then(m => m.OnboardingModal),
  { ssr: false },
);
```

### Layer 2 — Onboarding gate + state

**Path:** `frontend/src/app/page.tsx` (lines 187–213)

```typescript
  // Onboarding — show only for genuinely new users (localStorage + activity gate)
  const userId = session?.user?.id;
  const onboardingKey = userId ? `aitoma_onboarding_done_${userId}` : '';
  const [showOnboarding, setShowOnboarding] = useState(false);

  const hasExistingActivity = useMemo(() => {
    if (projects.some((p) => (p.asset_counts?.images ?? 0) + (p.asset_counts?.videos ?? 0) > 0)) return true;
    if (jobs.some((j) => j.status === 'success')) return true;
    if (recentImages.length > 0) return true;
    return false;
  }, [projects, jobs, recentImages]);

  const markOnboardingDone = useCallback(() => {
    if (onboardingKey) localStorage.setItem(onboardingKey, '1');
    setShowOnboarding(false);
  }, [onboardingKey]);

  useEffect(() => {
    if (!onboardingKey || jobsLoading || projectsData === undefined) return;
    const dismissed = localStorage.getItem(onboardingKey);
    if (dismissed || hasExistingActivity) {
      if (hasExistingActivity && !dismissed) localStorage.setItem(onboardingKey, '1');
      setShowOnboarding(false);
      return;
    }
    setShowOnboarding(true);
  }, [onboardingKey, jobsLoading, projectsData, hasExistingActivity]);
```

### Layer 2 — Onboarding modal mount + onComplete

**Path:** `frontend/src/app/page.tsx` (lines 741–770)

```typescript
      {/* Onboarding modal for first-time users */}
      {showOnboarding && (
        <OnboardingModal
          onComplete={async ({ productId, productName, productImageUrl, influencerId, influencerName, influencerImageUrl, prompt: selectedPrompt }) => {
            try {
              markOnboardingDone();
              // Create a new project and navigate to it with the prompt pre-filled
              const name = `${productName} × ${influencerName}`;
              const newProject = await creativeFetch<{ id: string }>('/creative-os/projects/', {
                method: 'POST',
                body: JSON.stringify({ name }),
              });
              if (newProject?.id) {
                // Build proper @ references so the agent can resolve the product & influencer
                const refs = [
                  { type: 'product', tag: productName, name: productName, id: productId, image_url: productImageUrl || undefined },
                  { type: 'influencer', tag: influencerName, name: influencerName, id: influencerId, image_url: influencerImageUrl || undefined },
                ];
                const refsParam = encodeURIComponent(JSON.stringify(refs));
                router.push(
                  `/projects/${newProject.id}?brief=${encodeURIComponent(selectedPrompt)}&refs=${refsParam}&seedance=1`
                );
              }
            } catch (err) {
              console.error('Onboarding project creation failed:', err);
              markOnboardingDone();
            }
          }}
          onSkip={markOnboardingDone}
        />
```

### Layer 3 — Onboarding modal (full)

**Path:** `frontend/src/components/studio/OnboardingModal.tsx` (full file)

```typescript
'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from '@/lib/i18n';
import { apiFetch } from '@/lib/utils';
import { creativeFetch } from '@/lib/creative-os-api';

/* ── Types ────────────────────────────────────────────────────── */

interface RealProduct {
    id: string;
    name: string;
    description?: string;
    image_url?: string;
    product_image?: string;
}

interface RealInfluencer {
    id: string;
    name: string;
    description?: string;
    profile_image_url?: string;
    image_url?: string;
    thumbnail_url?: string;
}

/* ── Hardcoded showcase videos ─────────────────────────────────── */
const SHOWCASE_VIDEOS = [
    { label: 'UGC Videos', url: 'https://res.cloudinary.com/ducrze2ys/video/upload/v1777294804/MariaVideo_avxpjt.mp4' },
    { label: 'Cinematic Ads', url: 'https://res.cloudinary.com/ducrze2ys/video/upload/v1777322746/Poppi_-_Product_puarix.mov' },
    { label: 'Ad Creatives', url: 'https://res.cloudinary.com/ducrze2ys/video/upload/v1777294720/KaiVideo_ssbyz8.mp4' },
];

/* ── Template products for new users without any products ───── */
const TEMPLATE_PRODUCTS: RealProduct[] = [
    {
        id: '434540e2-2b00-49fa-8749-3bd3e6f71ff3',
        name: 'Protein',
        image_url: 'https://kzvdfponrzwfwdbkpfjf.supabase.co/storage/v1/object/public/product-images/35c48749-25d5-462d-9503-c1e275f2c417.png',
    },
    {
        id: 'fd752583-4988-48ed-84e1-c371b7b6cc05',
        name: 'Skincare',
        image_url: 'https://kzvdfponrzwfwdbkpfjf.supabase.co/storage/v1/object/public/product-images/f7979a91-f483-42c3-9c6c-aec8013f6021.png',
    },
    {
        id: 'd377775e-afac-4af4-a133-dcb64babf739',
        name: 'Apple Headphones',
        image_url: 'https://kzvdfponrzwfwdbkpfjf.supabase.co/storage/v1/object/public/product-images/8130031c-5b67-43d0-8558-3e516656309d.png',
    },
];

/* ── Helpers ───────────────────────────────────────────────────── */

function getInfluencerImage(inf: RealInfluencer): string | null {
    return inf.profile_image_url || inf.image_url || inf.thumbnail_url || null;
}

function getProductImage(p: RealProduct): string | null {
    return p.image_url || p.product_image || null;
}

function getSuggestedPrompts(product: string, influencer: string): string[] {
    return [
        `Create a UGC ad with @${influencer} showing @${product} and explaining why it's a must-have this summer`,
        `Generate 3 image ads of @${influencer} holding @${product} in different scenarios`,
        `Create an eye-grabbing cinematic ad of @${product}`,
    ];
}

/* ── @-mention pill (mirrors chat styling) ──────────────────────────── */

function MentionPill({ image, name }: { image?: string | null; name: string }) {
    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', gap: '4px',
            padding: '2px 8px 2px 2px', borderRadius: '6px',
            background: 'rgba(51,122,255,0.08)', border: '1px solid rgba(51,122,255,0.15)',
            verticalAlign: 'baseline',
        }}>
            {image && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={image} alt="" style={{ width: '18px', height: '18px', borderRadius: '4px', objectFit: 'cover', flexShrink: 0 }} />
            )}
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#337AFF', maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</span>
        </span>
    );
}

/** Parse "@<name>" tokens in a prompt and render matches as MentionPill.
 *  Matching is case-insensitive against the product + influencer names. */
function renderPromptWithPills(
    prompt: string,
    refs: { name: string; image: string | null }[],
): React.ReactNode {
    if (!prompt) return prompt;
    // Match against the literal @<name> strings (longest first so multi-word
    // names like "@Apple Headphones" win over a partial "@Apple" match).
    const tokens = refs
        .map(r => ({ ...r, token: `@${r.name}` }))
        .sort((a, b) => b.token.length - a.token.length);
    if (!tokens.length) return prompt;
    const nodes: React.ReactNode[] = [];
    let remaining = prompt;
    let key = 0;
    while (remaining.length) {
        // Find the earliest token occurrence in the remaining string.
        let bestIdx = -1;
        let bestTok: typeof tokens[number] | null = null;
        for (const t of tokens) {
            const idx = remaining.toLowerCase().indexOf(t.token.toLowerCase());
            if (idx !== -1 && (bestIdx === -1 || idx < bestIdx)) {
                bestIdx = idx;
                bestTok = t;
            }
        }
        if (!bestTok || bestIdx === -1) {
            nodes.push(<span key={key++}>{remaining}</span>);
            break;
        }
        if (bestIdx > 0) nodes.push(<span key={key++}>{remaining.slice(0, bestIdx)}</span>);
        nodes.push(<MentionPill key={key++} image={bestTok.image || undefined} name={bestTok.name} />);
        remaining = remaining.slice(bestIdx + bestTok.token.length);
    }
    return nodes;
}

/* ── 9:16 image card with hover-revealed edit icon (top-right) ─────── */

function HoverEditableCard({ imageUrl, onEdit, title }: { imageUrl: string | null; onEdit: () => void; title: string }) {
    const [hovered, setHovered] = useState(false);
    return (
        <div
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
                position: 'relative',
                height: 'min(360px, 42vh)',
                aspectRatio: '9 / 16',
                borderRadius: '18px',
                overflow: 'hidden',
                background: '#F4F6FA',
                border: '1px solid rgba(0,0,0,0.06)',
                transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                transform: hovered ? 'scale(1.01)' : 'none',
                boxShadow: hovered ? '0 8px 24px rgba(0,0,0,0.12)' : 'none',
            }}
        >
            {imageUrl && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={imageUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            )}
            <button
                onClick={onEdit}
                title={title}
                style={{
                    position: 'absolute',
                    top: '10px',
                    right: '10px',
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    background: 'rgba(255,255,255,0.95)',
                    border: '1px solid rgba(0,0,0,0.08)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    boxShadow: '0 2px 6px rgba(0,0,0,0.15)',
                    padding: 0,
                    opacity: hovered ? 1 : 0,
                    transform: hovered ? 'scale(1)' : 'scale(0.85)',
                    transition: 'opacity 0.18s ease, transform 0.18s ease',
                    pointerEvents: hovered ? 'auto' : 'none',
                }}
            >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0D1B3E" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
            </button>
        </div>
    );
}

/* ── Component ────────────────────────────────────────────────── */

interface OnboardingModalProps {
    onComplete: (params: {
        productId: string;
        productName: string;
        productImageUrl: string | null;
        influencerId: string;
        influencerName: string;
        influencerImageUrl: string | null;
        prompt: string;
    }) => void;
    onSkip: () => void;
}

export function OnboardingModal({ onComplete, onSkip }: OnboardingModalProps) {
    const { t } = useTranslation();
    const [step, setStep] = useState(0);
    const [selectedProduct, setSelectedProduct] = useState('');
    const [selectedInfluencer, setSelectedInfluencer] = useState('');
    const [selectedPrompt, setSelectedPrompt] = useState('');

    // Real data from DB
    const [products, setProducts] = useState<RealProduct[]>([]);
    const [influencers, setInfluencers] = useState<RealInfluencer[]>([]);
    const [loading, setLoading] = useState(true);

    // Fetch real products & influencers on mount
    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            try {
                const [prods, infs] = await Promise.all([
                    apiFetch<RealProduct[]>('/api/products', { skipProjectScope: true }).catch(() => []),
                    apiFetch<RealInfluencer[]>('/influencers', { skipProjectScope: true }).catch(() => []),
                ]);
                if (cancelled) return;
                // Fall back to template products when user has none
                const finalProducts = (prods || []).length > 0 ? (prods || []).slice(0, 3) : TEMPLATE_PRODUCTS;
                setProducts(finalProducts);

                // Pick the curated template trio for first-time users. If the
                // user has built up their own roster, fall back to the first
                // three of theirs (mirrors the prior behavior).
                const TEMPLATE_NAMES = ['Mateo', 'Lexi', 'Amelie'];
                const all = infs || [];
                const templates = TEMPLATE_NAMES
                    .map(n => all.find(i => (i.name || '').toLowerCase() === n.toLowerCase()))
                    .filter((i): i is RealInfluencer => !!i);
                setInfluencers(templates.length > 0 ? templates : all.slice(0, 3));
            } catch (err) {
                console.warn('Onboarding data load failed:', err);
            } finally {
                if (!cancelled) setLoading(false);
            }
        };
        load();
        return () => { cancelled = true; };
    }, []);

    const product = products.find(p => p.id === selectedProduct);
    const influencer = influencers.find(i => i.id === selectedInfluencer);
    const prompts = product && influencer ? getSuggestedPrompts(product.name, influencer.name) : [];

    const handleCreate = () => {
        if (!product || !influencer || !selectedPrompt) return;
        const productImageUrl = getProductImage(product);
        const influencerImageUrl = getInfluencerImage(influencer);
        // Prompt #2 (3 image ads) uses template products whose UUIDs may not
        // exist in the user's DB → backend 404s on product_id lookup. Tell the
        // agent to use reference_image_urls instead so the pipeline takes the
        // upload-only branch which works without a DB row.
        const isImageAdsPrompt = selectedPrompt.toLowerCase().includes('image ads');
        const refImageHint = isImageAdsPrompt
            ? ` [USE reference_image_urls (NOT product_id) when calling generate_image. URLs to pass: ${[productImageUrl, influencerImageUrl].filter(Boolean).join(' AND ')}. The pipeline takes the upload-only branch and renders 3 composites from these two images.]`
            : '';
        onComplete({
            productId: product.id,
            productName: product.name,
            productImageUrl,
            influencerId: influencer.id,
            influencerName: influencer.name,
            influencerImageUrl,
            prompt: `${selectedPrompt} [9:16 vertical] [5s clip duration] [SCRIPT LENGTH: hook/dialogue MUST be ≤12 words total — anything longer cannot be spoken in 5 seconds.] [PRODUCT INTERACTION: if the product has a cap, lid, seal, or wrapper (bottle, jar, tube, can, pouch), the character MUST visibly open/unscrew/remove it BEFORE drinking, eating, or using — never drink through a closed cap or use a sealed product. No impossible interactions, no hallucinations.] [ONBOARDING_FIRST_VIDEO — this is the user's welcome video, it must be FREE (0 credits). Use the product image_url as a reference_image in Seedance so the product is visible in the video.]${refImageHint}`,
        });
    };

    const renderStep = () => {
        switch (step) {
            /* ── Step 1: Welcome ── */
            case 0:
                return (
                    <div style={{ textAlign: 'center', padding: '40px 30px' }}>
                        {/* Real Studio Logo — large & visible */}
                        <div style={{
                            margin: '0 auto 28px',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                            <img
                                src="/StudioLogo_Black.svg"
                                alt="Aitoma Studio"
                                style={{ width: '180px', height: 'auto', objectFit: 'contain' }}
                            />
                        </div>
                        <h2 style={{ fontSize: '24px', fontWeight: 800, color: '#0D1B3E', margin: '0 0 12px', lineHeight: 1.2 }}>
                            {t('onboarding.welcomeTitle')}
                        </h2>
                        <p style={{ fontSize: '15px', color: '#5A6178', margin: '0 0 20px', lineHeight: 1.6 }}>
                            {t('onboarding.welcomeSubtitle')}
                        </p>
                        {/* Credits badge — blue theme */}
                        <div style={{
                            display: 'inline-flex', alignItems: 'center', gap: '8px',
                            padding: '10px 20px', borderRadius: '999px',
                            background: 'rgba(51,122,255,0.08)', color: '#337AFF',
                            fontSize: '14px', fontWeight: 700,
                            border: '1px solid rgba(51,122,255,0.15)',
                        }}>
                            <svg viewBox="0 0 24 24" style={{ width: '16px', height: '16px', fill: 'none', stroke: '#337AFF', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                                <rect x="3" y="8" width="18" height="13" rx="2" />
                                <path d="M12 8v13" />
                                <path d="M3 13h18" />
                                <path d="M7.5 8C7.5 8 7 3 12 3s4.5 5 4.5 5" />
                            </svg>
                            {t('onboarding.freeCredits')}
                        </div>
                        <div style={{ marginTop: '32px' }}>
                            <button onClick={() => setStep(1)} style={primaryBtnStyle}>
                                {t('onboarding.getStarted')}
                            </button>
                        </div>
                    </div>
                );

            /* ── Step 2: Capabilities with 9:16 video previews ── */
            case 1:
                return (
                    <div style={{ padding: '30px' }}>
                        <h3 style={{ fontSize: '20px', fontWeight: 800, color: '#0D1B3E', margin: '0 0 6px', textAlign: 'center' }}>
                            {t('onboarding.capabilitiesTitle')}
                        </h3>
                        <p style={{ fontSize: '14px', color: '#6b7280', margin: '0 0 20px', textAlign: 'center', lineHeight: 1.4 }}>
                            {t('onboarding.capabilitiesSubtitle')}
                        </p>
                        <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
                            {SHOWCASE_VIDEOS.map((sv, i) => (
                                <ShowcaseVideoCard key={i} url={sv.url} label={sv.label} />
                            ))}
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '24px' }}>
                            <button onClick={() => setStep(0)} style={secondaryBtnStyle}>{t('onboarding.back')}</button>
                            <button onClick={() => setStep(2)} style={primaryBtnStyle}>{t('onboarding.next')}</button>
                        </div>
                    </div>
                );

            /* ── Step 3: How Agent Works ── */
            case 2:
                return (
                    <div style={{ padding: '30px' }}>
                        <h3 style={{ fontSize: '20px', fontWeight: 800, color: '#0D1B3E', margin: '0 0 12px', textAlign: 'center' }}>
                            {t('onboarding.agentTitle')}
                        </h3>
                        <p style={{ fontSize: '14px', color: '#5A6178', textAlign: 'center', margin: '0 0 20px', lineHeight: 1.6 }}>
                            {t('onboarding.agentDesc')}
                        </p>
                        <div style={{
                            borderRadius: '12px',
                            overflow: 'hidden',
                            border: '1px solid rgba(0,0,0,0.08)',
                            marginBottom: '12px',
                            width: '70%',
                            maxWidth: '70%',
                            marginLeft: 'auto',
                            marginRight: 'auto',
                        }}>
                            <video
                                src="https://res.cloudinary.com/ducrze2ys/video/upload/v1777570469/StudioRecording_final_edxjzf.mp4"
                                muted
                                autoPlay
                                loop
                                playsInline
                                preload="auto"
                                style={{
                                    width: '100%',
                                    display: 'block',
                                    borderRadius: '12px',
                                }}
                            />
                        </div>
                        <div style={{
                            fontSize: '12px', color: '#8A93B0', textAlign: 'center',
                            background: 'rgba(0,0,0,0.03)', padding: '8px 12px', borderRadius: '8px',
                        }}>
                            {t('onboarding.agentHint')}
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '24px' }}>
                            <button onClick={() => setStep(1)} style={secondaryBtnStyle}>{t('onboarding.back')}</button>
                            <button onClick={() => setStep(3)} style={primaryBtnStyle}>{t('onboarding.next')}</button>
                        </div>
                    </div>
                );

            /* ── Step 4: Pick Product + Influencer (sequential reveal) ── */
            case 3:
                return (
                    <div style={{ padding: '24px 30px' }}>
                        <h3 style={{ fontSize: '20px', fontWeight: 800, color: '#0D1B3E', margin: '0 0 16px', textAlign: 'center' }}>
                            {t('onboarding.pickTitle')}
                        </h3>

                        {loading ? (
                            <div style={{ textAlign: 'center', padding: '40px 0', color: '#8A93B0', fontSize: '13px' }}>
                                Loading...
                            </div>
                        ) : (
                            <>
                                {/* ── Products (always visible) ── */}
                                {!selectedProduct && (
                                    <>
                                        <div style={{ fontSize: '12px', fontWeight: 700, color: '#8A93B0', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>
                                            {t('onboarding.pickProduct')}
                                        </div>
                                        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                                            {products.map(p => (
                                                <PickerCard
                                                    key={p.id}
                                                    selected={selectedProduct === p.id}
                                                    onClick={() => setSelectedProduct(p.id)}
                                                    imageUrl={getProductImage(p)}
                                                    name={p.name}
                                                />
                                            ))}
                                        </div>
                                    </>
                                )}

                                {/* ── Selected product chip (only while picking influencer) ── */}
                                {selectedProduct && !selectedInfluencer && (
                                    <div style={{
                                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                        padding: '8px 14px', borderRadius: '10px',
                                        background: 'rgba(51,122,255,0.06)', border: '1px solid rgba(51,122,255,0.15)',
                                        marginBottom: '16px',
                                    }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                            {product && getProductImage(product) && (
                                                <img src={getProductImage(product)!} alt="" style={{ width: '28px', height: '28px', borderRadius: '6px', objectFit: 'cover' }} />
                                            )}
                                            <span style={{ fontSize: '13px', fontWeight: 700, color: '#0D1B3E' }}>{product?.name}</span>
                                        </div>
                                        <button
                                            onClick={() => { setSelectedProduct(''); setSelectedInfluencer(''); setSelectedPrompt(''); }}
                                            style={{ background: 'none', border: 'none', color: '#337AFF', fontSize: '12px', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
                                        >
                                            Change
                                        </button>
                                    </div>
                                )}

                                {/* ── Influencers (after product selected) ── */}
                                {selectedProduct && !selectedInfluencer && (
                                    <>
                                        <div style={{ fontSize: '12px', fontWeight: 700, color: '#8A93B0', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>
                                            {t('onboarding.pickInfluencer')}
                                        </div>
                                        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                                            {influencers.map(inf => (
                                                <PickerCard
                                                    key={inf.id}
                                                    selected={selectedInfluencer === inf.id}
                                                    onClick={() => setSelectedInfluencer(inf.id)}
                                                    imageUrl={getInfluencerImage(inf)}
                                                    name={inf.name}
                                                />
                                            ))}
                                        </div>
                                    </>
                                )}

                                {/* ── Two-column layout when both are selected:
                                    LEFT = product + influencer as 9:16 cards
                                    RIGHT = prompt suggestions ── */}
                                {selectedProduct && selectedInfluencer && (() => {
                                    const promptRefs = [
                                        product ? { name: product.name, image: getProductImage(product) } : null,
                                        influencer ? { name: influencer.name, image: getInfluencerImage(influencer) } : null,
                                    ].filter(Boolean) as { name: string; image: string | null }[];

                                    return (
                                        <div style={{ display: 'flex', gap: '20px', marginBottom: '16px', alignItems: 'flex-start' }}>
                                            {/* LEFT column — two 9:16 cards, ~202×360 each. Edit icon shows on hover, top-right. */}
                                            <div style={{ display: 'flex', flexDirection: 'row', gap: '8px' }}>
                                                <HoverEditableCard
                                                    imageUrl={product ? getProductImage(product) : null}
                                                    onEdit={() => { setSelectedProduct(''); setSelectedInfluencer(''); setSelectedPrompt(''); }}
                                                    title="Change product"
                                                />
                                                <HoverEditableCard
                                                    imageUrl={influencer ? getInfluencerImage(influencer) : null}
                                                    onEdit={() => { setSelectedInfluencer(''); setSelectedPrompt(''); }}
                                                    title="Change influencer"
                                                />
                                            </div>

                                            {/* RIGHT column — prompts; column stretches to match
                                                the height of the 9:16 cards on the left so the
                                                whole row reads as one balanced block. */}
                                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: 'min(360px, 42vh)' }}>
                                                <div style={{ fontSize: '12px', fontWeight: 700, color: '#8A93B0', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '20px' }}>
                                                    {t('onboarding.suggestedPrompts')}
                                                </div>
                                                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', flex: 1, justifyContent: 'flex-start' }}>
                                                    {prompts.map((p, i) => (
                                                        <button
                                                            key={i}
                                                            onClick={() => setSelectedPrompt(p)}
                                                            style={{
                                                                padding: '16px 18px',
                                                                borderRadius: '10px',
                                                                border: selectedPrompt === p ? '2px solid #337AFF' : '1px solid rgba(0,0,0,0.08)',
                                                                background: selectedPrompt === p ? 'rgba(51,122,255,0.08)' : 'rgba(51,122,255,0.025)',
                                                                cursor: 'pointer',
                                                                textAlign: 'left',
                                                                fontSize: '13px',
                                                                color: '#0D1B3E',
                                                                lineHeight: 1.6,
                                                                transition: 'all 0.15s',
                                                                fontFamily: 'inherit',
                                                                minHeight: 'min(88px, 10vh)',
                                                                display: 'flex',
                                                                alignItems: 'center',
                                                            }}
                                                        >
                                                            <span>{renderPromptWithPills(p, promptRefs)}</span>
                                                        </button>
                                                    ))}
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })()}
                            </>
                        )}

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <button onClick={() => setStep(2)} style={secondaryBtnStyle}>{t('onboarding.back')}</button>
                            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                                <button
                                    onClick={handleCreate}
                                    disabled={!selectedProduct || !selectedInfluencer || !selectedPrompt}
                                    style={{
                                        ...primaryBtnStyle,
                                        opacity: (!selectedProduct || !selectedInfluencer || !selectedPrompt) ? 0.5 : 1,
                                        cursor: (!selectedProduct || !selectedInfluencer || !selectedPrompt) ? 'not-allowed' : 'pointer',
                                    }}
                                >
                                    {t('onboarding.createFirst')}
                                </button>
                            </div>
                        </div>
                    </div>
                );

            default: return null;
        }
    };

    return (
        <>
            {/* Backdrop */}
            <div style={{
                position: 'fixed', inset: 0,
                background: 'rgba(0,0,0,0.5)',
                backdropFilter: 'blur(8px)',
                zIndex: 9998,
            }} />
            {/* Modal — content drives the size; 4% padding gutter on all sides via
                an outer flex viewport wrapper, then the modal sits inside it at
                content-natural width/height (capped by the wrapper). */}
            <div style={{
                position: 'fixed', inset: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: '4vh 4vw',
                pointerEvents: 'none',
                zIndex: 9999,
            }}>
                <div style={{
                    width: 'auto',
                    maxWidth: 'min(900px, 100%)',
                    maxHeight: '100%',
                    overflowY: 'auto',
                    background: 'white',
                    borderRadius: '20px',
                    boxShadow: '0 32px 80px rgba(0,0,0,0.25)',
                    animation: 'onboardingScaleIn 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    pointerEvents: 'auto',
                    display: 'flex',
                    flexDirection: 'column',
                }}>
                    {/* Step indicator + skip */}
                    <div style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        position: 'relative',
                        padding: '16px 20px 0',
                    }}>
                        <div style={{ display: 'flex', gap: '4px' }}>
                            {[0, 1, 2, 3].map(i => (
                                <div key={i} style={{
                                    width: step === i ? '24px' : '8px',
                                    height: '4px',
                                    borderRadius: '2px',
                                    background: step === i ? '#337AFF' : 'rgba(0,0,0,0.1)',
                                    transition: 'all 0.3s',
                                }} />
                            ))}
                        </div>
                        <button
                            type="button"
                            onClick={onSkip}
                            style={{
                                position: 'absolute',
                                right: '20px',
                                top: '12px',
                                padding: '4px 8px',
                                border: 'none',
                                background: 'transparent',
                                color: '#8A93B0',
                                fontSize: '13px',
                                fontWeight: 500,
                                cursor: 'pointer',
                                fontFamily: 'inherit',
                                transition: 'color 0.15s',
                            }}
                            onMouseEnter={(e) => { e.currentTarget.style.color = '#337AFF'; }}
                            onMouseLeave={(e) => { e.currentTarget.style.color = '#8A93B0'; }}
                        >
                            {t('onboarding.skip')}
                        </button>
                    </div>
                    {renderStep()}
                </div>
            </div>
            <style>{`
                @keyframes onboardingScaleIn {
                    from { opacity: 0; transform: scale(0.95); }
                    to { opacity: 1; transform: scale(1); }
                }
            `}</style>
        </>
    );
}

/* ── Shared styles ─────────────────────────────────────────────── */

const primaryBtnStyle: React.CSSProperties = {
    padding: '12px 28px',
    borderRadius: '12px',
    border: 'none',
    background: 'linear-gradient(135deg, #337AFF, #6C5CE7)',
    color: 'white',
    fontSize: '14px',
    fontWeight: 700,
    cursor: 'pointer',
    transition: 'all 0.2s',
    boxShadow: '0 4px 16px rgba(51,122,255,0.25)',
    fontFamily: 'inherit',
};

const secondaryBtnStyle: React.CSSProperties = {
    padding: '8px 16px',
    borderRadius: '10px',
    border: 'none',
    background: 'transparent',
    color: '#8A93B0',
    fontSize: '13px',
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: 'inherit',
};

/* ── Sub-components ────────────────────────────────────────────── */

function PickerCard({ selected, onClick, imageUrl, name }: {
    selected: boolean; onClick: () => void; imageUrl: string | null; name: string;
}) {
    return (
        <button
            onClick={onClick}
            style={{
                flex: 1,
                padding: 0,
                borderRadius: '12px',
                border: selected ? '2px solid #337AFF' : '1px solid rgba(0,0,0,0.08)',
                background: selected ? 'rgba(51,122,255,0.04)' : '#f0f0f5',
                cursor: 'pointer',
                textAlign: 'center',
                transition: 'all 0.2s',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                overflow: 'hidden',
                fontFamily: 'inherit',
                position: 'relative',
            }}
        >
            {/* 9:16 portrait image */}
            {imageUrl ? (
                <img
                    src={imageUrl}
                    alt={name}
                    style={{
                        width: '100%',
                        aspectRatio: '9 / 16',
                        objectFit: 'cover',
                        display: 'block',
                    }}
                />
            ) : (
                <div style={{
                    width: '100%',
                    aspectRatio: '9 / 16',
                    background: 'linear-gradient(135deg, #337AFF, #6C5CE7)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: 'white', fontSize: '24px', fontWeight: 700,
                }}>
                    {name.charAt(0).toUpperCase()}
                </div>
            )}
            {/* Name overlay */}
            <div style={{
                position: 'absolute', bottom: 0, left: 0, right: 0,
                padding: '20px 6px 8px',
                background: 'linear-gradient(transparent, rgba(0,0,0,0.65))',
            }}>
                <span style={{ fontSize: '12px', fontWeight: 700, color: 'white' }}>{name}</span>
            </div>
        </button>
    );
}

function ShowcaseVideoCard({ url, label }: { url: string; label: string }) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const [muted, setMuted] = useState(true);

    const toggleMute = () => {
        const v = videoRef.current;
        if (!v) return;
        v.muted = !v.muted;
        setMuted(v.muted);
    };

    return (
        <div style={{
            flex: '0 0 160px',
            borderRadius: '14px',
            overflow: 'hidden',
            border: '1px solid rgba(0,0,0,0.08)',
            position: 'relative',
        }}>
            <video
                ref={videoRef}
                src={url}
                muted
                autoPlay
                loop
                playsInline
                preload="auto"
                style={{
                    width: '160px', height: '284px',
                    objectFit: 'cover',
                    display: 'block',
                }}
            />
            {/* Sound toggle */}
            <button
                onClick={toggleMute}
                style={{
                    position: 'absolute', top: '8px', right: '8px',
                    width: '28px', height: '28px',
                    borderRadius: '50%',
                    border: 'none',
                    background: 'rgba(0,0,0,0.45)',
                    backdropFilter: 'blur(4px)',
                    cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    padding: 0,
                    transition: 'background 0.15s',
                }}
            >
                {muted ? (
                    <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'white', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                        <polygon points="11,5 6,9 2,9 2,15 6,15 11,19" />
                        <line x1="23" y1="9" x2="17" y2="15" />
                        <line x1="17" y1="9" x2="23" y2="15" />
                    </svg>
                ) : (
                    <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'white', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                        <polygon points="11,5 6,9 2,9 2,15 6,15 11,19" />
                        <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
                        <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
                    </svg>
                )}
            </button>
            {/* Label overlay */}
            <div style={{
                position: 'absolute', bottom: 0, left: 0, right: 0,
                padding: '24px 10px 10px',
                background: 'linear-gradient(transparent, rgba(0,0,0,0.7))',
            }}>
                <div style={{ fontSize: '12px', fontWeight: 700, color: 'white' }}>{label}</div>
            </div>
        </div>
    );
}
```

### Layer 3 — i18n EN

**Path:** `frontend/src/locales/en.json` (lines 1166–1190)

```json
  "onboarding.welcomeTitle": "Welcome to Aitoma Studio",
  "onboarding.welcomeSubtitle": "Generate videos, images and full ad campaigns by simply chatting with AI.",
  "onboarding.freeCredits": "100 free credits to start",
  "onboarding.getStarted": "Get started →",
  "onboarding.capabilitiesTitle": "Everything You Need to Scale",
  "onboarding.capabilitiesSubtitle": "From viral TikToks to high-converting ad creatives. Studio handles it all.",
  "onboarding.ugcTitle": "UGC Videos",
  "onboarding.ugcDesc": "AI influencers hold your product, speak your script, and deliver scroll-stopping content.",
  "onboarding.productShotsTitle": "Product Shots",
  "onboarding.productShotsDesc": "Professional product photography powered by AI — studio quality in seconds.",
  "onboarding.cinematicTitle": "Cinematic Ads",
  "onboarding.cinematicDesc": "Premium brand films with cinematic camera movements and visual storytelling.",
  "onboarding.next": "Next →",
  "onboarding.agentTitle": "Meet Your Agent",
  "onboarding.agentDesc": "Type what you want in plain English or Spanish. Your agent automatically handles the scripting, casting, generation, editing and posting.",
  "onboarding.agentExample": "\"Create a UGC ad with Lexi showing my product and saying it's the best new thing for summer\"",
  "onboarding.agentHint": "Use @ to reference your products & influencers.",
  "onboarding.pickTitle": "Let's create your first ad!",
  "onboarding.pickProduct": "Choose a product:",
  "onboarding.pickInfluencer": "Choose an influencer:",
  "onboarding.suggestedPrompts": "Suggested prompts:",
  "onboarding.createFirst": "Create now",
  "onboarding.skip": "Skip for now →",
  "onboarding.step": "Step {current} of {total}",
  "onboarding.back": "← Back",
```

### Layer 3 — i18n ES

**Path:** `frontend/src/locales/es.json` (lines 1166–1190)

```json
  "onboarding.welcomeTitle": "Bienvenido a Aitoma Studio",
  "onboarding.welcomeSubtitle": "Genera videos, imágenes y campañas publicitarias completas simplemente chateando con IA.",
  "onboarding.freeCredits": "100 créditos gratis para empezar",
  "onboarding.getStarted": "Comenzar →",
  "onboarding.capabilitiesTitle": "Todo lo que Necesitas para Escalar",
  "onboarding.capabilitiesSubtitle": "Desde TikToks virales hasta creativos publicitarios de alta conversión. Studio se encarga de todo.",
  "onboarding.ugcTitle": "Videos UGC",
  "onboarding.ugcDesc": "Influencers IA sostienen tu producto, leen tu guión y crean contenido que detiene el scroll.",
  "onboarding.productShotsTitle": "Fotos de Producto",
  "onboarding.productShotsDesc": "Fotografía profesional de producto con IA — calidad de estudio en segundos.",
  "onboarding.cinematicTitle": "Anuncios Cinemáticos",
  "onboarding.cinematicDesc": "Videos de marca premium con movimientos de cámara cinemáticos y narrativa visual.",
  "onboarding.next": "Siguiente →",
  "onboarding.agentTitle": "Conoce a Tu Agente",
  "onboarding.agentDesc": "Escribe lo que quieras en inglés o español. Tu agente se encarga automáticamente del guión, casting, generación, edición y publicación.",
  "onboarding.agentExample": "\"Crea un anuncio UGC con Lexi mostrando mi producto y diciendo que es lo mejor para el verano\"",
  "onboarding.agentHint": "Usa @ para referenciar tus productos e influencers.",
  "onboarding.pickTitle": "¡Vamos a crear tu primer anuncio!",
  "onboarding.pickProduct": "Elige un producto:",
  "onboarding.pickInfluencer": "Elige un influencer:",
  "onboarding.suggestedPrompts": "Prompts sugeridos:",
  "onboarding.createFirst": "Crear ahora",
  "onboarding.skip": "Saltar por ahora →",
  "onboarding.step": "Paso {current} de {total}",
  "onboarding.back": "← Atrás",
```

### Layer 4 — Project launch params

**Path:** `frontend/src/app/projects/[id]/page.tsx` (lines 199–242)

```typescript
    // Capture the auto-submit params ONCE at mount. We immediately strip them
    // from the URL so a browser refresh doesn't re-trigger the initial
    // message send.
    const initialParamsRef = useRef<{ brief: string | null; refs: any; seedance: boolean } | null>(null);
    if (initialParamsRef.current === null) {
        if (searchParams.get('launch') === '1') {
            const draft = consumeAgentLaunchDraft(projectId);
            initialParamsRef.current = draft
                ? {
                    brief: draft.brief,
                    refs: draft.refs?.length ? draft.refs : undefined,
                    seedance: draft.seedance,
                }
                : { brief: null, refs: undefined, seedance: false };
        } else {
            const refsParamRaw = searchParams.get('refs');
            let parsedRefs: any = undefined;
            if (refsParamRaw) {
                try { parsedRefs = JSON.parse(refsParamRaw); } catch { parsedRefs = undefined; }
            }
            initialParamsRef.current = {
                brief: searchParams.get('brief'),
                refs: parsedRefs,
                seedance: searchParams.get('seedance') === '1',
            };
        }
    }
    const initialBrief = initialParamsRef.current.brief;
    const initialRefs = initialParamsRef.current.refs;
    const initialUseSeedance = initialParamsRef.current.seedance;

    useEffect(() => {
        if (!pathname) return;
        const hasAutoSubmitParams =
            searchParams.get('brief')
            || searchParams.get('refs')
            || searchParams.get('seedance')
            || searchParams.get('launch');
        if (hasAutoSubmitParams) {
            router.replace(pathname, { scroll: false });
        }
        // Only run once on mount — we want the cleanup to happen exactly once.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
```

### Layer 4 — AgentPanel props wiring

**Path:** `frontend/src/app/projects/[id]/page.tsx` (lines 1206–1209)

```typescript
                {projectHeaderBar}
                {galleryBlock}
                <AgentPanel ref={agentRef} projectId={projectId} jobId={selectedJobId} onArtifact={refreshGallery} onArtifactPending={addPendingPlaceholder} onArtifactReady={clearOnePlaceholder} onStateChange={setAgentState} initialBrief={initialBrief || undefined} initialRefs={initialRefs} initialUseSeedance={initialUseSeedance} onJobStart={(kind) => { setActiveTab(kind === 'video' ? 'videos' : 'images'); startJobRefetchBurst(); }} onVideoJobStarted={registerVideoJobWatch} />
            </div>
```

### Layer 4 — Agent launch draft

**Path:** `frontend/src/lib/agentLaunchDraft.ts` (full file)

```typescript
import type { AgentRef } from '@/lib/creative-os-api';

export interface AgentLaunchDraft {
    brief: string;
    refs: AgentRef[];
    seedance: boolean;
}

function storageKey(projectId: string): string {
    return `agent-launch:${projectId}`;
}

/** Persist a large agent brief + refs for handoff after project creation. */
export function storeAgentLaunchDraft(projectId: string, draft: AgentLaunchDraft): void {
    if (typeof window === 'undefined') return;
    try {
        sessionStorage.setItem(storageKey(projectId), JSON.stringify(draft));
        const verify = sessionStorage.getItem(storageKey(projectId));
        if (!verify) {
            throw new Error('sessionStorage write failed');
        }
    } catch {
        throw new Error(
            'Could not save launch brief — check browser privacy settings and try again.',
        );
    }
}

/** Read and remove a launch draft (one-time consume on project page mount). */
export function consumeAgentLaunchDraft(projectId: string): AgentLaunchDraft | null {
    if (typeof window === 'undefined') return null;
    try {
        const raw = sessionStorage.getItem(storageKey(projectId));
        sessionStorage.removeItem(storageKey(projectId));
        if (!raw) return null;
        const parsed = JSON.parse(raw) as AgentLaunchDraft;
        if (!parsed?.brief || typeof parsed.brief !== 'string') return null;
        return {
            brief: parsed.brief,
            refs: Array.isArray(parsed.refs) ? parsed.refs : [],
            seedance: Boolean(parsed.seedance),
        };
    } catch {
        return null;
    }
}
```

### Layer 4 — launchCreativeOsProject (not used by onboarding)

**Path:** `frontend/src/lib/launchCreativeOsProject.ts` (full file)

```typescript
import type { AppRouterInstance } from 'next/dist/shared/lib/app-router-context.shared-runtime';
import { storeAgentLaunchDraft } from '@/lib/agentLaunchDraft';
import { creativeFetch, type AgentRef } from '@/lib/creative-os-api';

export interface LaunchCreativeOsProjectOptions {
    brief: string;
    refs?: AgentRef[];
    seedance?: boolean;
}

/**
 * Create a Creative OS project and navigate with prefilled agent brief + @mention refs.
 * Large briefs are stored in sessionStorage — the URL only carries `?launch=1`.
 */
export async function launchCreativeOsProject(
    _router: AppRouterInstance,
    { brief, refs = [], seedance = false }: LaunchCreativeOsProjectOptions,
): Promise<string | null> {
    const trimmed = brief.trim();
    if (!trimmed) return null;

    const nameRes = await creativeFetch<{ name: string }>('/creative-os/projects/generate-name', {
        method: 'POST',
        body: JSON.stringify({ prompt: trimmed }),
    });
    const projectName = nameRes.name || 'New Project';
    const newProject = await creativeFetch<{ id: string }>('/creative-os/projects/', {
        method: 'POST',
        body: JSON.stringify({ name: projectName }),
    });
    if (!newProject?.id) return null;

    const mentionRefs = refs.filter((r) => trimmed.includes(`@${r.tag}`));
    const refsArray = mentionRefs.length > 0 ? mentionRefs : refs;

    storeAgentLaunchDraft(newProject.id, {
        brief: trimmed,
        refs: refsArray,
        seedance,
    });

    try {
        localStorage.setItem('activeProjectId', newProject.id);
    } catch {
        // ignore
    }

    const target = `/projects/${newProject.id}?launch=1`;
    // Hard navigation — soft router.push from Analytics modals is cancelled
    // when PostDetailModal's onClose triggers router.replace on /schedule.
    window.location.assign(target);
    return newProject.id;
}
```

### Layer 4 — AgentPanel: marker sanitization

**Path:** `frontend/src/components/studio/AgentPanel.tsx` (lines 884–905)

```typescript
    // Strip hidden instruction markers from user turns loaded from thread history
    // (e.g. [9:16 vertical], [5s clip duration], [ONBOARDING_FIRST_VIDEO ...])
    // AND scrub leaked technical content from agent turns (AI_EDIT_OPS, JSON ops, tool calls).
    const sanitizeTurns = useCallback((turns: AgentTurn[]): AgentTurn[] => {
        return turns.map((t) => {
            if (t.role === 'user' && t.text) {
                const clean = t.text.replace(/\s*\[[^\]]*\]\s*/g, ' ').trim();
                if (clean !== t.text) return { ...t, text: clean };
            }
            if (t.role === 'agent' && t.text) {
                const clean = scrubAgentText(t.text);
                if (!clean) return { ...t, text: '' };
                if (clean !== t.text) return { ...t, text: clean };
            }
            return t;
        }).filter((t) => {
            // Drop agent turns that are now empty after scrubbing
            // (unless they have artifacts, tool_calls, or a failure notice)
            if (t.role === 'agent' && !t.text && !(t.artifacts?.length) && !(t.tool_calls?.length) && !t.generation_failed) return false;
            return true;
        });
    }, []);
```

### Layer 4 — AgentPanel: auto-submit Phase 1

**Path:** `frontend/src/components/studio/AgentPanel.tsx` (lines 940–973)

```typescript
    // Auto-start: if initialBrief is provided, pre-fill textarea and auto-submit once
    const hasAutoSubmitted = useRef(false);
    const pendingBriefRef = useRef<string | null>(null);
    // Tags seeded from initialRefs (dashboard uploads / pre-populated mentions) —
    // always forwarded regardless of whether @tag appears in the brief text.
    const initialRefTagsRef = useRef<Set<string>>(new Set());
    // Store the actual ref objects from initialRefs so they survive stale closures
    const initialRefsArrayRef = useRef<AgentRef[]>([]);

    // Phase 1: store the brief and pre-fill textarea (runs early)
    useEffect(() => {
        if (!initialBrief || hasAutoSubmitted.current) return;
        hasAutoSubmitted.current = true;
        setBrief(initialBrief);
        pendingBriefRef.current = initialBrief;
        // Force-open in floating mode so the hydration effect runs and Phase 2
        // eventually fires. In embedded mode this is a no-op.
        setOpen(true);
        // Pre-populate activeRefs from initialRefs so handleRun includes them
        if (initialRefs && initialRefs.length > 0) {
            const refMap = new Map<string, AgentRef>();
            const seedTags = new Set<string>();
            for (const r of initialRefs) {
                refMap.set(r.tag, r);
                seedTags.add(r.tag);
            }
            setActiveRefs(refMap);
            initialRefTagsRef.current = seedTags;
            // Store refs in a ref so they survive stale closures in handleRun
            initialRefsArrayRef.current = [...initialRefs];
        }
        console.log('[AgentPanel] Auto-submit: stored pending brief', initialBrief.slice(0, 50), 'refs:', initialRefs?.length ?? 0);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [initialBrief]);
```

### Layer 4 — AgentPanel: display text strip

**Path:** `frontend/src/components/studio/AgentPanel.tsx` (lines 1153–1155)

```typescript
        // Strip hidden instruction markers from the displayed text
        // (e.g. [9:16 vertical], [5s clip duration], [ONBOARDING_FIRST_VIDEO ...])
        const displayText = finalText.replace(/\s*\[[^\]]*\]\s*/g, ' ').trim();
```

### Layer 4 — AgentPanel: auto-submit Phase 2

**Path:** `frontend/src/components/studio/AgentPanel.tsx` (lines 1652–1662)

```typescript
    // Phase 2: fire handleRun AFTER hydration completes (hydrating: true → false)
    // This ensures the panel is fully initialized before auto-submitting.
    useEffect(() => {
        if (hydrating) return; // still hydrating, wait
        if (pendingBriefRef.current) {
            const text = pendingBriefRef.current;
            pendingBriefRef.current = null;
            console.log('[AgentPanel] Auto-submit: firing handleRun with', text.slice(0, 50));
            handleRun(text);
        }
    }, [hydrating, handleRun]);
```

### Layer 5 — Agent onboarding instructions

**Path:** `services/creative-os/routers/agent.py` (lines 894–913)

```python
    # ── Onboarding first video: special handling ──────────────────────────
    is_onboarding = "ONBOARDING_FIRST_VIDEO" in brief
    if is_onboarding:
        onboarding_instructions = (
            "\n\n[ONBOARDING INSTRUCTIONS — CRITICAL]\n"
            "This is the user's very first video from onboarding. Follow these rules EXACTLY:\n"
            "1. DURATION: Use 5 seconds (duration=5). Do NOT use 10s.\n"
            "2. PRODUCT IMAGE: You MUST include the product's image_url in the `reference_image_urls` "
            "array when calling seedance_2_ugc. The product must be VISIBLE in the video. "
            "Include BOTH the influencer image AND the product image as reference images.\n"
            "3. FREE VIDEO: This video costs 0 credits — it is a free welcome gift. "
            "In your confirmation message to the user, explicitly say this video is FREE "
            "and mention they still have all 100 credits to use afterwards. "
            "Do NOT mention any credit cost number.\n"
            "4. SKIP QUESTIONS: Do NOT ask the user about aspect ratio, duration, or any preferences. "
            "Just start generating immediately with 9:16 vertical, 5s, Seedance 2.0.\n"
            "5. CONFIRMATION: Start your response with a brief, enthusiastic confirmation and "
            "immediately call the generation tool. Keep your message short and action-oriented."
        )
        augmented_brief += onboarding_instructions
```

### Layer 5 — Free video credit refund

**Path:** `services/creative-os/routers/generate_video.py` (lines 901–915)

```python
    # ── Onboarding free video: refund credits for the user's first video ──
    # Check if this is the first-ever job in this project. If so, it's the
    # onboarding welcome video and should be free.
    if credit_cost > 0 and data.project_id and _resolve_billing_user_id(user):
        try:
            existing_jobs = await client.list_jobs()
            # Only the job we just created should exist
            if len(existing_jobs or []) <= 1:
                from ugc_db.db_manager import refund_credits
                billing_uid = _resolve_billing_user_id(user)
                refund_credits(billing_uid, credit_cost, {"reason": "onboarding_free_video", "job_id": job_id})
                print(f"[Seedance] Onboarding free video — refunded {credit_cost} credits to {billing_uid}")
                credit_cost = 0
        except Exception as e:
            print(f"[Seedance] WARNING: onboarding refund check failed: {e}")
```
