import React, {useCallback} from 'react';
import {MIN_TIMELINE_ZOOM} from '../constants';
import {MinusIcon} from '../icons/minus';
import {PlusIcon} from '../icons/plus';
import {Slider} from '../slider';
import {useTimelineSize} from './utils/use-timeline-size';
import {useTimelineZoom} from './utils/use-timeline-zoom';

export const TimelineZoomSlider: React.FC = () => {
	const {zoom, setZoom} = useTimelineZoom();
	const {maxZoom, zoomStep} = useTimelineSize();

	const handleSliderChange = useCallback(
		(value: number) => {
			const realValue = value;
			setZoom(realValue);
		},
		[setZoom],
	);

	const handleZoomOut = useCallback(() => {
		setZoom((prev) => Math.max(prev - zoomStep, MIN_TIMELINE_ZOOM));
	}, [setZoom, zoomStep]);

	const handleZoomIn = useCallback(() => {
		setZoom((prev) => Math.min(prev + zoomStep, maxZoom));
	}, [setZoom, zoomStep, maxZoom]);

	return (
		<div
			data-timeline-zoom-slider=""
			className="flex shrink-0 items-center gap-0.5"
		>
			<button
				type="button"
				className="editor-starter-focus-ring flex shrink-0 items-center justify-center p-2"
				onClick={handleZoomOut}
				title="Zoom out"
				aria-label="Zoom out"
			>
				<MinusIcon className="size-3 text-white" />
			</button>
			<div className="flex w-[76px] min-w-[76px] shrink-0 items-center">
				<Slider
					value={zoom}
					onValueChange={handleSliderChange}
					min={MIN_TIMELINE_ZOOM}
					max={maxZoom}
					step={zoomStep}
					className="w-full"
					title="Zoom"
				/>
			</div>
			<button
				type="button"
				className="editor-starter-focus-ring flex shrink-0 items-center justify-center p-2"
				onClick={handleZoomIn}
				title="Zoom in"
				aria-label="Zoom in"
			>
				<PlusIcon className="size-3 text-white" />
			</button>
		</div>
	);
};
