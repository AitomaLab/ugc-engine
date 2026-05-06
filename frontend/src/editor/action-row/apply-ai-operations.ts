import {addCaptionAsset} from '../state/actions/add-caption-asset';
import {createTextItem} from '../items/text/create-text-item';
import {EditorStarterItem} from '../items/item-type';
import {addAssetToState} from '../state/actions/add-asset-to-state';
import {addItem} from '../state/actions/add-item';
import {changeItem} from '../state/actions/change-item';
import {deleteItems} from '../state/actions/delete-items';
import {EditorState} from '../state/types';
import {editorFetchMusic} from '../utils/editor-api';
import {generateRandomId} from '../utils/generate-random-id';
import {MAX_VOLUME_DB, MIN_VOLUME_DB} from '../utils/decibels';
import {getCompositionDuration} from '../utils/get-composition-duration';
import {getCaptions} from '../captioning/caption-state';

export const AI_EDIT_OPS_MARKER = 'AI_EDIT_OPS';

export type AiEditPreviewRow = {
	field: string;
	before: string;
	after: string;
};

export type AiEditPreviewEntry = {
	title: string;
	rows: AiEditPreviewRow[];
	note?: string;
};

function splitByOpsMarker(text: string): {display: string; jsonPart: string} | null {
	const match = text.match(
		/(?:^|\n)\s*AI_EDIT_OPS\s*:?\s*\n([\s\S]*)$/m,
	);
	if (!match) {
		return null;
	}
	const markerIndex = match.index ?? -1;
	if (markerIndex < 0) {
		return null;
	}
	const display = text.slice(0, markerIndex).trimEnd();
	const jsonPart = match[1].trim();
	return {display, jsonPart};
}

const MAX_DELETE_IDS = 40;
const MAX_TEXT_LEN = 2000;
const MIN_RATE = 0.05;
const MAX_RATE = 8;

export type AiEditOp =
	| {op: 'set_opacity'; itemId: string; opacity: number}
	| {op: 'set_playback_rate'; itemId: string; playbackRate: number}
	| {op: 'set_volume_db'; itemId: string; decibelAdjustment: number}
	| {op: 'delete_items'; itemIds: string[]}
	| {
			op: 'set_timeline_span';
			itemId: string;
			from?: number;
			durationInFrames?: number;
	  }
	| {
			op: 'set_fade';
			itemId: string;
			fadeInDurationInSeconds?: number;
			fadeOutDurationInSeconds?: number;
	  }
	| {
			op: 'set_audio_fade';
			itemId: string;
			audioFadeInDurationInSeconds?: number;
			audioFadeOutDurationInSeconds?: number;
	  }
	| {op: 'set_text_content'; itemId: string; text: string}
	| {
			op: 'set_position_size';
			itemId: string;
			left?: number;
			top?: number;
			width?: number;
			height?: number;
	  }
	| {op: 'set_media_start'; itemId: string; mediaStartInSeconds: number}
	| {
			op: 'add_music';
			mood?: string;
			duration?: number;
			volume?: number;
			position?: 'background';
	  }
	| {
			op: 'add_captions';
			language?: string;
			style?: 'default' | 'bold' | 'minimal';
			position?: 'bottom' | 'top' | 'center';
			highlight_words?: boolean;
	  }
	| {
			op: 'set_caption_style';
			itemId: string;
			color?: string;
			highlightColor?: string;
			strokeColor?: string;
			strokeWidth?: number;
			strokeMode?: 'solid' | 'shadow' | 'glow';
			shadowColor?: string;
			shadowBlur?: number;
			shadowOffsetX?: number;
			shadowOffsetY?: number;
			fontSize?: number;
			fontFamily?: string;
			maxLines?: number;
			pageDurationInMilliseconds?: number;
	  }
	| {op: 'add_text'; text: string; from?: number; durationInFrames?: number};

export function stripAiEditBlockForDisplay(text: string): string {
	const split = splitByOpsMarker(text);
	if (!split) {
		return text;
	}
	return split.display;
}

export function parseAiEditOps(text: string): AiEditOp[] | null {
	const split = splitByOpsMarker(text);
	if (!split) {
		return null;
	}
	try {
		let jsonText = split.jsonPart.trim();
		const fencedMatch = jsonText.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
		if (fencedMatch) {
			jsonText = fencedMatch[1].trim();
		}
		const parsed: unknown = JSON.parse(jsonText);
		if (!Array.isArray(parsed)) {
			return null;
		}
		return parsed.filter(isValidAiEditOp);
	} catch {
		return null;
	}
}

