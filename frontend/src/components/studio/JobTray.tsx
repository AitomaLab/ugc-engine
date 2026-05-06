'use client';

/**
 * JobTray — renders the active async image jobs for a project.
 *
 * Hydrates from /creative-os/async-agent/jobs on mount, then subscribes
 * to Supabase Realtime on `async_image_jobs` for INSERT/UPDATE rows
 * scoped to the current project. Each tile shows status, prompt, and
 * cancel/retry controls. On success the tile flips to a thumbnail.
 *
 * Tracer-bullet scope: image jobs only. async_video_jobs lands in Layer 2.
 */
import { useEffect, useMemo, useState } from 'react';
import { supabase } from '@/lib/supabaseClient';
import {
	cancelImageJob,
	listImageJobs,
	type AsyncImageJob,
	type AsyncJobStatus,
} from '@/lib/async-agent-api';

interface JobTrayProps {
	projectId: string;
	/** Called when a job reaches a terminal state, so the parent can react (e.g. swap a chat-bubble placeholder). */
	onJobTerminal?: (job: AsyncImageJob) => void;
}

const TERMINAL: AsyncJobStatus[] = ['success', 'failed', 'cancelled'];

function statusLabel(s: AsyncJobStatus): string {
	switch (s) {
		case 'dispatched': return 'Queued';
		case 'running':    return 'Generating';
		case 'finishing':  return 'Finishing';
		case 'success':    return 'Ready';
		case 'failed':     return 'Failed';
		case 'cancelled':  return 'Cancelled';
	}
}

function statusTone(s: AsyncJobStatus): string {
	if (s === 'success')   return 'bg-emerald-500/15 text-emerald-300';
	if (s === 'failed')    return 'bg-red-500/15 text-red-300';
	if (s === 'cancelled') return 'bg-zinc-500/15 text-zinc-300';
	return 'bg-sky-500/15 text-sky-300';
}

export function JobTray({ projectId, onJobTerminal }: JobTrayProps) {
	const [jobs, setJobs] = useState<AsyncImageJob[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	// 1) Hydrate from REST on mount or when projectId changes.
	useEffect(() => {
		let cancelled = false;
		setLoading(true);
		setError(null);
		listImageJobs(projectId)
			.then((res) => {
				if (cancelled) return;
				setJobs(res.image_jobs || []);
			})
			.catch((e) => {
				if (cancelled) return;
				setError(e?.message || 'Failed to load jobs');
			})
			.finally(() => !cancelled && setLoading(false));
		return () => { cancelled = true; };
	}, [projectId]);

	// 2) Subscribe to Realtime updates for this project's image jobs.
	useEffect(() => {
		const channel = supabase
			.channel(`async_image_jobs:${projectId}`)
			.on(
				'postgres_changes',
				{
					event: '*',
					schema: 'public',
					table: 'async_image_jobs',
					filter: `project_id=eq.${projectId}`,
				},
				(payload) => {
					const next = (payload.new as AsyncImageJob) || (payload.old as AsyncImageJob);
					if (!next?.id) return;
					setJobs((prev) => {
						const idx = prev.findIndex((j) => j.id === next.id);
						if (payload.eventType === 'DELETE') {
							return idx >= 0 ? prev.filter((_, i) => i !== idx) : prev;
						}
						if (idx >= 0) {
							const merged = { ...prev[idx], ...next } as AsyncImageJob;
							const updated = [...prev];
							updated[idx] = merged;
							if (TERMINAL.includes(merged.status) && !TERMINAL.includes(prev[idx].status)) {
								onJobTerminal?.(merged);
							}
							return updated;
						}
						return [next as AsyncImageJob, ...prev];
					});
				},
			)
			.subscribe();
		return () => { supabase.removeChannel(channel); };
	}, [projectId, onJobTerminal]);

	const active = useMemo(
		() => jobs.filter((j) => !TERMINAL.includes(j.status)),
		[jobs],
	);
	const recent = useMemo(
		() => jobs.filter((j) => TERMINAL.includes(j.status)).slice(0, 6),
		[jobs],
	);

	const handleCancel = async (jobId: string) => {
		try {
			await cancelImageJob(jobId);
		} catch (e: any) {
			setError(e?.message || 'Cancel failed');
		}
	};

	if (loading && jobs.length === 0) {
		return <div className="text-sm text-zinc-500">Loading jobs…</div>;
	}

	return (
		<div className="space-y-3">
			{error && (
				<div className="text-xs text-red-400">{error}</div>
			)}

			{active.length > 0 && (
				<div>
					<div className="mb-1 text-xs uppercase tracking-wide text-zinc-500">In progress</div>
					<div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
						{active.map((j) => (
							<TileLoading key={j.id} job={j} onCancel={handleCancel} />
						))}
					</div>
				</div>
			)}

			{recent.length > 0 && (
				<div>
					<div className="mb-1 text-xs uppercase tracking-wide text-zinc-500">Recent</div>
					<div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
						{recent.map((j) => (
							<TileTerminal key={j.id} job={j} />
						))}
					</div>
				</div>
			)}

			{active.length === 0 && recent.length === 0 && (
				<div className="text-sm text-zinc-500">No image jobs yet for this project.</div>
			)}
		</div>
	);
}

function TileShell({
	children,
	tone,
}: {
	children: React.ReactNode;
	tone: string;
}) {
	return (
		<div className={`relative overflow-hidden rounded-md border border-zinc-800 bg-zinc-900 ${tone}`}>
			{children}
		</div>
	);
}

function TileLoading({ job, onCancel }: { job: AsyncImageJob; onCancel: (id: string) => void }) {
	return (
		<TileShell tone="">
			<div className="aspect-square w-full animate-pulse bg-zinc-800" />
			<div className="space-y-1 p-2">
				<div className="line-clamp-2 text-xs text-zinc-300">{job.prompt}</div>
				<div className="flex items-center justify-between">
					<span className={`rounded px-1.5 py-0.5 text-[10px] ${statusTone(job.status)}`}>
						{statusLabel(job.status)}
					</span>
					<button
						className="text-[10px] text-zinc-400 hover:text-zinc-200"
						onClick={() => onCancel(job.id)}
					>
						Cancel
					</button>
				</div>
			</div>
		</TileShell>
	);
}

function TileTerminal({ job }: { job: AsyncImageJob }) {
	return (
		<TileShell tone="">
			{job.status === 'success' && job.image_url ? (
				<img
					src={job.image_url}
					alt={job.prompt}
					className="aspect-square w-full object-cover"
					loading="lazy"
				/>
			) : (
				<div className="flex aspect-square w-full items-center justify-center bg-zinc-800 text-xs text-zinc-500">
					{job.status === 'failed' && (job.error || 'Failed')}
					{job.status === 'cancelled' && 'Cancelled'}
				</div>
			)}
			<div className="space-y-1 p-2">
				<div className="line-clamp-2 text-xs text-zinc-300">{job.prompt}</div>
				<span className={`rounded px-1.5 py-0.5 text-[10px] ${statusTone(job.status)}`}>
					{statusLabel(job.status)}
				</span>
			</div>
		</TileShell>
	);
}
