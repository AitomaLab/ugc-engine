/**
 * Async-agent API client (tracer-bullet, Layer 1).
 *
 * Talks to the new /creative-os/async-agent/* router. Fully isolated
 * from creative-os-api.ts so changes to the existing helpers never
 * affect this path. Uses the same Supabase session token and the same
 * NEXT_PUBLIC_CREATIVE_OS_URL env var.
 */
import { supabase } from '@/lib/supabaseClient';

const CREATIVE_OS_URL = process.env.NEXT_PUBLIC_CREATIVE_OS_URL || 'http://localhost:8001';

async function getAuthToken(): Promise<string | null> {
	try {
		const { data: { session } } = await supabase.auth.getSession();
		return session?.access_token ?? null;
	} catch {
		return null;
	}
}

async function asyncFetch<T = unknown>(path: string, init?: RequestInit): Promise<T> {
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	const token = await getAuthToken();
	if (token) headers['Authorization'] = `Bearer ${token}`;
	const res = await fetch(`${CREATIVE_OS_URL}${path}`, {
		...init,
		headers: { ...headers, ...(init?.headers || {}) },
	});
	if (!res.ok) {
		const body = await res.json().catch(() => ({ detail: res.statusText }));
		throw new Error(body.detail || `async-agent error: ${res.status}`);
	}
	return res.json() as Promise<T>;
}

export type AsyncJobStatus = 'dispatched' | 'running' | 'finishing' | 'success' | 'failed' | 'cancelled';

export interface AsyncImageJob {
	id: string;
	prompt: string;
	status: AsyncJobStatus;
	image_url?: string | null;
	error?: string | null;
	created_at: string;
	updated_at: string;
	kie_task_id?: string | null;
}

export interface DispatchImageResult {
	job_id: string;
	status: AsyncJobStatus;
	kie_task_id: string;
	agent_text: string;
}

export async function dispatchImage(opts: {
	projectId: string;
	prompt: string;
	imageInput?: string[];
	aspectRatio?: '9:16' | '16:9' | '1:1';
}): Promise<DispatchImageResult> {
	return asyncFetch<DispatchImageResult>('/creative-os/async-agent/dispatch-image', {
		method: 'POST',
		body: JSON.stringify({
			project_id: opts.projectId,
			prompt: opts.prompt,
			image_input: opts.imageInput,
			aspect_ratio: opts.aspectRatio || '9:16',
		}),
	});
}

export async function cancelImageJob(jobId: string): Promise<{ job_id: string; status: AsyncJobStatus }> {
	return asyncFetch(`/creative-os/async-agent/jobs/${jobId}/cancel`, { method: 'POST' });
}

export async function listImageJobs(projectId: string): Promise<{ image_jobs: AsyncImageJob[] }> {
	return asyncFetch(`/creative-os/async-agent/jobs?project_id=${encodeURIComponent(projectId)}`);
}

export async function asyncAgentHealth(): Promise<boolean> {
	try {
		const res = await fetch(`${CREATIVE_OS_URL}/creative-os/async-agent/health`);
		return res.ok;
	} catch {
		return false;
	}
}