function isValidAiEditOp(row: unknown): row is AiEditOp {
	if (!row || typeof row !== 'object') {
		return false;
	}
	const o = row as Record<string, unknown>;
	if (o.op === 'set_opacity') {
		return (
			typeof o.itemId === 'string' &&
			typeof o.opacity === 'number' &&
			Number.isFinite(o.opacity)
		);
	}
	if (o.op === 'set_playback_rate') {
		return (
			typeof o.itemId === 'string' &&
			typeof o.playbackRate === 'number' &&
			Number.isFinite(o.playbackRate) &&
			o.playbackRate > 0
		);
	}
	if (o.op === 'set_volume_db') {
		return (
			typeof o.itemId === 'string' &&
			typeof o.decibelAdjustment === 'number' &&
			Number.isFinite(o.decibelAdjustment)
		);
	}
	if (o.op === 'delete_items') {
		return (
			Array.isArray(o.itemIds) &&
			o.itemIds.length > 0 &&
			o.itemIds.length <= MAX_DELETE_IDS &&
			o.itemIds.every((id) => typeof id === 'string')
		);
	}
	if (o.op === 'set_timeline_span') {
		if (typeof o.itemId !== 'string') {
			return false;
		}
		const hasFrom = typeof o.from === 'number' && Number.isFinite(o.from);
		const hasDur =
			typeof o.durationInFrames === 'number' &&
			Number.isFinite(o.durationInFrames);
		return hasFrom || hasDur;
	}
	if (o.op === 'add_text') {
		if (typeof o.text !== 'string' || o.text.trim().length === 0) {
			return false;
		}
		if (o.from !== undefined) {
			if (typeof o.from !== 'number' || !Number.isFinite(o.from)) {
				return false;
			}
		}
		if (o.durationInFrames !== undefined) {
			if (
				typeof o.durationInFrames !== 'number' ||
				!Number.isFinite(o.durationInFrames)
			) {
				return false;
			}
		}
		return true;
	}
	if (o.op === 'set_fade') {
		if (typeof o.itemId !== 'string') {
			return false;
		}
		const hasIn =
			typeof o.fadeInDurationInSeconds === 'number' &&
			Number.isFinite(o.fadeInDurationInSeconds);
		const hasOut =
			typeof o.fadeOutDurationInSeconds === 'number' &&
			Number.isFinite(o.fadeOutDurationInSeconds);
		return hasIn || hasOut;
	}
	if (o.op === 'set_audio_fade') {
		if (typeof o.itemId !== 'string') {
			return false;
		}
		const hasIn =
			typeof o.audioFadeInDurationInSeconds === 'number' &&
			Number.isFinite(o.audioFadeInDurationInSeconds);
		const hasOut =
			typeof o.audioFadeOutDurationInSeconds === 'number' &&
			Number.isFinite(o.audioFadeOutDurationInSeconds);
		return hasIn || hasOut;
	}
	if (o.op === 'set_text_content') {
		return typeof o.itemId === 'string' && typeof o.text === 'string';
	}
	if (o.op === 'set_position_size') {
		if (typeof o.itemId !== 'string') {
			return false;
		}
		const hasLeft = typeof o.left === 'number' && Number.isFinite(o.left);
		const hasTop = typeof o.top === 'number' && Number.isFinite(o.top);
		const hasWidth = typeof o.width === 'number' && Number.isFinite(o.width);
		const hasHeight =
			typeof o.height === 'number' && Number.isFinite(o.height);
		return hasLeft || hasTop || hasWidth || hasHeight;
	}
	if (o.op === 'set_media_start') {
		return (
			typeof o.itemId === 'string' &&
			typeof o.mediaStartInSeconds === 'number' &&
			Number.isFinite(o.mediaStartInSeconds)
		);
	}
	if (o.op === 'add_music') {
		if (o.mood !== undefined && typeof o.mood !== 'string') {
			return false;
		}
		if (o.duration !== undefined) {
			if (typeof o.duration !== 'number' || !Number.isFinite(o.duration)) {
				return false;
			}
		}
		if (o.volume !== undefined) {
			if (typeof o.volume !== 'number' || !Number.isFinite(o.volume)) {
				return false;
			}
		}
		if (o.position !== undefined && o.position !== 'background') {
			return false;
		}
		return true;
	}
	if (o.op === 'add_captions') {
		if (o.language !== undefined && typeof o.language !== 'string') {
			return false;
		}
		if (
			o.style !== undefined &&
			o.style !== 'default' &&
			o.style !== 'bold' &&
			o.style !== 'minimal'
		) {
			return false;
		}
		if (
			o.position !== undefined &&
			o.position !== 'bottom' &&
			o.position !== 'top' &&
			o.position !== 'center'
		) {
			return false;
		}
		if (
			o.highlight_words !== undefined &&
			typeof o.highlight_words !== 'boolean'
		) {
			return false;
		}
		return true;
	}
	if (o.op === 'set_caption_style') {
		if (typeof o.itemId !== 'string') {
			return false;
		}
		// At least one style property must be set
		const hasAny =
			o.color !== undefined ||
			o.highlightColor !== undefined ||
			o.strokeColor !== undefined ||
			o.strokeWidth !== undefined ||
			o.strokeMode !== undefined ||
			o.shadowColor !== undefined ||
			o.shadowBlur !== undefined ||
			o.shadowOffsetX !== undefined ||
			o.shadowOffsetY !== undefined ||
			o.fontSize !== undefined ||
			o.fontFamily !== undefined ||
			o.maxLines !== undefined ||
			o.pageDurationInMilliseconds !== undefined;
		if (!hasAny) {
			return false;
		}
		if (o.strokeMode !== undefined && o.strokeMode !== 'solid' && o.strokeMode !== 'shadow' && o.strokeMode !== 'glow') {
			return false;
		}
		return true;
	}
	return false;
}

