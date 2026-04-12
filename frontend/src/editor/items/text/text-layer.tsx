import {useContext, useMemo} from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {
	TextItemEditingContext,
	TextItemHoverPreviewContext,
} from '../../context-provider';
import {FEATURE_TEXT_BACKGROUND_CONTROL} from '../../flags';
import {turnFontStyleIntoCss} from '../../inspector/controls/font-style-controls/font-style-controls';
import {FontInfoContext} from '../../utils/text/font-info';
import {useLoadFontFromTextItem} from '../../utils/text/load-font-from-text-item';
import {
	calculateFadeInOpacity,
	calculateFadeOutOpacity,
} from '../video/calculate-fade';
import {overrideTextItemWithHoverPreview} from './override-text-item-with-hover-preview';
import {RoundedTextBox} from './rounded-text-box';
import {CanvasTextEditor} from './text-editor';
import {TextItem} from './text-item-type';

export const TextLayer = ({
	item: itemWithoutHoverPreview,
}: {
	item: TextItem;
}) => {
	if (itemWithoutHoverPreview.type !== 'text') {
		throw new Error('Item is not a text');
	}

	const frame = useCurrentFrame();
	const {fps, durationInFrames} = useVideoConfig();

	const textItemHoverPreview = useContext(TextItemHoverPreviewContext);
	const item = useMemo(
		() => {
			const base = overrideTextItemWithHoverPreview({
				textItem: itemWithoutHoverPreview,
				hoverPreview: textItemHoverPreview,
			});
			// Defensive defaults — agent-injected items may lack required fields
			return {
				...base,
				opacity: base.opacity ?? 1,
				fadeInDurationInSeconds: base.fadeInDurationInSeconds ?? 0,
				fadeOutDurationInSeconds: base.fadeOutDurationInSeconds ?? 0,
				fontStyle: base.fontStyle ?? { variant: 'normal', weight: '400' },
				fontFamily: base.fontFamily ?? 'Roboto',
				lineHeight: base.lineHeight ?? 1.2,
				letterSpacing: base.letterSpacing ?? 0,
				rotation: base.rotation ?? 0,
				strokeWidth: base.strokeWidth ?? 0,
				strokeColor: base.strokeColor ?? '#000000',
				background: base.background ?? null,
				direction: base.direction ?? 'ltr',
				align: base.align ?? 'center',
				isDraggingInTimeline: base.isDraggingInTimeline ?? false,
			};
		},
		[itemWithoutHoverPreview, textItemHoverPreview],
	);

	const opacity = useMemo(() => {
		const inOpacity = calculateFadeInOpacity({
			currentFrame: frame,
			fadeInDurationInSeconds: item.fadeInDurationInSeconds,
			framesPerSecond: fps,
		});
		const outOpacity = calculateFadeOutOpacity({
			currentFrame: frame,
			fadeOutDurationInSeconds: item.fadeOutDurationInSeconds,
			framesPerSecond: fps,
			totalDurationInFrames: durationInFrames,
		});
		return inOpacity * outOpacity * item.opacity;
	}, [
		item.fadeInDurationInSeconds,
		fps,
		frame,
		item.opacity,
		durationInFrames,
		item.fadeOutDurationInSeconds,
	]);

	const context = useContext(FontInfoContext);
	const textItemEditing = useContext(TextItemEditingContext);

	const loaded = useLoadFontFromTextItem({
		fontFamily: item.fontFamily,
		fontVariant: item.fontStyle.variant,
		fontWeight: item.fontStyle.weight,
		fontInfosDuringRendering: context[item.fontFamily] ?? null,
	});

	const shouldShowBackground =
		item.background && item.background.color !== 'transparent';

	return (
		<>
			{shouldShowBackground && FEATURE_TEXT_BACKGROUND_CONTROL && loaded ? (
				<RoundedTextBox textItem={item} opacity={opacity} />
			) : null}
			{item.id === textItemEditing ? (
				<CanvasTextEditor item={item} />
			) : (
				<div
					dir={item.direction}
					style={{
						fontSize: item.fontSize,
						color: item.color,
						lineHeight: String(item.lineHeight),
						letterSpacing: `${item.letterSpacing}px`,
						left: item.left,
						top: item.top,
						width: item.width,
						height: item.height,
						position: 'absolute',
						whiteSpace: 'pre-wrap',
						display: 'block',
						fontFamily: item.fontFamily,
						...turnFontStyleIntoCss(item.fontStyle),
						overflow: 'visible',
						wordWrap: 'break-word',
						boxSizing: 'border-box',
						userSelect: 'none',
						textAlign: item.align,
						opacity,
						transform: `rotate(${item.rotation}deg)`,
						WebkitTextStroke: item.strokeWidth
							? `${item.strokeWidth}px ${item.strokeColor}`
							: '0',
						paintOrder: 'stroke',
					}}
				>
					{item.text}
				</div>
			)}
		</>
	);
};
