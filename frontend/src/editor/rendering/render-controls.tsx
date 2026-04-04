import React, {useState} from 'react';
import {FEATURE_RENDERING_CODEC_SELECTOR} from '../flags';
import {InspectorLabel} from '../inspector/components/inspector-label';
import {InspectorSection} from '../inspector/components/inspector-section';
import {getCompositionDuration} from '../utils/get-composition-duration';
import {useCurrentStateAsRef, useWriteContext} from '../utils/use-context';
import {CodecOption, CodecSelector} from './codec-selector';
import {triggerLambdaRender} from './render-state';
import {TriggerRenderButton} from './trigger-render-button';

export const RenderControls: React.FC = () => {
	const {setState} = useWriteContext();
	const state = useCurrentStateAsRef();
	const [selectedCodec, setSelectedCodec] = useState<CodecOption>('h264');

	const onClick = React.useCallback(async () => {
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
			codec: selectedCodec,
		});
	}, [setState, state, selectedCodec]);

	return (
		<InspectorSection>
			<InspectorLabel>Export</InspectorLabel>
			<div className="h-2"></div>
			<div className="w-full">
				<div className="mb-3">
					{FEATURE_RENDERING_CODEC_SELECTOR ? (
						<CodecSelector
							value={selectedCodec}
							onValueChange={setSelectedCodec}
						/>
					) : null}
				</div>
				<TriggerRenderButton onTrigger={onClick} />
			</div>
		</InspectorSection>
	);
};
