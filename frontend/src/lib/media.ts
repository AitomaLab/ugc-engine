/**
 * Shared media URL helpers.
 *
 * Supabase Storage exposes an on-the-fly image transformation endpoint at
 * /storage/v1/render/image/public/. Rewriting public object URLs through it
 * lets cards ship a small, CDN-cached, auto-WebP thumbnail instead of the
 * full-resolution original (WebP conversion is automatic based on the
 * browser's Accept header — no format param needed).
 */

/**
 * Thumbnail URL for a Supabase-hosted image. Pass-through for any other URL.
 *
 * resize=contain (default): both width AND height bounds keep the aspect
 * ratio proportional (image fits inside the box, longest side <= width).
 * Without both bounds OR with resize=cover, Supabase's renderer can return
 * a broken width-clamped/height-untouched image (e.g. 1792x2560 -> 480x2560)
 * which makes intrinsic-dimension measurement nonsensical.
 *
 * resize=cover: fills the box, cropping overflow — use for fixed-ratio
 * card grids where cropping is intended.
 */
export function thumbUrl(
    url: string | null | undefined,
    width: number,
    resize: 'contain' | 'cover' = 'contain',
): string {
    if (!url) return url || '';
    if (url.includes('/storage/v1/object/public/')) {
        const rewritten = url.replace('/storage/v1/object/public/', '/storage/v1/render/image/public/');
        const sep = rewritten.includes('?') ? '&' : '?';
        if (resize === 'cover') {
            return `${rewritten}${sep}width=${width}&quality=70&resize=cover`;
        }
        return `${rewritten}${sep}width=${width}&height=${width}&resize=contain&quality=70`;
    }
    return url;
}

/** True when the URL points at a video file (by extension). */
export function isVideoUrl(url: string | null | undefined): boolean {
    return /\.(mp4|webm|mov)(\?|#|$)/i.test(url || '');
}

/**
 * Best raw poster image URL for a video job/asset, or null when none exists.
 * Prefers the cached first-frame thumbnail, then generation previews —
 * never returns a video URL. Callers pass the result through thumbUrl()
 * (HoverPlayVideo does this automatically).
 */
export function videoPosterCandidate(asset: {
    thumbnail_url?: string | null;
    preview_url?: string | null;
    reference_image_url?: string | null;
}): string | null {
    for (const candidate of [asset.thumbnail_url, asset.preview_url, asset.reference_image_url]) {
        if (candidate && !isVideoUrl(candidate)) return candidate;
    }
    return null;
}
