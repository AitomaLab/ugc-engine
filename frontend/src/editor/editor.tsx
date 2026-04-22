'use client';
import type {PlayerRef} from '@remotion/player';
import {useCallback, useEffect, useRef, useState} from 'react';
import {Toaster} from 'sonner';
import {ActionRow} from './action-row/action-row';
import {AiAgentPanel} from './action-row/ai-agent-panel';
import {DownloadRemoteAssets} from './caching/download-remote-assets';
import {UseLocalCachedAssets} from './caching/use-local-cached-assets';
import {ContextProvider} from './context-provider';
import './editor-starter.css';
import {FEATURE_AI_AGENT, FEATURE_RESIZE_TIMELINE_PANEL} from './flags';
import {ForceSpecificCursor} from './force-specific-cursor';
import {JobHistoryProvider} from './job-history/job-context';
import {PlaybackControls} from './playback-controls';
import {PreviewSizeProvider} from './preview-size-provider';
import {TimelineResizer} from './timeline-resizer';
import {Timeline} from './timeline/timeline';
import {TimelineContainer} from './timeline/timeline-container';
import {TopPanel} from './top-panel';
import {WaitForInitialized} from './wait-for-initialized';

const INSPECTOR_OPEN_KEY = 'editor-inspector-open';
const SIDEBAR_OPEN_KEY = 'editor-sidebar-open';
const SIDEBAR_WIDTH_KEY = 'editor-sidebar-width';
const MIN_SIDEBAR_WIDTH = 280;
const MAX_SIDEBAR_WIDTH = 520;
const DEFAULT_SIDEBAR_WIDTH = 360;

