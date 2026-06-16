/**
 * UGC Engine v3 — Supabase Client (Cookie-based)
 *
 * Uses @supabase/ssr's createBrowserClient which stores auth tokens
 * in cookies instead of localStorage. This is required for the
 * Next.js middleware to detect the session on the server side.
 */
import { createBrowserClient } from '@supabase/ssr';

const supabaseUrl =
	process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://placeholder.supabase.co';
const supabaseAnonKey =
	process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'placeholder-anon-key';

export const supabase = createBrowserClient(supabaseUrl, supabaseAnonKey);

/**
 * Hard-clear every Supabase auth artifact from the browser.
 *
 * Use this on sign-out (and before re-login) to recover from cases where
 * @supabase/ssr leaves chunked cookies behind, the refresh token is missing
 * (`Invalid Refresh Token: Refresh Token Not Found`), or the access-token
 * cookie persists past `signOut()` and traps the middleware in a redirect
 * loop. `supabase.auth.signOut()` is best-effort here — we ignore failures
 * so a corrupt session can't block the redirect.
 */
export async function clearAllAuthState(): Promise<void> {
	if (typeof window === 'undefined') return;

	try {
		await supabase.auth.signOut({ scope: 'local' });
	} catch {
		// Network or "no session" errors are expected when state is already
		// partially gone — keep going.
	}

	const cookieKeyMatchers = [/^sb-/, /supabase\.auth/i];
	for (const raw of document.cookie.split(';')) {
		const name = raw.split('=')[0]?.trim();
		if (!name) continue;
		if (!cookieKeyMatchers.some((re) => re.test(name))) continue;
		// Delete on every plausible path / domain combination.
		const host = window.location.hostname;
		const domains = [host, `.${host}`, ''];
		const paths = ['/', '/login', '/signup'];
		for (const domain of domains) {
			for (const path of paths) {
				const domainAttr = domain ? `; domain=${domain}` : '';
				document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=${path}${domainAttr}`;
			}
		}
	}

	try {
		for (let i = window.localStorage.length - 1; i >= 0; i--) {
			const key = window.localStorage.key(i);
			if (key && (key.startsWith('sb-') || key.includes('supabase.auth'))) {
				window.localStorage.removeItem(key);
			}
		}
		for (let i = window.sessionStorage.length - 1; i >= 0; i--) {
			const key = window.sessionStorage.key(i);
			if (key && (key.startsWith('sb-') || key.includes('supabase.auth'))) {
				window.sessionStorage.removeItem(key);
			}
		}
	} catch {
		// Storage may be unavailable (Safari private mode, etc.) — ignore.
	}
}
