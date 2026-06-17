import { supabase } from '@/lib/supabaseClient';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function adminFetch<T>(path: string, init?: RequestInit): Promise<T> {
    const token = (await supabase.auth.getSession()).data.session?.access_token;
    const headers: Record<string, string> = {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers as Record<string, string> | undefined),
    };
    if (!(init?.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }
    const res = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers,
    });
    const text = await res.text();
    const json = text ? JSON.parse(text) : {};
    if (!res.ok) {
        throw new Error((json as { detail?: string })?.detail || `Request failed (${res.status})`);
    }
    return json as T;
}

export const ADMIN_PRIMARY = '#337AFF';
