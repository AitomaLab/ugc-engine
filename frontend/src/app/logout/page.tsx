'use client';

/**
 * Safety-valve logout route.
 *
 * Navigate to `/logout` from any page (e.g. paste it in the address bar) to
 * forcibly clear every Supabase auth artifact — cookies, localStorage, and
 * the in-memory session — and bounce to /login. Useful when the header
 * dropdown is unreachable or a corrupt session is trapping the user.
 */
import { useEffect } from 'react';
import { clearAllAuthState } from '@/lib/supabaseClient';

export default function LogoutPage() {
    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                await clearAllAuthState();
            } finally {
                if (!cancelled) window.location.replace('/login');
            }
        })();
        return () => {
            cancelled = true;
        };
    }, []);

    return (
        <div
            style={{
                minHeight: '100vh',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#6b7280',
                fontSize: 14,
            }}
        >
            Signing you out…
        </div>
    );
}