/**
 * Applies allowlisted AI ops in order. Uses async for add_text (font loading).
 */
type SetStateLike = (options: {
	update: EditorState | ((state: EditorState) => EditorState);
	commitToUndoStack: boolean;
}) => void;

const DEFAULT_CAPTION_HIGHLIGHT_COLOR = '#39E508';

const volumeToDecibel = (volume: number) => {
	if (volume <= 0) {
		return MIN_VOLUME_DB;
	}
	return 20 * Math.log10(volume);
};

export async function applyAiEditOps(
	state: EditorState,
	ops: AiEditOp[],
	options?: {setState?: SetStateLike},
): Promise<EditorState> {
	let s = state;
	const fps = s.undoableState.fps;
	const maxDur = Math.min(3600 * fps, 1_000_000);

	for (const op of ops) {
		if (op.op === 'delete_items') {
			const ids = op.itemIds.filter((id) => s.undoableState.items[id]);
			if (ids.length > 0) {
				s = deleteItems(s, ids);
			}
			continue;
		}

		if (op.op === 'set_timeline_span') {
			const item = s.undoableState.items[op.itemId];
			if (!item) {
				continue;
			}
			s = changeItem(s, op.itemId, (i: EditorStarterItem) => {
				let next = {...i};
				if (typeof op.from === 'number' && Number.isFinite(op.from)) {
					next.from = Math.max(0, Math.round(op.from));
				}
				if (
					typeof op.durationInFrames === 'number' &&
					Number.isFinite(op.durationInFrames)
				) {
					next.durationInFrames = Math.min(
						maxDur,
						Math.max(1, Math.round(op.durationInFrames)),
					);
				}
				return next;
			});
			continue;
		}

		if (op.op === 'add_text') {
			const {compositionWidth: cw, compositionHeight: ch} =
				s.undoableState;
			const text = op.text.trim().slice(0, MAX_TEXT_LEN);
			if (!text) {
				continue;
			}
			const dur = Math.min(
				maxDur,
				Math.max(
					1,
					Math.round(
						op.durationInFrames !== undefined ? op.durationInFrames : 100,
					),
				),
			);
			const compEnd = getCompositionDuration(
				Object.values(s.undoableState.items),
			);
			const from =
				typeof op.from === 'number' && Number.isFinite(op.from)
					? Math.max(0, Math.round(op.from))
					: Math.max(0, compEnd - dur);

			const item = await createTextItem({
				xOnCanvas: cw / 2,
				yOnCanvas: ch / 2,
				from,
				text,
				align: 'center',
			});
			const itemWithDur =
				item.durationInFrames !== dur ? {...item, durationInFrames: dur} : item;
			s = addItem({
				state: s,
				item: itemWithDur,
				select: false,
				position: {type: 'front'},
			});
			continue;
		}

		if (op.op === 'add_music') {
			const compositionDurationInFrames = getCompositionDuration(
				Object.values(s.undoableState.items),
			);
			const fallbackDurationInSeconds = Math.max(
				1,
				compositionDurationInFrames / fps,
			);
			const durationInSeconds =
				typeof op.duration === 'number' && Number.isFinite(op.duration)
					? Math.max(1, op.duration)
					: fallbackDurationInSeconds;
			const mood =
				typeof op.mood === 'string' && op.mood.trim().length > 0
					? op.mood.trim()
					: 'cinematic';
			const volume =
				typeof op.volume === 'number' && Number.isFinite(op.volume)
					? Math.min(1, Math.max(0, op.volume))
					: 0.7;

			const musicRes = await editorFetchMusic({
				prompt: mood,
				duration: durationInSeconds,
			});
			if (!musicRes.ok) {
				let detail = 'Failed to generate music';
				try {
					const errorJson = (await musicRes.json()) as {detail?: unknown};
					if (typeof errorJson.detail === 'string') {
						detail = errorJson.detail;
					} else if (errorJson.detail) {
						detail = JSON.stringify(errorJson.detail);
					}
				} catch {
					// ignore parse failures and fall back to default message
				}
				throw new Error(detail);
			}

			const musicJson = (await musicRes.json()) as {
				url?: string;
				audioUrl?: string;
			};
			const audioUrl = musicJson.url || musicJson.audioUrl;
			if (!audioUrl) {
				throw new Error('Music generation did not return an audio URL');
			}

			const assetId = generateRandomId(10);
			const itemId = generateRandomId(10);
			const audioAsset = {
				id: assetId,
				type: 'audio' as const,
				durationInSeconds,
				filename: `generated-music-${Date.now()}.mp3`,
				remoteUrl: audioUrl,
				remoteFileKey: null,
				size: 0,
				mimeType: 'audio/mpeg',
			};
			const audioItem = {
				id: itemId,
				type: 'audio' as const,
				assetId,
				durationInFrames: Math.max(1, Math.round(durationInSeconds * fps)),
				from: 0,
				top: 0,
				left: 0,
				width: 100,
				height: 100,
				opacity: 1,
				isDraggingInTimeline: false,
				audioStartFromInSeconds: 0,
				decibelAdjustment: Math.min(
					MAX_VOLUME_DB,
					Math.max(MIN_VOLUME_DB, volumeToDecibel(volume)),
				),
				playbackRate: 1,
				audioFadeInDurationInSeconds: 0,
				audioFadeOutDurationInSeconds: 0,
			};

			let stateWithAsset = addAssetToState({state: s, asset: audioAsset});
			stateWithAsset = {
				...stateWithAsset,
				assetStatus: {
					...stateWithAsset.assetStatus,
					[assetId]: {type: 'uploaded'},
				},
			};
			s = addItem({
				state: stateWithAsset,
				item: audioItem,
				select: false,
				position: {type: 'back'},
			});
			continue;
		}

		if (op.op === 'add_captions') {
			const primaryVideo = Object.values(s.undoableState.items)
				.filter((item): item is Extract<EditorStarterItem, {type: 'video'}> => item.type === 'video')
				.sort((a, b) => a.from - b.from || b.durationInFrames - a.durationInFrames)[0];
			if (!primaryVideo) {
				throw new Error('No primary video clip found to generate captions from');
			}

			const videoAsset = s.undoableState.assets[primaryVideo.assetId];
			if (!videoAsset || videoAsset.type !== 'video' || !videoAsset.remoteUrl) {
				throw new Error('Primary video source is unavailable for caption generation');
			}

			const captionItemId = generateRandomId(10);
			const setStateShim: SetStateLike = ({update}) => {
				if (typeof update === 'function') {
					s = update(s);
					options?.setState?.({update, commitToUndoStack: false});
				} else {
					s = update;
					options?.setState?.({update, commitToUndoStack: false});
				}
			};

			const captions = await getCaptions({
				src: videoAsset.remoteUrl,
				setState: setStateShim,
				asset: videoAsset,
				captionItemId,
			});

			if (!captions || captions.length === 0) {
				throw new Error('Caption generation returned no captions');
			}

			const videoTrackIndex = s.undoableState.tracks.findIndex((track) =>
				track.items.some((id) => id === primaryVideo.id),
			);
			if (videoTrackIndex === -1) {
				throw new Error('Could not find timeline track for the primary video clip');
			}

			const style = op.style ?? 'default';
			const placement = op.position ?? 'bottom';
			const highlightWords = op.highlight_words ?? false;
			const compositionWidth = s.undoableState.compositionWidth;
			const compositionHeight = s.undoableState.compositionHeight;
			const width = Math.min(compositionWidth, 900) - 40;
			const baseColor = '#FFFFFF';
			const stylePreset =
				style === 'bold'
					? {fontSize: 88, weight: '800', strokeWidth: 5}
					: style === 'minimal'
						? {fontSize: 62, weight: '500', strokeWidth: 2}
						: {fontSize: 80, weight: '600', strokeWidth: 4};
			const topByPlacement: Record<'bottom' | 'top' | 'center', number> = {
				top: Math.round(compositionHeight * 0.15),
				center: Math.round(compositionHeight * 0.45),
				bottom: Math.round(compositionHeight * 0.75),
			};
			const captionStartInSeconds = primaryVideo.videoStartFromInSeconds ?? 0;
			const lastCaption = captions[captions.length - 1];
			const captionEndInSeconds = (lastCaption?.endMs ?? 0) / 1000;
			const durationInFrames = Math.max(
				1,
				Math.round((captionEndInSeconds - captionStartInSeconds) * fps),
			);

			const captionResult = addCaptionAsset({
				state: s,
				captions,
				filename: 'captions.srt',
			});

			s = addItem({
				state: captionResult.state,
				item: {
					type: 'captions',
					assetId: captionResult.asset.id,
					durationInFrames,
					from: primaryVideo.from,
					height: Math.round(stylePreset.fontSize * 1.2 * 2),
					id: captionItemId,
					isDraggingInTimeline: false,
					left: (compositionWidth - width) / 2,
					top: topByPlacement[placement],
					width,
					opacity: 1,
					fontFamily: 'TikTok Sans',
					fontStyle: {
						variant: 'normal',
						weight: stylePreset.weight,
					},
					rotation: 0,
					lineHeight: 1.2,
					letterSpacing: 0,
					fontSize: stylePreset.fontSize,
					align: 'center',
					color: baseColor,
					highlightColor: highlightWords
						? DEFAULT_CAPTION_HIGHLIGHT_COLOR
						: baseColor,
					direction: 'ltr',
					pageDurationInMilliseconds: 2000,
					captionStartInSeconds,
					strokeWidth: stylePreset.strokeWidth,
					strokeColor: 'black',
					maxLines: 2,
					fadeInDurationInSeconds: 0,
					fadeOutDurationInSeconds: 0,
				},
				select: true,
				position: {
					type: 'insert-track-before',
					trackIndex: videoTrackIndex,
				},
			});
			continue;
		}

		if (op.op === 'set_caption_style') {
			const item = s.undoableState.items[op.itemId];
			if (!item || item.type !== 'captions') {
				continue;
			}
			s = changeItem(s, op.itemId, (i: EditorStarterItem) => {
				if (i.type !== 'captions') {
					return i;
				}
				const updated = {...i};
				if (op.color !== undefined) updated.color = op.color;
				if (op.highlightColor !== undefined) updated.highlightColor = op.highlightColor;
				if (op.strokeColor !== undefined) updated.strokeColor = op.strokeColor;
				if (typeof op.strokeWidth === 'number') updated.strokeWidth = Math.max(0, op.strokeWidth);
				if (op.strokeMode !== undefined) updated.strokeMode = op.strokeMode;
				if (op.shadowColor !== undefined) updated.shadowColor = op.shadowColor;
				if (typeof op.shadowBlur === 'number') updated.shadowBlur = Math.max(0, op.shadowBlur);
				if (typeof op.shadowOffsetX === 'number') updated.shadowOffsetX = op.shadowOffsetX;
				if (typeof op.shadowOffsetY === 'number') updated.shadowOffsetY = op.shadowOffsetY;
				if (typeof op.fontSize === 'number') updated.fontSize = Math.max(8, op.fontSize);
				if (typeof op.fontFamily === 'string') updated.fontFamily = op.fontFamily;
				if (typeof op.maxLines === 'number') updated.maxLines = Math.max(1, Math.min(4, op.maxLines));
				if (typeof op.pageDurationInMilliseconds === 'number') updated.pageDurationInMilliseconds = Math.max(200, op.pageDurationInMilliseconds);
				return updated;
			});
			continue;
		}

		if (op.op === 'set_text_content') {
			const item = s.undoableState.items[op.itemId];
			if (!item || item.type !== 'text') {
				continue;
			}
			const text = op.text.trim().slice(0, MAX_TEXT_LEN);
			if (!text) {
				continue;
			}
			s = changeItem(s, op.itemId, (i: EditorStarterItem) => {
				if (i.type !== 'text') {
					return i;
				}
				return {...i, text};
			});
			continue;
		}

		if (op.op === 'set_position_size') {
			const item = s.undoableState.items[op.itemId];
			if (!item) {
				continue;
			}
			s = changeItem(s, op.itemId, (i: EditorStarterItem) => ({
				...i,
				left:
					typeof op.left === 'number' && Number.isFinite(op.left)
						? Math.round(op.left)
						: i.left,
				top:
					typeof op.top === 'number' && Number.isFinite(op.top)
						? Math.round(op.top)
						: i.top,
				width:
					typeof op.width === 'number' && Number.isFinite(op.width)
						? Math.max(1, Math.round(op.width))
						: i.width,
				height:
					typeof op.height === 'number' && Number.isFinite(op.height)
						? Math.max(1, Math.round(op.height))
						: i.height,
			}));
			continue;
		}

		if (op.op === 'set_media_start') {
			const item = s.undoableState.items[op.itemId];
			if (!item) {
				continue;
			}
			const mediaStartInSeconds = Math.max(0, op.mediaStartInSeconds);
			s = changeItem(s, op.itemId, (i: EditorStarterItem) => {
				if (i.type === 'video') {
					return {...i, videoStartFromInSeconds: mediaStartInSeconds};
				}
				if (i.type === 'gif') {
					return {...i, gifStartFromInSeconds: mediaStartInSeconds};
				}
				if (i.type === 'audio') {
					return {...i, audioStartFromInSeconds: mediaStartInSeconds};
				}
				return i;
			});
			continue;
		}

		const item = s.undoableState.items[op.itemId];
		if (!item) {
			continue;
		}

		if (op.op === 'set_opacity') {
			const opacity = Math.min(1, Math.max(0, op.opacity));
			s = changeItem(s, op.itemId, (i: EditorStarterItem) => ({
				...i,
				opacity,
			}));
		} else if (op.op === 'set_playback_rate') {
			if (
				item.type !== 'video' &&
				item.type !== 'gif' &&
				item.type !== 'audio'
			) {
				continue;
			}
			const playbackRate = Math.min(
				MAX_RATE,
				Math.max(MIN_RATE, op.playbackRate),
			);
			s = changeItem(s, op.itemId, (i: EditorStarterItem) => {
				if (i.type === 'video' || i.type === 'gif' || i.type === 'audio') {
					return {...i, playbackRate};
				}
				return i;
			});
		} else if (op.op === 'set_volume_db') {
			if (item.type !== 'video' && item.type !== 'audio') {
				continue;
			}
			const decibelAdjustment = Math.min(
				MAX_VOLUME_DB,
				Math.max(MIN_VOLUME_DB, op.decibelAdjustment),
			);
			s = changeItem(s, op.itemId, (i: EditorStarterItem) => {
				if (i.type === 'video' || i.type === 'audio') {
					return {...i, decibelAdjustment};
				}
				return i;
			});
		} else if (op.op === 'set_fade') {
			if (
				item.type !== 'video' &&
				item.type !== 'gif' &&
				item.type !== 'image' &&
				item.type !== 'text'
			) {
				continue;
			}
			s = changeItem(s, op.itemId, (i: EditorStarterItem) => {
				if (
					i.type !== 'video' &&
					i.type !== 'gif' &&
					i.type !== 'image' &&
					i.type !== 'text'
				) {
					return i;
				}
				const clipDurationInSeconds = i.durationInFrames / fps;
				const minGap = 1 / fps;
				let fadeIn = i.fadeInDurationInSeconds;
				let fadeOut = i.fadeOutDurationInSeconds;
				if (
					typeof op.fadeInDurationInSeconds === 'number' &&
					Number.isFinite(op.fadeInDurationInSeconds)
				) {
					const maxFadeIn = Math.max(0, clipDurationInSeconds - fadeOut - minGap);
					fadeIn = Math.min(maxFadeIn, Math.max(0, op.fadeInDurationInSeconds));
				}
				if (
					typeof op.fadeOutDurationInSeconds === 'number' &&
					Number.isFinite(op.fadeOutDurationInSeconds)
				) {
					const maxFadeOut = Math.max(0, clipDurationInSeconds - fadeIn - minGap);
					fadeOut = Math.min(maxFadeOut, Math.max(0, op.fadeOutDurationInSeconds));
				}
				return {
					...i,
					fadeInDurationInSeconds: fadeIn,
					fadeOutDurationInSeconds: fadeOut,
				};
			});
		} else if (op.op === 'set_audio_fade') {
			if (item.type !== 'video' && item.type !== 'audio') {
				continue;
			}
			s = changeItem(s, op.itemId, (i: EditorStarterItem) => {
				if (i.type !== 'video' && i.type !== 'audio') {
					return i;
				}
				const clipDurationInSeconds = i.durationInFrames / fps;
				const minGap = 1 / fps;
				let fadeIn = i.audioFadeInDurationInSeconds;
				let fadeOut = i.audioFadeOutDurationInSeconds;
				if (
					typeof op.audioFadeInDurationInSeconds === 'number' &&
					Number.isFinite(op.audioFadeInDurationInSeconds)
				) {
					const maxFadeIn = Math.max(0, clipDurationInSeconds - fadeOut - minGap);
					fadeIn = Math.min(
						maxFadeIn,
						Math.max(0, op.audioFadeInDurationInSeconds),
					);
				}
				if (
					typeof op.audioFadeOutDurationInSeconds === 'number' &&
					Number.isFinite(op.audioFadeOutDurationInSeconds)
				) {
					const maxFadeOut = Math.max(0, clipDurationInSeconds - fadeIn - minGap);
					fadeOut = Math.min(
						maxFadeOut,
						Math.max(0, op.audioFadeOutDurationInSeconds),
					);
				}
				return {
					...i,
					audioFadeInDurationInSeconds: fadeIn,
					audioFadeOutDurationInSeconds: fadeOut,
				};
			});
		}
	}

	return s;
}

