/**
 * UGC Engine v3 — Utility Functions
 *
 * Clean utility helpers with auth-scoped API calls.
 */

import { fetchWithAuth, getValidAccessToken } from '@/lib/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/** Shared with i18n.tsx — persisted UI language for API + AI locale. */
export const UI_LANGUAGE_STORAGE_KEY = 'aitoma_ui_language';

function getUiLanguageHeader(): string {
    if (typeof window === 'undefined') return 'en';
    try {
        const stored = localStorage.getItem(UI_LANGUAGE_STORAGE_KEY);
        return stored === 'es' ? 'es' : 'en';
    } catch {
        return 'en';
    }
}

/**
 * Get the backend API base URL.
 */
export function getApiUrl(): string {
    return API_URL;
}

/** Lowercase slug for deduping influencer names in UI lists. */
export function slugifyName(s: string): string {
    return (s || '').toLowerCase().trim().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
}

/**
 * Collapse duplicate influencer rows that share the same name within a project.
 * Prefers the row with an image_url when duplicates exist (matches AgentPanel).
 */
export function dedupeInfluencersByName<T extends { name?: string | null; image_url?: string | null }>(
    rows: T[],
): T[] {
    const byTag = new Map<string, T>();
    for (const row of rows) {
        const tag = slugifyName(row.name || '');
        if (!tag) continue;
        const prev = byTag.get(tag);
        if (!prev) {
            byTag.set(tag, row);
            continue;
        }
        const prevImg = prev.image_url?.trim();
        const rowImg = row.image_url?.trim();
        if (!prevImg && rowImg) {
            byTag.set(tag, row);
        }
    }
    return Array.from(byTag.values());
}

/**
 * Fetch wrapper for backend API calls.
 * Automatically includes the auth token so the backend can scope data by user.
 */
export async function apiFetch<T = unknown>(
    path: string,
    options?: RequestInit & { skipProjectScope?: boolean }
): Promise<T> {
    const method = options?.method?.toUpperCase() || 'GET';
    const headers: Record<string, string> = {};

    // Only add Content-Type for requests that have a body (POST, PUT, PATCH).
    // Skip when body is FormData — the browser sets multipart/form-data with
    // the correct boundary, and overriding it breaks the upload.
    const isFormData = typeof FormData !== 'undefined' && options?.body instanceof FormData;
    if (method !== 'GET' && method !== 'DELETE' && !isFormData) {
        headers['Content-Type'] = 'application/json';
    }

    // Send active project ID so the backend scopes assets to the correct project.
    // Callers that need data across all projects (dashboard aggregations) can
    // opt out via { skipProjectScope: true } — we send an explicit skip header
    // so the backend doesn't silently fall back to the user's default project.
    if (typeof window !== 'undefined') {
        headers['X-Ui-Language'] = getUiLanguageHeader();
        if (options?.skipProjectScope) {
            headers['X-Skip-Project-Scope'] = '1';
        } else {
            const projectId = localStorage.getItem('activeProjectId');
            if (projectId) {
                headers['X-Project-Id'] = projectId;
            }
        }
    }

    const accessToken = await getValidAccessToken();

    const result = await fetchWithAuth<T>(`${API_URL}${path}`, {
        ...options,
        accessToken,
        headers: { ...headers, ...options?.headers },
    });
    if (!result.ok) {
        throw new Error(result.unauthorized
            ? 'Session expired. Please sign in again.'
            : `API error: ${result.status}`);
    }
    return result.data;
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
