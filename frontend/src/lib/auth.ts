/**
 * Shared Supabase auth helpers — validate tokens server-side, refresh on 401,
 * and force re-login when recovery fails (prevents ghost "User" header state).
 */
import type { Session } from '@supabase/supabase-js';
import { supabase, clearAllAuthState } from '@/lib/supabaseClient';

let reauthing = false;
let refreshInFlight: Promise<Session | null> | null = null;
let sessionReadyPromise: Promise<string | null> | null = null;
let consecutiveAuthFailures = 0;

const AUTH_FAILURE_THRESHOLD = 2;
const REFRESH_RETRY_ATTEMPTS = 3;
const REFRESH_RETRY_DELAY_MS = 400;

function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Only one refreshSession() at a time — prevents rotation races on tab resume. */
export async function refreshSessionOnce(): Promise<Session | null> {
    if (refreshInFlight) return refreshInFlight;

    refreshInFlight = (async () => {
        for (let attempt = 1; attempt <= REFRESH_RETRY_ATTEMPTS; attempt++) {
            try {
                const { data: { session }, error } = await supabase.auth.refreshSession();
                if (session) return session;
                if (error && attempt < REFRESH_RETRY_ATTEMPTS) {
                    await sleep(REFRESH_RETRY_DELAY_MS * attempt);
                    continue;
                }
                return null;
            } catch {
                if (attempt < REFRESH_RETRY_ATTEMPTS) {
                    await sleep(REFRESH_RETRY_DELAY_MS * attempt);
                    continue;
                }
                return null;
            }
        }
        return null;
    })().finally(() => {
        refreshInFlight = null;
    });

    return refreshInFlight;
}

/**
 * Await a fresh access token before focus-time API bursts (SWR, visibility refetch).
 * Coalesces concurrent callers onto one refresh/validation pass.
 */
export async function waitForFreshSession(): Promise<string | null> {
    if (sessionReadyPromise) return sessionReadyPromise;

    sessionReadyPromise = (async () => {
        const token = await getValidAccessToken();
        return token;
    })().finally(() => {
        sessionReadyPromise = null;
    });

    return sessionReadyPromise;
}

/** Fast path: read cached session token (may be stale). */
export async function getAccessToken(): Promise<string | null> {
    try {
        const { data: { session } } = await supabase.auth.getSession();
        return session?.access_token ?? null;
    } catch {
        return null;
    }
}

/** Validate with Supabase server; refresh with mutex if the cached JWT is invalid. */
export async function getValidAccessToken(): Promise<string | null> {
    for (let attempt = 1; attempt <= REFRESH_RETRY_ATTEMPTS; attempt++) {
        try {
            const { data: { user } } = await supabase.auth.getUser();
            if (user) {
                const { data: { session } } = await supabase.auth.getSession();
                if (session?.access_token) {
                    consecutiveAuthFailures = 0;
                    return session.access_token;
                }
            }

            const session = await refreshSessionOnce();
            if (session?.access_token) {
                consecutiveAuthFailures = 0;
                return session.access_token;
            }
        } catch {
            // fall through to retry
        }

        if (attempt < REFRESH_RETRY_ATTEMPTS) {
            await sleep(REFRESH_RETRY_DELAY_MS * attempt);
        }
    }

    return null;
}

function recordAuthFailure(): boolean {
    consecutiveAuthFailures += 1;
    return consecutiveAuthFailures >= AUTH_FAILURE_THRESHOLD;
}

function resetAuthFailures(): void {
    consecutiveAuthFailures = 0;
}

/** Clear session and redirect to login — only runs once per page lifecycle. */
export async function forceReauth(reason = 'session_expired'): Promise<void> {
    if (reauthing || typeof window === 'undefined') return;

    // Last-chance refresh before signing out
    const recovered = await refreshSessionOnce();
    if (recovered?.access_token) {
        resetAuthFailures();
        return;
    }

    if (!recordAuthFailure()) return;

    reauthing = true;

    try {
        localStorage.removeItem('activeProjectId');
        await clearAllAuthState();
    } catch {
        // Still redirect even if signOut fails
    }

    const params = new URLSearchParams({ reason });
    const redirectTo = window.location.pathname + window.location.search;
    if (redirectTo && redirectTo !== '/login') {
        params.set('redirectTo', redirectTo);
    }
    window.location.href = `/login?${params.toString()}`;
}

export type FetchWithAuthResult<T> =
    | { ok: true; data: T; status: number }
    | { ok: false; status: number; unauthorized: boolean; data: null };

/**
 * Fetch with Bearer token. On 401, attempts one refresh + retry.
 * On persistent 401, calls forceReauth() unless skipReauth is set.
 */
export async function fetchWithAuth<T = unknown>(
    url: string,
    options?: RequestInit & { skipReauth?: boolean },
): Promise<FetchWithAuthResult<T>> {
    const { skipReauth, ...fetchOptions } = options ?? {};

    let token = await getValidAccessToken();
    if (!token) {
        if (!skipReauth) await forceReauth();
        return { ok: false, status: 401, unauthorized: true, data: null };
    }

    const doFetch = async (accessToken: string): Promise<Response> => {
        const headers = new Headers(fetchOptions.headers);
        headers.set('Authorization', `Bearer ${accessToken}`);
        return fetch(url, { ...fetchOptions, headers });
    };

    let res = await doFetch(token);

    if (res.status === 401) {
        const session = await refreshSessionOnce();
        if (session?.access_token) {
            token = session.access_token;
            res = await doFetch(session.access_token);
        }
    }

    if (res.status === 401) {
        if (!skipReauth) {
            await forceReauth();
        }
        return { ok: false, status: 401, unauthorized: true, data: null };
    }

    resetAuthFailures();

    if (!res.ok) {
        return { ok: false, status: res.status, unauthorized: false, data: null };
    }

    const data = await res.json() as T;
    return { ok: true, data, status: res.status };
}
