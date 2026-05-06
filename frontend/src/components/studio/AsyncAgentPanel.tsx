'use client';

/**
 * AsyncAgentPanel — tracer-bullet (Layer 1).
 *
 * Self-contained UI that proves the fire-and-return architecture:
 *   1. user types a prompt
 *   2. we call /creative-os/async-agent/dispatch-image (returns in ~1-3s)
 *   3. agent_text appears in the chat as the agent's reply
 *   4. a placeholder card renders next to the reply with the job_id
 *   5. JobTray below shows the same job's tile
 *   6. Realtime row update on async_image_jobs flips placeholder + tile
 *      to the real thumbnail (or to a failure card)
 *
 * The composer never disables. Sending a second prompt while the first
 * job is still running is allowed — both proceed in parallel.
 *
 * This is intentionally minimal. The full UX (mention picker, attachments,
 * Seedance toggle, etc.) ports over after the architecture is validated.
 */

import { useCallback, useState } from 'react';
import {
	dispatchImage,
	type AsyncImageJob,
	type DispatchImageResult,
} from '@/lib/async-agent-api';
import { JobTray } from '@/components/studio/JobTray';

interface AsyncAgentPanelProps {
	projectId: string;
}

interface ChatMessage {
	id: string;
	role: 'user' | 'agent';
	text: string;
	jobId?: string;
	imageUrl?: string | null;
	failed?: boolean;
}

export function AsyncAgentPanel({ projectId }: AsyncAgentPanelProps) {
	const [brief, setBrief] = useState('');
	const [messages, setMessages] = useState<ChatMessage[]>([]);
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const send = useCallback(async () => {
		const prompt = brief.trim();
		if (!prompt) return;
		setError(null);
		setSubmitting(true);
		const userMsg: ChatMessage = {
			id: `u-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
			role: 'user',
			text: prompt,
		};
		setMessages((m) => [...m, userMsg]);
		setBrief('');

		try {
			const res: DispatchImageResult = await dispatchImage({
				projectId,
				prompt,
				aspectRatio: '9:16',
			});
			const agentMsg: ChatMessage = {
				id: `a-${res.job_id}`,
				role: 'agent',
				text: res.agent_text,
				jobId: res.job_id,
			};
			setMessages((m) => [...m, agentMsg]);
		} catch (e: any) {
			setError(e?.message || 'Dispatch failed');
			setMessages((m) => [
				...m,
				{
					id: `e-${Date.now()}`,
					role: 'agent',
					text: 'Sorry — that failed. Try again?',
					failed: true,
				},
			]);
		} finally {
			setSubmitting(false);
		}
	}, [brief, projectId]);

	const onJobTerminal = useCallback((job: AsyncImageJob) => {
		setMessages((prev) =>
			prev.map((m) => {
				if (m.jobId !== job.id) return m;
				if (job.status === 'success' && job.image_url) {
					return { ...m, imageUrl: job.image_url };
				}
				if (job.status === 'failed') {
					return { ...m, text: `Failed: ${job.error || 'unknown error'}`, failed: true };
				}
				if (job.status === 'cancelled') {
					return { ...m, text: 'Cancelled.', failed: true };
				}
				return m;
			}),
		);
	}, []);

	return (
		<div className="mx-auto flex h-full max-w-3xl flex-col gap-4 p-4">
			<header className="flex items-center justify-between">
				<h1 className="text-lg font-semibold text-zinc-100">Async Agent — tracer</h1>
				<span className="rounded bg-amber-500/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-300">
					Layer 1
				</span>
			</header>

			<div className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
				<div className="mb-2 text-xs uppercase tracking-wide text-zinc-500">Chat</div>
				<div className="flex max-h-[40vh] flex-col gap-2 overflow-y-auto pr-2">
					{messages.length === 0 && (
						<div className="text-sm text-zinc-500">
							Type a prompt — the image generates in the background while you keep chatting.
						</div>
					)}
					{messages.map((m) => (
						<MessageBubble key={m.id} msg={m} />
					))}
				</div>

				<div className="mt-3 flex items-end gap-2">
					<textarea
						value={brief}
						onChange={(e) => setBrief(e.target.value)}
						onKeyDown={(e) => {
							if (e.key === 'Enter' && !e.shiftKey) {
								e.preventDefault();
								if (!submitting) send();
							}
						}}
						placeholder="Describe the image (composer never locks — fire as many as you want)…"
						className="min-h-[60px] flex-1 resize-y rounded border border-zinc-800 bg-zinc-900 p-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-700 focus:outline-none"
					/>
					<button
						onClick={send}
						disabled={submitting || !brief.trim()}
						className="rounded bg-sky-500 px-3 py-2 text-sm font-medium text-zinc-950 hover:bg-sky-400 disabled:cursor-not-allowed disabled:bg-zinc-800 disabled:text-zinc-500"
					>
						{submitting ? 'Sending…' : 'Send'}
					</button>
				</div>
				{error && <div className="mt-2 text-xs text-red-400">{error}</div>}
			</div>

			<div className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
				<div className="mb-2 text-xs uppercase tracking-wide text-zinc-500">Job tray</div>
				<JobTray projectId={projectId} onJobTerminal={onJobTerminal} />
			</div>
		</div>
	);
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
	const isUser = msg.role === 'user';
	return (
		<div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
			<div
				className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
					isUser ? 'bg-sky-500 text-zinc-950' : 'bg-zinc-800 text-zinc-100'
				} ${msg.failed ? 'border border-red-500/40' : ''}`}
			>
				<div>{msg.text}</div>
				{msg.jobId && (
					<div className="mt-2">
						{msg.imageUrl ? (
							<img
								src={msg.imageUrl}
								alt="generated"
								className="max-h-64 rounded border border-zinc-700"
							/>
						) : !msg.failed ? (
							<div className="flex h-32 w-32 items-center justify-center rounded bg-zinc-900 text-[10px] text-zinc-500">
								Generating…
							</div>
						) : null}
					</div>
				)}
			</div>
		</div>
	);
}
