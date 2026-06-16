/**
 * Shared Supabase auth helpers — validate tokens server-side, refresh on 401,
 * and force re-login when recovery fails (prevents ghost "User" header state).
 */
import { supabase } from '@/lib/supabaseClient';

let reauthing = false;

/** Fast path: read cached session token (may be stale). */
export async function getAccessToken(): Promise<string | null> {
    try {
        const { data: { session } } = await supabase.auth.getSession();
        return session?.access_token ?? null;
    } catch {
        return null;
    }
}

/** Validate with Supabase server; refresh once if the cached JWT is invalid. */
export async function getValidAccessToken(): Promise<string | null> {
    try {
        const { data: { user } } = await supabase.auth.getUser();
        if (user) {
            const { data: { session } } = await supabase.auth.getSession();
            return session?.access_token ?? null;
        }

        const { data: { session } } = await supabase.auth.refreshSession();
        return session?.access_token ?? null;
    } catch {
        return null;
    }
}

/** Clear session and redirect to login — only runs once per page lifecycle. */
export async function forceReauth(reason = 'session_expired'): Promise<void> {
    if (reauthing || typeof window === 'undefined') return;
    reauthing = true;

    try {
        localStorage.removeItem('activeProjectId');
        await supabase.auth.signOut();
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
        const { data: { session } } = await supabase.auth.refreshSession();
        if (session?.access_token) {
            res = await doFetch(session.access_token);
        }
    }

    if (res.status === 401) {
        if (!skipReauth) await forceReauth();
        return { ok: false, status: 401, unauthorized: true, data: null };
    }

    if (!res.ok) {
        return { ok: false, status: res.status, unauthorized: false, data: null };
    }

    const data = await res.json() as T;
    return { ok: true, data, status: res.status };
}
