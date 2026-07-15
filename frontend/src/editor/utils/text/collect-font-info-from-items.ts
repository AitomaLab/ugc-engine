import type {FontInfo} from '@remotion/google-fonts/index';
import {GOOGLE_FONTS_DATABASE} from '../../data/google-fonts';
import type {EditorStarterItem} from '../../items/item-type';

const FALLBACK_FONT_FAMILY = 'Roboto';

/**
 * `fontFamily` is usually a bare family ("Anton"), but callers occasionally hand
 * us a CSS stack ("Anton, Impact, sans-serif"). The database is keyed on the bare
 * family, so take the first entry and strip quotes.
 */
export const normalizeFontFamily = (fontFamily: string | undefined): string => {
	if (!fontFamily) {
		return FALLBACK_FONT_FAMILY;
	}
	const first = fontFamily.split(',')[0].trim().replace(/^['"]|['"]$/g, '');
	return first || FALLBACK_FONT_FAMILY;
};

/**
 * Runs inside Root.tsx's calculateMetadata, i.e. on the render path only.
 *
 * A font we can't resolve degrades to Roboto with a warning rather than throwing:
 * fonts are data, and one odd item shouldn't fail an entire render. An unknown
 * *item type* still throws — that's a code bug, and it should be loud.
 */
export const collectFontInfoFromItems = (items: EditorStarterItem[]) => {
	const fontInfos: Record<string, FontInfo> = {};

	for (const item of Object.values(items)) {
		if (item.type === 'text' || item.type === 'captions') {
			const family = normalizeFontFamily(item.fontFamily);
			const info =
				GOOGLE_FONTS_DATABASE.find((font) => font.fontFamily === family) ??
				GOOGLE_FONTS_DATABASE.find(
					(font) => font.fontFamily === FALLBACK_FONT_FAMILY,
				);

			if (!info) {
				throw new Error(
					`Font ${family} not found, and neither is the ${FALLBACK_FONT_FAMILY} fallback`,
				);
			}
			if (info.fontFamily !== family) {
				// Surfaced in render logs via server.js's onBrowserLog.
				console.warn(
					`[fonts] "${item.fontFamily}" is not a known Google Font — falling back to ${info.fontFamily}`,
				);
			}

			// Key on what the item will actually ask for at render time — the
			// layers look up `context[item.fontFamily]` verbatim — as well as the
			// normalized family. A miss there throws inside cancelRender.
			fontInfos[family] = info;
			if (item.fontFamily) {
				fontInfos[item.fontFamily] = info;
			}
		} else if (
			// Type safety check, add item types here that don't have text here
			item.type === 'audio' ||
			item.type === 'gif' ||
			item.type === 'image' ||
			item.type === 'solid' ||
			item.type === 'video'
		) {
			continue;
		} else {
			throw new Error('Invalid item type: ' + (item satisfies never));
		}
	}

	return fontInfos;
};