const formatNum = (value: number, digits = 2) => value.toFixed(digits);

const fmtFrames = (value: number) => `${Math.round(value)} fr`;
const fmtSeconds = (value: number) => `${formatNum(value, 2)} s`;
const fmtPercent = (value: number) => `${Math.round(value * 100)}%`;
const fmtDb = (value: number) => `${formatNum(value, 1)} dB`;
const fmtPx = (value: number) => `${Math.round(value)} px`;

export function summarizeAiEditOpsForPreview(
	state: EditorState,
	ops: AiEditOp[],
): AiEditPreviewEntry[] {
	return ops.map((op) => {
		if (op.op === 'delete_items') {
			const existing = op.itemIds.filter((id) =>
				Boolean(state.undoableState.items[id]),
			);
			return {
				title: `Delete ${existing.length} item${existing.length === 1 ? '' : 's'}`,
				rows: [
					{
						field: 'itemIds',
						before: existing.join(', ') || '-',
						after: '(removed)',
					},
				],
			};
		}
		if (op.op === 'add_text') {
			const fromValue =
				typeof op.from === 'number' && Number.isFinite(op.from)
					? Math.max(0, Math.round(op.from))
					: null;
			const durationValue =
				typeof op.durationInFrames === 'number' &&
				Number.isFinite(op.durationInFrames)
					? Math.max(1, Math.round(op.durationInFrames))
					: null;
			return {
				title: 'Add text item',
				rows: [
					{
						field: 'text',
						before: '(new)',
						after: op.text.trim().slice(0, 120) || '(empty)',
					},
					{
						field: 'from',
						before: '(auto)',
						after: fromValue === null ? '(auto)' : fmtFrames(fromValue),
					},
					{
						field: 'duration',
						before: '(auto)',
						after: durationValue === null ? '(auto)' : fmtFrames(durationValue),
					},
				],
			};
		}
		if (op.op === 'add_music') {
			const compositionDurationInFrames = getCompositionDuration(
				Object.values(state.undoableState.items),
			);
			const fallbackDurationInSeconds = Math.max(
				1,
				compositionDurationInFrames / state.undoableState.fps,
			);
			return {
				title: 'Add background music',
				rows: [
					{
						field: 'mood',
						before: '(auto)',
						after: op.mood?.trim() || 'cinematic',
					},
					{
						field: 'duration',
						before: '(video duration)',
						after: fmtSeconds(
							typeof op.duration === 'number' && Number.isFinite(op.duration)
								? Math.max(1, op.duration)
								: fallbackDurationInSeconds,
						),
					},
					{
						field: 'volume',
						before: '(default)',
						after: fmtPercent(
							typeof op.volume === 'number' && Number.isFinite(op.volume)
								? Math.min(1, Math.max(0, op.volume))
								: 0.7,
						),
					},
				],
			};
		}
		if (op.op === 'add_captions') {
			return {
				title: 'Add captions',
				rows: [
					{
						field: 'language',
						before: '(default)',
						after: op.language?.trim() || 'en',
					},
					{
						field: 'style',
						before: '(default)',
						after: op.style || 'default',
					},
					{
						field: 'position',
						before: '(default)',
						after: op.position || 'bottom',
					},
					{
						field: 'highlight_words',
						before: '(default)',
						after: String(op.highlight_words ?? false),
					},
				],
			};
		}
		if (op.op === 'set_caption_style') {
			const captionItem = state.undoableState.items[op.itemId];
			const rows: AiEditPreviewRow[] = [];
			const addRow = (field: string, before: string, after: string) => {
				if (before !== after) rows.push({field, before, after});
			};
			if (captionItem && captionItem.type === 'captions') {
				if (op.color !== undefined) addRow('color', captionItem.color, op.color);
				if (op.highlightColor !== undefined) addRow('highlightColor', captionItem.highlightColor, op.highlightColor);
				if (op.strokeColor !== undefined) addRow('strokeColor', captionItem.strokeColor, op.strokeColor);
				if (op.strokeWidth !== undefined) addRow('strokeWidth', String(captionItem.strokeWidth), String(op.strokeWidth));
				if (op.strokeMode !== undefined) addRow('strokeMode', captionItem.strokeMode ?? 'solid', op.strokeMode);
				if (op.fontSize !== undefined) addRow('fontSize', String(captionItem.fontSize), String(op.fontSize));
				if (op.fontFamily !== undefined) addRow('fontFamily', captionItem.fontFamily, op.fontFamily);
				if (op.maxLines !== undefined) addRow('maxLines', String(captionItem.maxLines), String(op.maxLines));
			}
			return {
				title: `Update caption style`,
				rows: rows.length > 0 ? rows : [{field: 'style', before: '(current)', after: '(updated)'}],
			};
		}
		const item = state.undoableState.items[op.itemId];
		if (!item) {
			return {
				title: `Skip ${op.op}`,
				rows: [],
				note: `Item "${op.itemId}" was not found`,
			};
		}
		if (op.op === 'set_opacity') {
			return {
				title: `Set opacity (${op.itemId})`,
				rows: [
					{
						field: 'opacity',
						before: fmtPercent(item.opacity),
						after: fmtPercent(Math.min(1, Math.max(0, op.opacity))),
					},
				],
			};
		}
		if (op.op === 'set_playback_rate') {
			if (item.type !== 'video' && item.type !== 'gif' && item.type !== 'audio') {
				return {
					title: `Skip playback rate (${op.itemId})`,
					rows: [],
					note: 'Unsupported item type',
				};
			}
			return {
				title: `Set playback rate (${op.itemId})`,
				rows: [
					{
						field: 'playbackRate',
						before: `${formatNum(item.playbackRate, 2)}x`,
						after: `${formatNum(
							Math.min(MAX_RATE, Math.max(MIN_RATE, op.playbackRate)),
							2,
						)}x`,
					},
				],
			};
		}
		if (op.op === 'set_volume_db') {
			if (item.type !== 'video' && item.type !== 'audio') {
				return {
					title: `Skip volume (${op.itemId})`,
					rows: [],
					note: 'Unsupported item type',
				};
			}
			return {
				title: `Set volume (${op.itemId})`,
				rows: [
					{
						field: 'decibelAdjustment',
						before: fmtDb(item.decibelAdjustment),
						after: fmtDb(
							Math.min(MAX_VOLUME_DB, Math.max(MIN_VOLUME_DB, op.decibelAdjustment)),
						),
					},
				],
			};
		}
		if (op.op === 'set_timeline_span') {
			return {
				title: `Set timeline span (${op.itemId})`,
				rows: [
					{
						field: 'from',
						before: fmtFrames(item.from),
						after:
							typeof op.from === 'number' && Number.isFinite(op.from)
								? fmtFrames(Math.max(0, Math.round(op.from)))
								: '(unchanged)',
					},
					{
						field: 'duration',
						before: fmtFrames(item.durationInFrames),
						after:
							typeof op.durationInFrames === 'number' &&
							Number.isFinite(op.durationInFrames)
								? fmtFrames(Math.max(1, Math.round(op.durationInFrames)))
								: '(unchanged)',
					},
				],
			};
		}
		if (op.op === 'set_fade') {
			if (
				item.type !== 'video' &&
				item.type !== 'gif' &&
				item.type !== 'image' &&
				item.type !== 'text'
			) {
				return {
					title: `Skip visual fade (${op.itemId})`,
					rows: [],
					note: 'Unsupported item type',
				};
			}
			const fadeInNext =
				typeof op.fadeInDurationInSeconds === 'number'
					? op.fadeInDurationInSeconds
					: item.fadeInDurationInSeconds;
			const fadeOutNext =
				typeof op.fadeOutDurationInSeconds === 'number'
					? op.fadeOutDurationInSeconds
					: item.fadeOutDurationInSeconds;
			return {
				title: `Set visual fade (${op.itemId})`,
				rows: [
					{
						field: 'fadeIn',
						before: fmtSeconds(item.fadeInDurationInSeconds),
						after: fmtSeconds(Math.max(0, fadeInNext)),
					},
					{
						field: 'fadeOut',
						before: fmtSeconds(item.fadeOutDurationInSeconds),
						after: fmtSeconds(Math.max(0, fadeOutNext)),
					},
				],
			};
		}
		if (op.op === 'set_audio_fade') {
			if (item.type !== 'video' && item.type !== 'audio') {
				return {
					title: `Skip audio fade (${op.itemId})`,
					rows: [],
					note: 'Unsupported item type',
				};
			}
			const fadeInNext =
				typeof op.audioFadeInDurationInSeconds === 'number'
					? op.audioFadeInDurationInSeconds
					: item.audioFadeInDurationInSeconds;
			const fadeOutNext =
				typeof op.audioFadeOutDurationInSeconds === 'number'
					? op.audioFadeOutDurationInSeconds
					: item.audioFadeOutDurationInSeconds;
			return {
				title: `Set audio fade (${op.itemId})`,
				rows: [
					{
						field: 'audioFadeIn',
						before: fmtSeconds(item.audioFadeInDurationInSeconds),
						after: fmtSeconds(Math.max(0, fadeInNext)),
					},
					{
						field: 'audioFadeOut',
						before: fmtSeconds(item.audioFadeOutDurationInSeconds),
						after: fmtSeconds(Math.max(0, fadeOutNext)),
					},
				],
			};
		}
		if (op.op === 'set_text_content') {
			if (item.type !== 'text') {
				return {
					title: `Skip text content (${op.itemId})`,
					rows: [],
					note: 'Unsupported item type',
				};
			}
			return {
				title: `Set text content (${op.itemId})`,
				rows: [
					{
						field: 'text',
						before: item.text.slice(0, 120) || '(empty)',
						after: op.text.trim().slice(0, 120) || '(empty)',
					},
				],
			};
		}
		if (op.op === 'set_position_size') {
			return {
				title: `Set position/size (${op.itemId})`,
				rows: [
					{
						field: 'left',
						before: fmtPx(item.left),
						after:
							typeof op.left === 'number' && Number.isFinite(op.left)
								? fmtPx(op.left)
								: '(unchanged)',
					},
					{
						field: 'top',
						before: fmtPx(item.top),
						after:
							typeof op.top === 'number' && Number.isFinite(op.top)
								? fmtPx(op.top)
								: '(unchanged)',
					},
					{
						field: 'width',
						before: fmtPx(item.width),
						after:
							typeof op.width === 'number' && Number.isFinite(op.width)
								? fmtPx(Math.max(1, op.width))
								: '(unchanged)',
					},
					{
						field: 'height',
						before: fmtPx(item.height),
						after:
							typeof op.height === 'number' && Number.isFinite(op.height)
								? fmtPx(Math.max(1, op.height))
								: '(unchanged)',
					},
				],
			};
		}
		if (op.op === 'set_media_start') {
			if (item.type === 'video') {
				return {
					title: `Set media start (${op.itemId})`,
					rows: [
						{
							field: 'videoStartFromInSeconds',
							before: fmtSeconds(item.videoStartFromInSeconds),
							after: fmtSeconds(Math.max(0, op.mediaStartInSeconds)),
						},
					],
				};
			}
			if (item.type === 'gif') {
				return {
					title: `Set media start (${op.itemId})`,
					rows: [
						{
							field: 'gifStartFromInSeconds',
							before: fmtSeconds(item.gifStartFromInSeconds),
							after: fmtSeconds(Math.max(0, op.mediaStartInSeconds)),
						},
					],
				};
			}
			if (item.type === 'audio') {
				return {
					title: `Set media start (${op.itemId})`,
					rows: [
						{
							field: 'audioStartFromInSeconds',
							before: fmtSeconds(item.audioStartFromInSeconds),
							after: fmtSeconds(Math.max(0, op.mediaStartInSeconds)),
						},
					],
				};
			}
			return {
				title: `Skip media start (${op.itemId})`,
				rows: [],
				note: 'Unsupported item type',
			};
		}
		const _never: never = op;
		return {
			title: 'Unhandled operation',
			rows: [],
			note: JSON.stringify(_never),
		};
	});
}
