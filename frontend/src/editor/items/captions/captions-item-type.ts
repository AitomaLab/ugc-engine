import {BaseItem, CanHaveRotation} from '../shared';
import {FontStyle, TextAlign, TextDirection} from '../text/text-item-type';

export type StrokeMode = 'solid' | 'shadow' | 'glow';

export type CaptionsItem = BaseItem &
	CanHaveRotation & {
		type: 'captions';
		assetId: string;
		fontFamily: string;
		fontStyle: FontStyle;
		lineHeight: number;
		letterSpacing: number;
		fontSize: number;
		align: TextAlign;
		color: string;
		highlightColor: string;
		strokeWidth: number;
		strokeColor: string;
		strokeMode?: StrokeMode;
		shadowOffsetX?: number;
		shadowOffsetY?: number;
		shadowBlur?: number;
		shadowColor?: string;
		direction: TextDirection;
		pageDurationInMilliseconds: number;
		captionStartInSeconds: number;
		maxLines: number;
		fadeInDurationInSeconds: number;
		fadeOutDurationInSeconds: number;
	};
