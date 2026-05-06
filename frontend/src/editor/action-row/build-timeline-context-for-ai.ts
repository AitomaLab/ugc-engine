import {EditorStarterItem} from '../items/item-type';
import {EditorState} from '../state/types';
import {getCompositionDuration} from '../utils/get-composition-duration';

function summarizeItem(item: EditorStarterItem): Record<string, unknown> {
	const base: Record<string, unknown> = {
		id: item.id,
		type: item.type,
		from: item.from,
		durationInFrames: item.durationInFrames,
		opacity: item.opacity,
	};
	if (item.type === 'text') {
		const t = item.text.replace(/\s+/g, ' ').trim();
		base.textPreview = t.length > 120 ? `${t.slice(0, 120)}…` : t;
		base.color = item.color;
		base.fontSize = item.fontSize;
		base.align = item.align;
		base.fadeInDurationInSeconds = item.fadeInDurationInSeconds;
		base.fadeOutDurationInSeconds = item.fadeOutDurationInSeconds;
	}
	if (item.type === 'video' || item.type === 'audio' || item.type === 'gif') {
		base.playbackRate = item.playbackRate;
	}
	if (item.type === 'video') {
		base.decibelAdjustment = item.decibelAdjustment;
		base.audioFadeInDurationInSeconds = item.audioFadeInDurationInSeconds;
		base.audioFadeOutDurationInSeconds = item.audioFadeOutDurationInSeconds;
		base.fadeInDurationInSeconds = item.fadeInDurationInSeconds;
		base.fadeOutDurationInSeconds = item.fadeOutDurationInSeconds;
		base.videoStartFromInSeconds = item.videoStartFromInSeconds;
		base.assetId = item.assetId;
	}
	if (item.type === 'gif') {
		base.fadeInDurationInSeconds = item.fadeInDurationInSeconds;
		base.fadeOutDurationInSeconds = item.fadeOutDurationInSeconds;
		base.gifStartFromInSeconds = item.gifStartFromInSeconds;
		base.assetId = item.assetId;
	}
	if (item.type === 'image') {
		base.fadeInDurationInSeconds = item.fadeInDurationInSeconds;
		base.fadeOutDurationInSeconds = item.fadeOutDurationInSeconds;
		base.assetId = item.assetId;
	}
	if (item.type === 'audio') {
		base.decibelAdjustment = item.decibelAdjustment;
		base.audioFadeInDurationInSeconds = item.audioFadeInDurationInSeconds;
		base.audioFadeOutDurationInSeconds = item.audioFadeOutDurationInSeconds;
		base.audioStartFromInSeconds = item.audioStartFromInSeconds;
		base.assetId = item.assetId;
	}
	if (item.type === 'captions') {
		base.assetId = item.assetId;
		base.fontFamily = item.fontFamily;
		base.fontSize = item.fontSize;
		base.color = item.color;
		base.highlightColor = item.highlightColor;
		base.strokeWidth = item.strokeWidth;
		base.strokeColor = item.strokeColor;
		base.strokeMode = item.strokeMode ?? 'solid';
		base.shadowColor = item.shadowColor;
		base.shadowBlur = item.shadowBlur;
		base.shadowOffsetX = item.shadowOffsetX;
		base.shadowOffsetY = item.shadowOffsetY;
		base.maxLines = item.maxLines;
		base.pageDurationInMilliseconds = item.pageDurationInMilliseconds;
		base.left = item.left;
		base.top = item.top;
		base.width = item.width;
		base.height = item.height;
	}
	return base;
}

/**
 * Compact JSON summary of the timeline for the AI (no URLs or asset blobs).
 */
export function buildTimelineContextForAi(state: EditorState): string {
	const {tracks, items, fps, compositionWidth, compositionHeight} =
		state.undoableState;
	const compositionDurationInFrames = getCompositionDuration(
		Object.values(items),
	);
	const itemToTrack = new Map<string, string>();
	for (const track of tracks) {
		for (const itemId of track.items) {
			itemToTrack.set(itemId, track.id);
		}
	}
	const payload = {
		fps,
		compositionWidth,
		compositionHeight,
		compositionDurationInFrames,
		selectedItemIds: state.selectedItems,
		tracks: tracks.map((t) => ({
			id: t.id,
			hidden: t.hidden,
			muted: t.muted,
			itemIds: t.items,
		})),
		items: Object.fromEntries(
			Object.entries(items).map(([id, item]) => [
				id,
				{
					...summarizeItem(item),
					trackId: itemToTrack.get(id) ?? null,
				},
			]),
		),
	};
	return JSON.stringify(payload, null, 0);
}
