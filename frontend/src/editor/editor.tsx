'use client';

import type {PlayerRef} from '@remotion/player';
import {useRef} from 'react';
import {Toaster} from 'sonner';
import {ActionRow} from './action-row/action-row';
import {DownloadRemoteAssets} from './caching/download-remote-assets';
import {UseLocalCachedAssets} from './caching/use-local-cached-assets';
import {ContextProvider} from './context-provider';
import './editor-starter.css';
import {FEATURE_RESIZE_TIMELINE_PANEL} from './flags';
import {ForceSpecificCursor} from './force-specific-cursor';
import {PlaybackControls} from './playback-controls';
import {PreviewSizeProvider} from './preview-size-provider';
import {TimelineResizer} from './timeline-resizer';
import {Timeline} from './timeline/timeline';
import {TimelineContainer} from './timeline/timeline-container';
import {TopPanel} from './top-panel';
import {WaitForInitialized} from './wait-for-initialized';

export const Editor: React.FC = () => {
	const playerRef = useRef<PlayerRef | null>(null);

	return (
		<div className="bg-editor-starter-bg flex h-screen w-screen flex-col items-center justify-between overflow-hidden">
			<ContextProvider>
				<WaitForInitialized>
					<PreviewSizeProvider>
						<ActionRow playerRef={playerRef} />
						<TopPanel playerRef={playerRef} />
					</PreviewSizeProvider>
					<PlaybackControls playerRef={playerRef} />
					{FEATURE_RESIZE_TIMELINE_PANEL && <TimelineResizer />}
					<TimelineContainer playerRef={playerRef}>
						<Timeline playerRef={playerRef} />
					</TimelineContainer>
				</WaitForInitialized>
				<ForceSpecificCursor />
				<DownloadRemoteAssets />
				<UseLocalCachedAssets />
				<Toaster theme="dark" />
			</ContextProvider>
		</div>
	);
};
