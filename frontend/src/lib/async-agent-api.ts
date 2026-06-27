/**
 * Async-agent API client (tracer-bullet, Layer 1).
 *
 * Talks to the new /creative-os/async-agent/* router. Fully isolated
 * from creative-os-api.ts so changes to the existing helpers never
 * affect this path. Uses the same Supabase session token and the same
 * NEXT_PUBLIC_CREATIVE_OS_URL env var.
 */
import { fetchWithAuth, getValidAccessToken } from '@/lib/auth';

const CREATIVE_OS_URL = process.env.NEXT_PUBLIC_CREATIVE_OS_URL || 'http://localhost:8001';

async function asyncFetch<T = unknown>(path: string, init?: RequestInit): Promise<T> {
	const accessToken = await getValidAccessToken();
	const result = await fetchWithAuth<T>(`${CREATIVE_OS_URL}${path}`, {
		...init,
		accessToken,
		headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
	});
	if (!result.ok) {
		throw new Error(result.unauthorized
			? 'Session expired. Please sign in again.'
			: `async-agent error: ${result.status}`);
	}
	return result.data;
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
