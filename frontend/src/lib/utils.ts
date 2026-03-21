/**
 * UGC Engine v3 — Utility Functions
 *
 * Clean utility helpers with auth-scoped API calls.
 */

import { supabase } from '@/lib/supabaseClient';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Get the backend API base URL.
 */
export function getApiUrl(): string {
    return API_URL;
}

/**
 * Get the current auth token from Supabase session.
 * Returns the JWT access_token or null if not authenticated.
 */
async function getAuthToken(): Promise<string | null> {
    try {
        const { data: { session } } = await supabase.auth.getSession();
        return session?.access_token ?? null;
    } catch {
        return null;
    }
}

/**
 * Fetch wrapper for backend API calls.
 * Automatically includes the auth token so the backend can scope data by user.
 */
export async function apiFetch<T = unknown>(
    path: string,
    options?: RequestInit
): Promise<T> {
    const method = options?.method?.toUpperCase() || 'GET';
    const headers: Record<string, string> = {};

    // Only add Content-Type for requests that have a body (POST, PUT, PATCH)
    if (method !== 'GET' && method !== 'DELETE') {
        headers['Content-Type'] = 'application/json';
    }

    // Auto-attach auth token
    const token = await getAuthToken();
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    // Send active project ID so the backend scopes assets to the correct project
    if (typeof window !== 'undefined') {
        const projectId = localStorage.getItem('activeProjectId');
        if (projectId) {
            headers['X-Project-Id'] = projectId;
        }
    }

    const res = await fetch(`${API_URL}${path}`, {
        ...options,
        headers: { ...headers, ...options?.headers },
    });
    if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(error.detail || `API error: ${res.status}`);
    }
    return res.json();
}

/**
 * Format a date for display.
 */
export function formatDate(dateStr: string | null | undefined): string {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleString();
}

/**
 * Get a status badge color class.
 */
export function statusColor(status: string): string {
    switch (status) {
        case 'success': return '#22c55e';
        case 'processing': return '#3b82f6';
        case 'pending': return '#f59e0b';
        case 'failed': return '#ef4444';
        default: return '#6b7280';
    }
}
