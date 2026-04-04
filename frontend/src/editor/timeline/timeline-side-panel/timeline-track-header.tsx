import {useMemo} from 'react';
import {FEATURE_HIDE_TRACKS, FEATURE_MUTE_TRACKS} from '../../flags';
import {TimelineTrackAndLayout} from '../utils/drag/calculate-track-heights';
import {TimelineHideTrack} from './timeline-hide-track';
import {TimelineMuteTrack} from './timeline-mute-track';

export const TrackHeader = ({
	name,
	trackAndLayout,
}: {
	name: string;
	trackAndLayout: TimelineTrackAndLayout;
}) => {
	const style = useMemo(() => {
		return {
			height: trackAndLayout.height,
		};
	}, [trackAndLayout]);

	return (
		<div
			className="group bg-editor-starter-bg flex w-full shrink-0 items-center gap-2 truncate pl-4 text-xs"
			style={style}
		>
			<div className="w-4 text-right text-neutral-400">{name}</div>
			<div className="flex">
				{FEATURE_HIDE_TRACKS && (
					<TimelineHideTrack track={trackAndLayout.track} />
				)}
				{FEATURE_MUTE_TRACKS && (
					<TimelineMuteTrack track={trackAndLayout.track} />
				)}
			</div>
		</div>
	);
};
