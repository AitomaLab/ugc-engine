import {PlayerRef} from '@remotion/player';
import React from 'react';
import {SnappingToggle} from '../action-row/snapping-toggle';
import {SplitItemTool} from '../action-row/split-item-tool';
import {
	FEATURE_CANVAS_SNAPPING,
	FEATURE_FULLSCREEN_CONTROL,
	FEATURE_JUMP_TO_END_BUTTON,
	FEATURE_JUMP_TO_START_BUTTON,
	FEATURE_LOOP_BUTTON,
	FEATURE_MUTE_BUTTON,
	FEATURE_SPLIT_ITEM,
	FEATURE_TIMELINE_SNAPPING,
	FEATURE_TIMELINE_ZOOM_SLIDER,
} from '../flags';
import {TimelineZoomSlider} from '../timeline/timeline-zoom-slider';
import {useFps} from '../utils/use-context';
import {FullscreenButton} from './fullscreen-button';
import {LoopButton} from './loop-button';
import {MuteButton} from './mute-button';
import {PlayPauseButton} from './play-pause';
import {ProjectDurationDisplay} from './project-duration-display';
import {GoToEndButton, GoToStartButton} from './seeking';
import {CurrentTimeDisplay} from './time-display';

export const PlaybackControls: React.FC<{
	playerRef: React.RefObject<PlayerRef | null>;
}> = ({playerRef}) => {
	const {fps} = useFps();
	return (
		<div
			data-playback-bar=""
			className="border-t-editor-starter-border bg-editor-starter-bg relative flex w-full min-w-0 shrink-0 flex-row items-center justify-between overflow-x-auto overflow-y-hidden border-t-[1px] text-white"
			style={{height: '46px', minHeight: '46px', maxHeight: '46px', padding: '0 12px'}}
		>
			<div className="flex min-w-0 flex-1 items-center">
				{FEATURE_SPLIT_ITEM ? <SplitItemTool playerRef={playerRef} /> : null}
				{FEATURE_TIMELINE_SNAPPING || FEATURE_CANVAS_SNAPPING ? (
					<SnappingToggle />
				) : null}
			</div>
			<div className="flex shrink-0 items-center gap-6">
				<CurrentTimeDisplay playerRef={playerRef} fps={fps} />
				<div className="flex items-center gap-2">
					{FEATURE_JUMP_TO_START_BUTTON && (
						<GoToStartButton playerRef={playerRef} />
					)}
					<PlayPauseButton playerRef={playerRef} />
					{FEATURE_JUMP_TO_END_BUTTON && (
						<GoToEndButton playerRef={playerRef} />
					)}
				</div>
				<ProjectDurationDisplay fps={fps} />
			</div>
			<div className="flex min-w-0 flex-1 items-center justify-end gap-2 sm:gap-3">
				{FEATURE_LOOP_BUTTON && <LoopButton />}
				{FEATURE_MUTE_BUTTON && <MuteButton playerRef={playerRef} />}
				{FEATURE_FULLSCREEN_CONTROL && (
					<FullscreenButton playerRef={playerRef} />
				)}
				{FEATURE_TIMELINE_ZOOM_SLIDER && <TimelineZoomSlider />}
			</div>
		</div>
	);
};
