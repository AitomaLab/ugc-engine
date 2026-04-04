import React, {useCallback, useState} from 'react';
import {clsx} from '../utils/clsx';
import {getCompositionDuration} from '../utils/get-composition-duration';
import {isTimelineEmpty} from '../utils/is-timeline-empty';
import {useCurrentStateAsRef, useTracks, useWriteContext} from '../utils/use-context';
import {triggerLambdaRender} from '../rendering/render-state';

const RenderIcon: React.FC<React.SVGProps<SVGSVGElement>> = (props) => (
	<svg
		xmlns="http://www.w3.org/2000/svg"
		width="16"
		height="16"
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		strokeWidth="2"
		strokeLinecap="round"
		strokeLinejoin="round"
		{...props}
	>
		<polygon points="23 7 16 12 23 17 23 7" />
		<rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
	</svg>
);

export const RenderButton = () => {
	const {setState} = useWriteContext();
	const state = useCurrentStateAsRef();
	const {tracks} = useTracks();
	const [isRendering, setIsRendering] = useState(false);

	const isEmpty = isTimelineEmpty(tracks);

	const handleRender = useCallback(async () => {
		if (isRendering || isEmpty) return;

		setIsRendering(true);
		try {
			const {assets, tracks, items, compositionHeight, compositionWidth, fps} =
				state.current.undoableState;

			const durationInFrames = getCompositionDuration(Object.values(items));

			await triggerLambdaRender({
				compositionHeight,
				compositionWidth,
				compositionDurationInSeconds: durationInFrames / fps,
				setState,
				tracks,
				assets,
				items,
				codec: 'h264',
			});
		} finally {
			setIsRendering(false);
		}
	}, [isRendering, isEmpty, setState, state]);

	return (
		<button
			data-toolbar-btn
			data-render
			className={clsx(
				'editor-starter-focus-ring flex h-10 items-center justify-center gap-1.5 rounded text-white transition-colors',
				'bg-blue-600 hover:bg-blue-500 px-4',
				(isEmpty || isRendering) && 'opacity-50 cursor-not-allowed',
			)}
			title={isEmpty ? 'Add content to the timeline first' : 'Render and export video'}
			disabled={isEmpty || isRendering}
			onClick={handleRender}
			aria-label="Render video"
		>
			<RenderIcon />
			<span className="text-xs font-semibold">{isRendering ? 'Rendering...' : 'Render'}</span>
		</button>
	);
};
