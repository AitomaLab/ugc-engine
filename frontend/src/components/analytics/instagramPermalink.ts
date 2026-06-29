import type { AnalyticsPost } from './analytics-types';

/** IG public shortcodes include letters; numeric media PKs break embeds and BrightData. */
export function isInstagramShortcode(value: string | null | undefined): boolean {
    const s = (value || '').trim();
    if (!s || s.length < 5 || s.length > 30) return false;
    if (!/^[A-Za-z0-9_-]+$/.test(s)) return false;
    if (/^\d+$/.test(s)) return false;
    if (!/[A-Za-z]/.test(s)) return false;
    return true;
}

const IG_POST_PATH_RE = /instagram\.com\/(?:p|reel|reels|tv)\/([^/?#]+)/i;

export function shortcodeFromInstagramUrl(url: string | null | undefined): string | null {
    if (!url || url.startsWith('studio://')) return null;
    const m = url.match(IG_POST_PATH_RE);
    const code = m?.[1];
    return code && isInstagramShortcode(code) ? code : null;
}

/** Resolve a shortcode suitable for instagram.com/p/{code}/embed/. */
export function resolveInstagramEmbedShortcode(post: AnalyticsPost): string | null {
    const fromPermalink = shortcodeFromInstagramUrl(post.permalink);
    if (fromPermalink) return fromPermalink;
    const fromPostUrl = shortcodeFromInstagramUrl(post.post_url);
    if (fromPostUrl) return fromPostUrl;
    const ext = post.external_post_id;
    if (ext && isInstagramShortcode(ext)) return ext;
    return null;
}