export const Editor: React.FC<{initialJobId?: string | null}> = ({initialJobId}) => {
	const playerRef = useRef<PlayerRef | null>(null);

	const [inspectorOpen, setInspectorOpen] = useState<boolean>(() => {
		if (typeof window === 'undefined') return true;
		const saved = window.localStorage.getItem(INSPECTOR_OPEN_KEY);
		return saved === null ? true : saved === 'true';
	});

	const [sidebarOpen, setSidebarOpen] = useState<boolean>(() => {
		if (typeof window === 'undefined') return false;
		return window.localStorage.getItem(SIDEBAR_OPEN_KEY) === 'true';
	});

	const [sidebarWidth, setSidebarWidth] = useState<number>(() => {
		if (typeof window === 'undefined') return DEFAULT_SIDEBAR_WIDTH;
		const saved = window.localStorage.getItem(SIDEBAR_WIDTH_KEY);
		if (saved) {
			const parsed = Number(saved);
			if (Number.isFinite(parsed)) {
				return Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, parsed));
			}
		}
		return DEFAULT_SIDEBAR_WIDTH;
	});

	const [isResizing, setIsResizing] = useState(false);
	const [resizeTooltip, setResizeTooltip] = useState<{x: number; y: number; width: number} | null>(null);
	const resizeMoveRef = useRef<((e: MouseEvent) => void) | null>(null);
	const resizeUpRef = useRef<(() => void) | null>(null);

	useEffect(() => {
		if (typeof window !== 'undefined') {
			window.localStorage.setItem(INSPECTOR_OPEN_KEY, String(inspectorOpen));
		}
	}, [inspectorOpen]);

	useEffect(() => {
		if (typeof window !== 'undefined') {
			window.localStorage.setItem(SIDEBAR_OPEN_KEY, String(sidebarOpen));
		}
	}, [sidebarOpen]);

	useEffect(() => {
		if (typeof window !== 'undefined') {
			window.localStorage.setItem(SIDEBAR_WIDTH_KEY, String(sidebarWidth));
		}
	}, [sidebarWidth]);

	useEffect(() => {
		const onKeyDown = (e: KeyboardEvent) => {
			if ((e.metaKey || e.ctrlKey) && e.key === '\\') {
				e.preventDefault();
				setSidebarOpen((prev) => !prev);
				return;
			}
			if ((e.metaKey || e.ctrlKey) && !e.shiftKey && e.key.toLowerCase() === 'i') {
				e.preventDefault();
				setInspectorOpen((prev) => !prev);
			}
		};
		window.addEventListener('keydown', onKeyDown);
		return () => window.removeEventListener('keydown', onKeyDown);
	}, []);

	const clearResizeListeners = useCallback(() => {
		if (resizeMoveRef.current) {
			document.removeEventListener('mousemove', resizeMoveRef.current);
			resizeMoveRef.current = null;
		}
		if (resizeUpRef.current) {
			document.removeEventListener('mouseup', resizeUpRef.current);
			resizeUpRef.current = null;
		}
		document.body.style.cursor = '';
		document.body.style.userSelect = '';
		setIsResizing(false);
		setResizeTooltip(null);
	}, []);

	useEffect(() => () => clearResizeListeners(), [clearResizeListeners]);

	const handleResizeStart = useCallback(
		(e: React.MouseEvent) => {
			e.preventDefault();
			const startX = e.clientX;
			const startWidth = sidebarWidth;
			setIsResizing(true);
			setResizeTooltip({x: e.clientX + 12, y: e.clientY + 12, width: sidebarWidth});

			const onMouseMove = (moveEvent: MouseEvent) => {
				const delta = startX - moveEvent.clientX;
				const newWidth = Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, startWidth + delta));
				setSidebarWidth(newWidth);
				setResizeTooltip({x: moveEvent.clientX + 12, y: moveEvent.clientY + 12, width: Math.round(newWidth)});
			};
			const onMouseUp = () => clearResizeListeners();

			resizeMoveRef.current = onMouseMove;
			resizeUpRef.current = onMouseUp;
			document.body.style.cursor = 'col-resize';
			document.body.style.userSelect = 'none';
			document.addEventListener('mousemove', onMouseMove);
			document.addEventListener('mouseup', onMouseUp);
		},
		[clearResizeListeners, sidebarWidth],
	);

	return (
		<div className="bg-editor-starter-bg flex h-screen min-h-0 w-screen flex-col overflow-hidden">
			<JobHistoryProvider initialJobId={initialJobId ?? null}>
				<ContextProvider>
					<WaitForInitialized>
						<PreviewSizeProvider>
							<ActionRow
								playerRef={playerRef}
								sidebarOpen={sidebarOpen}
								onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
								inspectorOpen={inspectorOpen}
								onToggleInspector={() => setInspectorOpen((prev) => !prev)}
							/>
							<div className="flex min-h-0 w-full flex-1 flex-row">
								<div className="flex min-h-0 min-w-0 flex-1 flex-col">
									<TopPanel playerRef={playerRef} inspectorOpen={inspectorOpen} />
									<PlaybackControls playerRef={playerRef} />
									{FEATURE_RESIZE_TIMELINE_PANEL && <TimelineResizer />}
									<TimelineContainer playerRef={playerRef}>
										<Timeline playerRef={playerRef} />
									</TimelineContainer>
								</div>

							{FEATURE_AI_AGENT && sidebarOpen ? (
								<>
									<div
										className="h-full w-1 shrink-0 cursor-col-resize bg-transparent transition-colors duration-150 hover:bg-[#2A2A2A]"
										onMouseDown={handleResizeStart}
										role="separator"
										aria-orientation="vertical"
										aria-label="Resize AI assistant sidebar"
									/>
									<div
										className="h-full shrink-0 overflow-hidden border-l border-[#222222] bg-[#111111]"
										style={{width: sidebarWidth}}
									>
										<AiAgentPanel
											open={sidebarOpen}
											onClose={() => setSidebarOpen(false)}
										/>
									</div>
								</>
							) : null}
							</div>
						</PreviewSizeProvider>
					</WaitForInitialized>
					<ForceSpecificCursor />
					<DownloadRemoteAssets />
					<UseLocalCachedAssets />
					<Toaster theme="dark" />

					{isResizing && resizeTooltip ? (
						<div
							className="pointer-events-none fixed z-[11000] rounded border border-[#2A2A2A] bg-[#1C1C1C] px-2 py-1 text-[11px] text-[#AAAAAA]"
							style={{left: resizeTooltip.x, top: resizeTooltip.y}}
						>
							{resizeTooltip.width}px
						</div>
					) : null}
				</ContextProvider>
			</JobHistoryProvider>
		</div>
	);
};
