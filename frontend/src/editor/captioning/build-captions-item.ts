import {CaptionsItem} from '../items/captions/captions-item-type';

export type CaptionPlacement = 'top' | 'center' | 'bottom';

/**
 * Aitoma: single source of truth for the shape of a captions item.
 *
 * Both callers that create captions — the inspector's "Caption video" button and
 * the AI assistant's `add_captions` op — build the same item, so it lives here.
 * Two hand-maintained copies had already drifted apart (font, stroke, highlight,
 * and a pageDurationInMilliseconds of 2000 that put every word on one page).
 */

// pageDurationInMilliseconds is the gate Remotion's createTikTokStyleCaptions
// uses to break pages: 800 gives 2-3 words at a time, >2000 collapses the whole
// transcript onto one page.
const PAGE_DURATION_MS = 800;
const LINE_HEIGHT = 1.2;
const LETTER_SPACING = 0;
const MAX_LINES = 2;
const FONT_SIZE = 72;
const FONT_FAMILY = 'Anton';
const FONT_WEIGHT = '400';
const COLOR = '#FFFFFF';
const HIGHLIGHT_COLOR = '#FFFF00';
const STROKE_COLOR = '#000000';
const STROKE_WIDTH = 8;

const TOP_RATIO: Record<CaptionPlacement, number> = {
	top: 0.15,
	center: 0.45,
	bottom: 0.75,
};

export const buildCaptionsItem = ({
	id,
	assetId,
	from,
	durationInFrames,
	captionStartInSeconds,
	compositionWidth,
	compositionHeight,
	placement = 'center',
	fontSize = FONT_SIZE,
	strokeWidth = STROKE_WIDTH,
	fontWeight = FONT_WEIGHT,
	highlight = true,
}: {
	id: string;
	assetId: string;
	from: number;
	durationInFrames: number;
	captionStartInSeconds: number;
	compositionWidth: number;
	compositionHeight: number;
	placement?: CaptionPlacement;
	fontSize?: number;
	strokeWidth?: number;
	fontWeight?: string;
	/** false paints the active word in the base colour, disabling word-by-word highlighting. */
	highlight?: boolean;
}): CaptionsItem => {
	const width = Math.min(compositionWidth, 900) - 40;

	return {
		type: 'captions',
		id,
		assetId,
		from,
		durationInFrames,
		captionStartInSeconds,
		height: fontSize * LINE_HEIGHT * MAX_LINES,
		isDraggingInTimeline: false,
		left: (compositionWidth - width) / 2,
		top: compositionHeight * TOP_RATIO[placement],
		width,
		opacity: 1,
		rotation: 0,
		fontFamily: FONT_FAMILY,
		fontStyle: {variant: 'normal', weight: fontWeight},
		lineHeight: LINE_HEIGHT,
		letterSpacing: LETTER_SPACING,
		fontSize,
		align: 'center',
		color: COLOR,
		highlightColor: highlight ? HIGHLIGHT_COLOR : COLOR,
		direction: 'ltr',
		pageDurationInMilliseconds: PAGE_DURATION_MS,
		strokeWidth,
		strokeColor: STROKE_COLOR,
		maxLines: MAX_LINES,
		fadeInDurationInSeconds: 0,
		fadeOutDurationInSeconds: 0,
	};
};
