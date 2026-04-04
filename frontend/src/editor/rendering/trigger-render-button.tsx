import React from 'react';
import {TextButton} from '../action-row/text-button';
import {isTimelineEmpty} from '../utils/is-timeline-empty';
import {useTracks} from '../utils/use-context';

export const TriggerRenderButton: React.FC<{
	onTrigger: () => void;
}> = ({onTrigger}) => {
	const {tracks} = useTracks();

	const disabled = isTimelineEmpty(tracks);

	return (
		<TextButton onClick={onTrigger} disabled={disabled}>
			<div>Render video</div>
		</TextButton>
	);
};
