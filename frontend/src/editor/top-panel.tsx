import {PlayerRef} from '@remotion/player';
import React from 'react';
import {Canvas} from './canvas/canvas';
import {Inspector} from './inspector/inspector';
import {JobHistorySidebar} from './job-history/job-history-sidebar';
import {useLoop} from './utils/use-context';

export const TopPanel: React.FC<{
	playerRef: React.RefObject<PlayerRef | null>;
	inspectorOpen: boolean;
}> = ({playerRef, inspectorOpen}) => {
	const loop = useLoop();

	return (
		<div className="relative min-h-0 min-w-0 w-full flex-1">
			<div className="absolute flex h-full w-full flex-row">
				<JobHistorySidebar />
				<Canvas playerRef={playerRef} loop={loop} />
				{inspectorOpen ? <Inspector /> : null}
			</div>
		</div>
	);
};
