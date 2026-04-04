import {PlayerRef} from '@remotion/player';
import React from 'react';
import {Canvas} from './canvas/canvas';
import {Inspector} from './inspector/inspector';
import {useLoop} from './utils/use-context';

export const TopPanel: React.FC<{
	playerRef: React.RefObject<PlayerRef | null>;
}> = ({playerRef}) => {
	const loop = useLoop();

	return (
		<div className="relative h-full w-full flex-1">
			<div className="absolute flex h-full w-full flex-row">
				<Canvas playerRef={playerRef} loop={loop} />
				<Inspector />
			</div>
		</div>
	);
};
