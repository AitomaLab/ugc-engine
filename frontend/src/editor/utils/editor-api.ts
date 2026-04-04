/**
 * Authenticated fetch wrapper for editor API calls.
 * Uses the main app's apiFetch to call the backend directly with the
 * Supabase auth token, instead of going through Next.js proxy routes.
 */
import { apiFetch, getApiUrl } from '@/lib/utils';

/**
 * Fetch a presigned upload URL from the editor API.
 */
export async function editorFetchUploadUrl(body: {
	contentType: string;
	size: number;
}): Promise<Response> {
	const API_URL = getApiUrl();
	const { supabase } = await import('@/lib/supabaseClient');
	const { data: { session } } = await supabase.auth.getSession();
	const token = session?.access_token;

	return fetch(`${API_URL}/api/editor/upload-url`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			...(token ? { Authorization: `Bearer ${token}` } : {}),
		},
		body: JSON.stringify({
			filename: body.contentType ? `upload.${body.contentType.split('/')[1]}` : 'upload.bin',
			contentType: body.contentType || 'application/octet-stream',
			size: body.size || 0,
		}),
	});
}

/**
 * Call the captions endpoint on the backend.
 */
export async function editorFetchCaptions(body: {
	fileKey: string;
}): Promise<Response> {
	const API_URL = getApiUrl();
	const { supabase } = await import('@/lib/supabaseClient');
	const { data: { session } } = await supabase.auth.getSession();
	const token = session?.access_token;

	return fetch(`${API_URL}/api/editor/captions`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			...(token ? { Authorization: `Bearer ${token}` } : {}),
		},
		body: JSON.stringify(body),
	});
}

/**
 * Trigger an editor render on the backend.
 */
export async function editorFetchRender(body: Record<string, unknown>): Promise<Response> {
	const API_URL = getApiUrl();
	const { supabase } = await import('@/lib/supabaseClient');
	const { data: { session } } = await supabase.auth.getSession();
	const token = session?.access_token;

	return fetch(`${API_URL}/api/editor/render`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			...(token ? { Authorization: `Bearer ${token}` } : {}),
		},
		body: JSON.stringify(body),
	});
}

/**
 * Poll render progress from the backend.
 */
export async function editorFetchProgress(
	body: Record<string, unknown>,
	signal?: AbortSignal,
): Promise<Response> {
	const API_URL = getApiUrl();
	const { supabase } = await import('@/lib/supabaseClient');
	const { data: { session } } = await supabase.auth.getSession();
	const token = session?.access_token;

	return fetch(`${API_URL}/api/editor/render/${(body as any).renderId}/progress`, {
		method: 'GET',
		headers: {
			...(token ? { Authorization: `Bearer ${token}` } : {}),
		},
		signal,
	});
}
