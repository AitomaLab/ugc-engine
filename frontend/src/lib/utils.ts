/**
 * UGC Engine v3 — Utility Functions
 *
 * Clean utility helpers. No more proxy hacks — Supabase Storage provides
 * direct, public URLs for all assets.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Get the backend API base URL.
 */
export function getApiUrl(): string {
    return API_URL;
}

/**
 * Fetch wrapper for backend API calls.
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
