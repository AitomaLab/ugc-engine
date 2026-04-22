import React, {memo, useCallback} from 'react';
import {CaptionsItem, StrokeMode} from '../../items/captions/captions-item-type';
import {changeItem} from '../../state/actions/change-item';
import {useWriteContext} from '../../utils/use-context';
import {InspectorSubLabel} from '../components/inspector-label';
import {NumberControl, NumberControlUpdateHandler} from './number-controls';

const MODES: {value: StrokeMode; label: string}[] = [
	{value: 'solid', label: 'Solid'},
	{value: 'shadow', label: 'Shadow'},
	{value: 'glow', label: 'Glow'},
];

const StrokeModeControlsUnmemoized: React.FC<{
	item: CaptionsItem;
}> = ({item}) => {
	const {setState} = useWriteContext();
	const mode: StrokeMode = item.strokeMode ?? 'solid';

	const setMode = useCallback(
		(newMode: StrokeMode) => {
			setState({
				update: (state) => {
					return changeItem(state, item.id, (i) => {
						if (i.type !== 'captions') {
							throw new Error('Stroke mode is only available on captions');
						}
						return {
							...i,
							strokeMode: newMode,
							shadowColor: i.shadowColor ?? i.strokeColor,
							shadowBlur: i.shadowBlur ?? 8,
							shadowOffsetX: i.shadowOffsetX ?? 0,
							shadowOffsetY: i.shadowOffsetY ?? 4,
						};
					});
				},
				commitToUndoStack: true,
			});
		},
		[setState, item.id],
	);

	const setShadowNumber = useCallback(
		(field: 'shadowBlur' | 'shadowOffsetX' | 'shadowOffsetY'): NumberControlUpdateHandler =>
			({num, commitToUndoStack}) => {
				setState({
					update: (state) => {
						return changeItem(state, item.id, (i) => {
							if (i.type !== 'captions') {
								throw new Error('Item is not captions');
							}
							return {...i, [field]: num};
						});
					},
					commitToUndoStack,
				});
			},
		[setState, item.id],
	);

	const onShadowColorChange: React.ChangeEventHandler<HTMLInputElement> = useCallback(
		(evt) => {
			const newColor = evt.target.value;
			setState({
				update: (state) => {
					return changeItem(state, item.id, (i) => {
						if (i.type !== 'captions') {
							throw new Error('Item is not captions');
						}
						return {...i, shadowColor: newColor};
					});
				},
				commitToUndoStack: true,
			});
		},
		[setState, item.id],
	);

	return (
		<div className="flex flex-col gap-2">
			<div>
				<InspectorSubLabel>Style</InspectorSubLabel>
				<div className="editor-starter-field inline-flex hover:border-transparent">
					{MODES.map((m) => (
						<button
							key={m.value}
							onClick={() => setMode(m.value)}
							data-active={mode === m.value}
							className="editor-starter-focus-ring flex h-6 min-w-14 items-center justify-center rounded-[2px] px-2 text-xs text-white data-[active=true]:bg-black/20 data-[active=true]:outline data-[active=true]:outline-neutral-700"
							title={m.label}
							aria-label={`Stroke style ${m.label}`}
							type="button"
						>
							{m.label}
						</button>
					))}
				</div>
			</div>

			{(mode === 'shadow' || mode === 'glow') && (
				<div className="flex flex-col gap-2">
					<div>
						<InspectorSubLabel>Blur</InspectorSubLabel>
						<NumberControl
							accessibilityLabel="Shadow blur"
							label={<span className="text-xs text-neutral-300">px</span>}
							value={item.shadowBlur ?? 8}
							setValue={setShadowNumber('shadowBlur')}
							min={0}
							max={100}
							step={1}
						/>
					</div>

					{mode === 'shadow' && (
						<div className="flex flex-row gap-2">
							<div className="flex-1">
								<InspectorSubLabel>Offset X</InspectorSubLabel>
								<NumberControl
									accessibilityLabel="Shadow offset X"
									label={<span className="text-xs text-neutral-300">px</span>}
									value={item.shadowOffsetX ?? 0}
									setValue={setShadowNumber('shadowOffsetX')}
									min={-100}
									max={100}
									step={1}
								/>
							</div>
							<div className="flex-1">
								<InspectorSubLabel>Offset Y</InspectorSubLabel>
								<NumberControl
									accessibilityLabel="Shadow offset Y"
									label={<span className="text-xs text-neutral-300">px</span>}
									value={item.shadowOffsetY ?? 4}
									setValue={setShadowNumber('shadowOffsetY')}
									min={-100}
									max={100}
									step={1}
								/>
							</div>
						</div>
					)}

					<div>
						<InspectorSubLabel>Color</InspectorSubLabel>
						<input
							type="color"
							value={item.shadowColor ?? item.strokeColor}
							onChange={onShadowColorChange}
							aria-label="Shadow color"
							className="h-8 w-full cursor-pointer rounded border border-neutral-700 bg-transparent"
						/>
					</div>
				</div>
			)}
		</div>
	);
};

export const StrokeModeControls = memo(StrokeModeControlsUnmemoized);
