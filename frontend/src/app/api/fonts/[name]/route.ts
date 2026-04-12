import {NextRequest, NextResponse} from 'next/server';

/**
 * Serves Google Fonts metadata in the FontInfo format that @remotion/google-fonts expects.
 *
 * Strategy:
 * 1. Check a small hardcoded cache for commonly used fonts (instant).
 * 2. For any other font, fetch the CSS from Google Fonts API, parse out
 *    the woff2 URLs and unicode ranges, and return a proper FontInfo object.
 *
 * This avoids importing the 4MB google-fonts.ts database on the server.
 */

// In-memory cache for parsed font info (persists for the lifetime of the server)
const fontCache: Record<string, object> = {};

/**
 * Parse Google Fonts CSS into a FontInfo-compatible object.
 * Google Fonts CSS returns @font-face blocks with woff2 URLs and unicode ranges.
 */
async function fetchFontInfoFromGoogle(
	fontFamily: string,
): Promise<object | null> {
	try {
		// Request woff2 format by using a modern user agent
		const cssUrl = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(fontFamily)}:ital,wght@0,100;0,200;0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,100;1,200;1,300;1,400;1,500;1,600;1,700;1,800;1,900&display=swap`;
		const response = await fetch(cssUrl, {
			headers: {
				// Chrome user-agent to get woff2 format
				'User-Agent':
					'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
			},
		});

		if (!response.ok) {
			return null;
		}

		const css = await response.text();

		// Parse @font-face blocks
		const fontFaceRegex =
			/@font-face\s*\{([^}]+)\}/g;
		const fonts: Record<string, Record<string, Record<string, string>>> = {};
		const unicodeRanges: Record<string, string> = {};

		let match;
		while ((match = fontFaceRegex.exec(css)) !== null) {
			const block = match[1];

			// Extract properties
			const styleMatch = block.match(/font-style:\s*(\w+)/);
			const weightMatch = block.match(/font-weight:\s*(\d+)/);
			const srcMatch = block.match(
				/src:\s*url\(([^)]+\.woff2[^)]*)\)\s*format\('woff2'\)/,
			);
			const rangeMatch = block.match(/unicode-range:\s*([^;]+)/);
			const commentMatch = css
				.substring(0, match.index)
				.match(/\/\*\s*([^*]+)\s*\*\/\s*$/);

			if (!styleMatch || !weightMatch || !srcMatch) continue;

			const style = styleMatch[1]; // 'normal' or 'italic'
			const weight = weightMatch[1]; // '400', '700', etc.
			const url = srcMatch[1];
			const range = rangeMatch ? rangeMatch[1].trim() : '';
			const subset = commentMatch
				? commentMatch[1].trim()
				: `subset-${Object.keys(unicodeRanges).length}`;

			if (!fonts[style]) fonts[style] = {};
			if (!fonts[style][weight]) fonts[style][weight] = {};

			fonts[style][weight][subset] = url;
			if (range && !unicodeRanges[subset]) {
				unicodeRanges[subset] = range;
			}
		}

		if (Object.keys(fonts).length === 0) {
			return null;
		}

		const importName = fontFamily.replace(/\s+/g, '');

		return {
			fontFamily,
			importName,
			version: 'v1',
			url: cssUrl,
			unicodeRanges,
			fonts,
			subsets: Object.keys(unicodeRanges),
		};
	} catch (error) {
		console.error(`Failed to fetch font info for ${fontFamily}:`, error);
		return null;
	}
}

export async function GET(
	request: NextRequest,
	{params}: {params: Promise<{name: string}>},
) {
	const {name} = await params;

	// Check in-memory cache
	if (fontCache[name]) {
		return NextResponse.json(fontCache[name]);
	}

	// Fetch from Google Fonts API and parse
	const fontInfo = await fetchFontInfoFromGoogle(name);
	if (fontInfo) {
		fontCache[name] = fontInfo;
		return NextResponse.json(fontInfo);
	}

	return NextResponse.json({error: 'Font not found'}, {status: 404});
}
