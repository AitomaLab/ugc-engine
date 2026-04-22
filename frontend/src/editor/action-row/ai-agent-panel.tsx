'use client';

import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {toast} from 'sonner';
import {
	AiEditPreviewEntry,
	applyAiEditOps,
	parseAiEditOps,
	stripAiEditBlockForDisplay,
	summarizeAiEditOpsForPreview,
} from './apply-ai-operations';
import {buildTimelineContextForAi} from './build-timeline-context-for-ai';
import {clsx} from '../utils/clsx';
import {useCurrentStateAsRef, useWriteContext} from '../utils/use-context';
import {VideoEditorChat} from './video-editor-chat';

type ChatTurn = {role: 'user' | 'assistant'; content: string};
type ChatMessage = ChatTurn & {
	id: string;
	appliedOps?: boolean;
	approvalStatus?: 'pending' | 'applying' | 'approved' | 'rejected';
	plannedChanges?: AiEditPreviewEntry[];
	timestamp?: Date;
};

export const AiAgentPanel: React.FC<{
	open: boolean;
	onClose: () => void;
}> = ({open, onClose}) => {
	const {setState} = useWriteContext();
	const stateRef = useCurrentStateAsRef();
	const [input, setInput] = useState('');
	const [messages, setMessages] = useState<ChatMessage[]>([]);
	const [loading, setLoading] = useState(false);
	const messageIdRef = useRef(0);

	const nextMessageId = useCallback(() => {
		messageIdRef.current += 1;
		return `msg_${messageIdRef.current}`;
	}, []);

	useEffect(() => {
		if (!open) {
			return;
		}
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') {
				onClose();
			}
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	}, [open, onClose]);

	const send = useCallback(async () => {
		const trimmed = input.trim();
		if (!trimmed || loading) {
			return;
		}
		const userMsg: ChatMessage = {
			id: nextMessageId(),
			role: 'user',
			content: trimmed,
			timestamp: new Date(),
		};
		const nextHistory = [...messages, userMsg];
		setMessages(nextHistory);
		setInput('');
		setLoading(true);
		try {
			const timelineContext = buildTimelineContextForAi(stateRef.current);
			const res = await fetch('/api/editor/ai', {
				method: 'POST',
				headers: {'Content-Type': 'application/json'},
				body: JSON.stringify({
					messages: nextHistory.map((m) => ({
						role: m.role,
						content: m.content,
					})),
					timelineContext,
				}),
			});
			if (!res.ok) {
				const err = await res.json().catch(() => ({error: res.statusText}));
				throw new Error(err.error || `AI request failed (${res.status})`);
			}
			const {text} = (await res.json()) as {text: string};
			const assistantId = nextMessageId();
			const ops = parseAiEditOps(text);
			const plannedChanges =
				ops && ops.length > 0
					? summarizeAiEditOpsForPreview(stateRef.current, ops)
					: undefined;
			const claimsAppliedWithoutOps =
				(!ops || ops.length === 0) &&
				/\b(applied|done|completed|updated|added|changed)\b/i.test(text);
			const safeText = claimsAppliedWithoutOps
				? `${text}\n\nNote: No executable edit steps were returned, so no timeline changes have been applied yet.`
				: text;
			setMessages((prev) => [
				...prev,
				{
					id: assistantId,
					role: 'assistant',
					content: safeText,
					timestamp: new Date(),
					approvalStatus:
						ops && ops.length > 0 ? 'pending' : undefined,
					plannedChanges,
				},
			]);
			if (claimsAppliedWithoutOps) {
				toast.message('Assistant response had no executable edit steps');
			}
		} catch (e) {
			toast.error(e instanceof Error ? e.message : 'AI request failed');
			setMessages((prev) => prev.slice(0, -1));
		} finally {
			setLoading(false);
		}
	}, [input, loading, messages, nextMessageId, stateRef]);

	const applyOpsFromMessage = useCallback(
		async (messageId: string, raw: string): Promise<boolean> => {
			const ops = parseAiEditOps(raw);
			if (!ops?.length) {
				toast.message('No suggested edits to apply');
				return false;
			}
			const hasMusic = ops.some((o) => o.op === 'add_music');
			const hasCaptions = ops.some((o) => o.op === 'add_captions');
			const loadingLabel = hasMusic
				? 'Generating background music… this can take 1–3 minutes'
				: hasCaptions
					? 'Transcribing and generating captions…'
					: `Applying ${ops.length} edit${ops.length === 1 ? '' : 's'}…`;
			const toastId = toast.loading(loadingLabel);
			try {
				const next = await applyAiEditOps(stateRef.current, ops, {setState});
				setState({
					update: () => next,
					commitToUndoStack: true,
				});
				setMessages((prev) =>
					prev.map((msg) =>
						msg.id === messageId ? {...msg, appliedOps: true} : msg,
					),
				);
				toast.success(
					`Applied ${ops.length} edit${ops.length === 1 ? '' : 's'}`,
					{id: toastId},
				);
				return true;
			} catch (e) {
				toast.error(
					e instanceof Error ? e.message : 'Could not apply edits',
					{id: toastId},
				);
				return false;
			}
		},
		[setState, stateRef],
	);

	const handleApproveAndApply = useCallback(
		async (messageId: string) => {
			const msg = messages.find((m) => m.id === messageId);
			if (!msg) {
				return;
			}

			setMessages((prev) =>
				prev.map((m) =>
					m.id === messageId ? {...m, approvalStatus: 'applying'} : m,
				),
			);

			const ok = await applyOpsFromMessage(messageId, msg.content);

			setMessages((prev) =>
				prev.map((m) =>
					m.id === messageId
						? {...m, approvalStatus: ok ? 'approved' : 'pending'}
						: m,
				),
			);
		},
		[messages, applyOpsFromMessage],
	);

	const handleReject = useCallback((messageId: string) => {
		setMessages((prev) =>
			prev.map((msg) =>
				msg.id === messageId ? {...msg, approvalStatus: 'rejected'} : msg,
			),
		);
		toast.message('Changes rejected');
	}, []);
	const suggestions = useMemo(
		() => [
			{id: '1', text: 'Summarize what is on the timeline', icon: '📋'},
			{id: '2', text: 'Lower opacity on the selected clip', icon: '👁️'},
			{id: '3', text: 'Speed up or slow down a video or audio clip', icon: '⚡'},
			{id: '4', text: 'Add background music to my video', icon: '🎵'},
			{id: '5', text: 'Generate captions for this video', icon: '🅲🅲'},
		],
		[],
	);

	const displayMessages = useMemo(
		() =>
			messages.map((m) => ({
				...m,
				content:
					m.role === 'assistant'
						? stripAiEditBlockForDisplay(m.content)
						: m.content,
			})),
		[messages],
	);

	if (!open) {
		return null;
	}

	return (
		<div className="h-full w-full" role="dialog" aria-label="Assistant">
			<VideoEditorChat
				messages={displayMessages}
				inputValue={input}
				isLoading={loading}
				suggestions={suggestions}
				onInputChange={setInput}
				onSend={() => void send()}
				onClearChat={() => {
					setMessages([]);
					toast.message('Chat cleared');
				}}
				onClose={onClose}
				onSuggestionClick={(text) => setInput(text)}
				renderAssistantExtras={(displayMessage) => {
					const original = messages.find((m) => m.id === displayMessage.id);
					if (!original || original.role !== 'assistant') {
						return null;
					}
					return (
						<>
							{original.plannedChanges && original.plannedChanges.length > 0 && !original.appliedOps ? (
								<div className="mt-3 rounded-lg border border-[#2d3748] bg-[#0f0f0f] p-4">
									<p className="text-[11px] font-semibold uppercase tracking-wider text-[#a0aec0]">
										Planned changes
									</p>
									<div className="mt-3 space-y-3">
										{original.plannedChanges.map((entry, idx) => (
											<div
												key={`${original.id}_change_${idx}`}
												className="overflow-hidden rounded-md border border-[#2d3748]"
											>
												<div className="border-b border-[#2d3748] bg-[#1a1a1a] px-3 py-2 text-[12px] font-semibold text-white">
													{entry.title}
												</div>
												{entry.rows.length > 0 ? (
													<table className="w-full text-left text-[12px]">
														<thead>
															<tr className="border-b border-[#2d3748] text-[#a0aec0]">
																<th className="px-3 py-2 font-medium">Field</th>
																<th className="px-3 py-2 font-medium">Before</th>
																<th className="px-3 py-2 font-medium">After</th>
															</tr>
														</thead>
														<tbody>
															{entry.rows.map((row, rowIdx) => (
																<tr
																	key={`${original.id}_change_${idx}_row_${rowIdx}`}
																	className="border-b border-[#2d3748]/70 last:border-b-0"
																>
																	<td className="px-3 py-2 text-[#a0aec0]">
																		{row.field}
																	</td>
																	<td className="px-3 py-2 text-[#a0aec0]">
																		{row.before}
																	</td>
																	<td className="px-3 py-2 text-[#ffffff]">
																		{row.after}
																	</td>
																</tr>
															))}
														</tbody>
													</table>
												) : (
													<p className="px-3 py-2 text-[12px] text-[#a0aec0]">
														No field changes
													</p>
												)}
												{entry.note ? (
													<p className="border-t border-[#2d3748] bg-[#1a1a1a] px-3 py-2 text-[12px] text-[#a0aec0]">
														{entry.note}
													</p>
												) : null}
											</div>
										))}
									</div>

									<div className="mt-4 grid grid-cols-2 gap-3">
										<button
											type="button"
											className={clsx(
												'rounded-md border px-4 py-2.5 text-[13px] font-semibold shadow-sm transition-colors duration-150 ease-out',
												original.approvalStatus === 'approved' ||
													original.approvalStatus === 'applying'
													? 'cursor-not-allowed border-[#3b82f6] bg-[#3b82f6]/20 text-white'
													: 'border-[#3b82f6] bg-[#3b82f6] text-white hover:bg-[#2563eb] active:bg-[#1d4ed8]',
											)}
											onClick={() => void handleApproveAndApply(original.id)}
											disabled={
												original.approvalStatus === 'approved' ||
												original.approvalStatus === 'applying'
											}
										>
											{original.approvalStatus === 'approved'
												? 'Approved'
												: original.approvalStatus === 'applying'
													? 'Applying…'
													: 'Approve'}
										</button>
										<button
											type="button"
											className={clsx(
												'rounded-md border px-4 py-2.5 text-[13px] font-semibold shadow-sm transition-colors duration-150 ease-out',
												original.approvalStatus === 'rejected'
													? 'cursor-not-allowed border-[#ef4444] bg-[#ef4444]/20 text-white'
													: original.approvalStatus === 'approved'
														? 'cursor-not-allowed border-[#2d3748] bg-[#1a1a1a] text-[#a0aec0]/70'
													: 'border-[#3f4654] bg-[#1a1a1a] text-white hover:border-[#ef4444] hover:bg-[#ef4444]/10 hover:text-white',
											)}
											onClick={() => handleReject(original.id)}
											disabled={original.approvalStatus !== 'pending'}
										>
											{original.approvalStatus === 'rejected' ? 'Rejected' : 'Reject'}
										</button>
									</div>
								</div>
							) : null}

							{original.appliedOps ? (
								<p className="mt-3 text-[11px] font-medium text-[#93c5fd]">
									Edits applied to timeline
								</p>
							) : null}
						</>
					);
				}}
			/>
		</div>
	);
};
