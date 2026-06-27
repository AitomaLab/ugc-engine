/**
 * Shared Supabase auth helpers — validate tokens server-side, refresh on 401,
 * and force re-login when recovery fails (prevents ghost "User" header state).
 */
import type { Session } from '@supabase/supabase-js';
import { supabase, clearAllAuthState } from '@/lib/supabaseClient';

let reauthing = false;
let refreshInFlight: Promise<Session | null> | null = null;
let tokenInFlight: Promise<string | null> | null = null;
let consecutiveAuthFailures = 0;

/** Cached access token from a recent successful validation. */
let cachedAccessToken: string | null = null;
let cachedTokenValidUntil = 0;

const AUTH_FAILURE_THRESHOLD = 2;
const REFRESH_RETRY_ATTEMPTS = 3;
const REFRESH_RETRY_DELAY_MS = 400;
/** Reuse session token without network validation for this long. */
const TOKEN_CACHE_TTL_MS = 60_000;
/** Refresh proactively when JWT expires within this window. */
const TOKEN_EXPIRY_BUFFER_SEC = 60;

function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function decodeJwtExp(token: string): number | null {
    try {
        const payloadB64 = token.split('.')[1];
        if (!payloadB64) return null;
        const padding = '='.repeat((4 - (payloadB64.length % 4)) % 4);
        const json = atob(payloadB64.replace(/-/g, '+').replace(/_/g, '/') + padding);
        const exp = JSON.parse(json).exp;
        return typeof exp === 'number' ? exp : null;
    } catch {
        return null;
    }
}

function isTokenFreshEnough(token: string): boolean {
    const exp = decodeJwtExp(token);
    if (!exp) return true;
    return exp - TOKEN_EXPIRY_BUFFER_SEC > Date.now() / 1000;
}

function setTokenCache(token: string): void {
    cachedAccessToken = token;
    const exp = decodeJwtExp(token);
    const expMs = exp ? exp * 1000 : Date.now() + TOKEN_CACHE_TTL_MS;
    cachedTokenValidUntil = Math.min(Date.now() + TOKEN_CACHE_TTL_MS, expMs - TOKEN_EXPIRY_BUFFER_SEC * 1000);
}

function clearTokenCache(): void {
    cachedAccessToken = null;
    cachedTokenValidUntil = 0;
}

/** Only one refreshSession() at a time — prevents rotation races on tab resume. */
export async function refreshSessionOnce(): Promise<Session | null> {
    if (refreshInFlight) return refreshInFlight;

    refreshInFlight = (async () => {
        for (let attempt = 1; attempt <= REFRESH_RETRY_ATTEMPTS; attempt++) {
            try {
                const { data: { session }, error } = await supabase.auth.refreshSession();
                if (session?.access_token) {
                    setTokenCache(session.access_token);
                    return session;
                }
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
 * Coalesces concurrent callers onto one validation pass.
 */
export async function waitForFreshSession(): Promise<string | null> {
    return getValidAccessToken({ forceValidate: true });
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

type GetTokenOptions = {
    /** Skip in-memory cache and validate with Supabase (network). */
    forceValidate?: boolean;
};

/**
 * Return a usable access token. Fast path reads local session cookies;
 * slow path validates with Supabase only on cold start, near-expiry, or
 * when forceValidate is set. Concurrent callers share one in-flight promise.
 */
export async function getValidAccessToken(options?: GetTokenOptions): Promise<string | null> {
    const forceValidate = options?.forceValidate ?? false;

    if (!forceValidate && cachedAccessToken && Date.now() < cachedTokenValidUntil) {
        return cachedAccessToken;
    }

    if (tokenInFlight) return tokenInFlight;

    tokenInFlight = (async () => {
        for (let attempt = 1; attempt <= REFRESH_RETRY_ATTEMPTS; attempt++) {
            try {
                const { data: { session } } = await supabase.auth.getSession();
                const sessionToken = session?.access_token ?? null;

                if (sessionToken && !forceValidate && isTokenFreshEnough(sessionToken)) {
                    consecutiveAuthFailures = 0;
                    setTokenCache(sessionToken);
                    return sessionToken;
                }

                if (forceValidate || !sessionToken || !isTokenFreshEnough(sessionToken ?? '')) {
                    const { data: { user } } = await supabase.auth.getUser();
                    if (user) {
                        const { data: { session: freshSession } } = await supabase.auth.getSession();
                        if (freshSession?.access_token) {
                            consecutiveAuthFailures = 0;
                            setTokenCache(freshSession.access_token);
                            return freshSession.access_token;
                        }
                    }
                }

                const refreshed = await refreshSessionOnce();
                if (refreshed?.access_token) {
                    consecutiveAuthFailures = 0;
                    return refreshed.access_token;
                }
            } catch {
                // fall through to retry
            }

            if (attempt < REFRESH_RETRY_ATTEMPTS) {
                await sleep(REFRESH_RETRY_DELAY_MS * attempt);
            }
        }

        clearTokenCache();
        return null;
    })().finally(() => {
        tokenInFlight = null;
    });

    return tokenInFlight;
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

    clearTokenCache();

    // Last-chance refresh before signing out
    const recovered = await refreshSessionOnce();
    if (recovered?.access_token) {
        resetAuthFailures();
        return;
    }

    if (!recordAuthFailure()) return;

    reauthing = true;

    try {
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
 * Pass `accessToken` when the caller already acquired a token (avoids duplicate auth).
 */
export async function fetchWithAuth<T = unknown>(
    url: string,
    options?: RequestInit & { skipReauth?: boolean; accessToken?: string | null },
): Promise<FetchWithAuthResult<T>> {
    const { skipReauth, accessToken: providedToken, ...fetchOptions } = options ?? {};

    let token = providedToken ?? await getValidAccessToken();
    if (!token) {
        if (!skipReauth) await forceReauth();
        return { ok: false, status: 401, unauthorized: true, data: null };
    }

    const doFetch = async (tok: string): Promise<Response> => {
        const headers = new Headers(fetchOptions.headers);
        headers.set('Authorization', `Bearer ${tok}`);
        return fetch(url, { ...fetchOptions, headers });
    };

    let res = await doFetch(token);

    if (res.status === 401) {
        clearTokenCache();
        const session = await refreshSessionOnce();
        if (session?.access_token) {
            token = session.access_token;
            res = await doFetch(session.access_token);
        } else {
            const recovered = await getValidAccessToken({ forceValidate: true });
            if (recovered) {
                token = recovered;
                res = await doFetch(recovered);
            }
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
