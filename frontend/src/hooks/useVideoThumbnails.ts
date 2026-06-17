'use client';

import { useEffect, useRef, useState } from 'react';
import { creativeFetch } from '@/lib/creative-os-api';
import { isVideoUrl } from '@/lib/media';

type VideoAssetLike = {
    id: string;
    status?: string;
    final_video_url?: string | null;
    video_url?: string | null;
    thumbnail_url?: string | null;
    preview_url?: string | null;
    reference_image_url?: string | null;
};

/** Max videos per batch request — endpoint generates max 3 concurrently. */
const BATCH_LIMIT = 24;

/** Persists poster URLs across page navigations within the same session. */
const globalThumbCache = new Map<string, string>();

/**
 * Lazily generates poster thumbnails for completed videos that have no usable
 * image preview, via the existing `/creative-os/projects/video-thumbnails`
 * batch endpoint (FFmpeg first-frame, DB-cached server-side).
 *
 * Returns a map of job id -> thumbnail URL that fills in as results arrive.
 * Each id is only ever requested once per session (module-level cache).
 */
export function useVideoThumbnails(assets: VideoAssetLike[]): Record<string, string> {
    const [thumbs, setThumbs] = useState<Record<string, string>>(() => {
        const initial: Record<string, string> = {};
        for (const a of assets) {
            if (a?.id && globalThumbCache.has(a.id)) {
                initial[a.id] = globalThumbCache.get(a.id)!;
            }
        }
        return initial;
    });
    const requested = useRef<Set<string>>(new Set(globalThumbCache.keys()));

    useEffect(() => {
        const need = assets
            .filter(a => {
                if (!a?.id || requested.current.has(a.id)) return false;
                const video = a.final_video_url || a.video_url;
                if (!video || !isVideoUrl(video)) return false;
                // Skip if any image poster candidate already exists.
                for (const c of [a.thumbnail_url, a.preview_url, a.reference_image_url]) {
                    if (c && !isVideoUrl(c)) return false;
                }
                return true;
            })
            .slice(0, BATCH_LIMIT);

        if (!need.length) return;
        need.forEach(a => requested.current.add(a.id));

        (async () => {
            try {
                const result = await creativeFetch<{ thumbnails: Record<string, string> }>(
                    '/creative-os/projects/video-thumbnails',
                    {
                        method: 'POST',
                        body: JSON.stringify({
                            jobs: need.map(a => ({ id: a.id, video_url: a.final_video_url || a.video_url })),
                        }),
                    },
                );
                if (result?.thumbnails && Object.keys(result.thumbnails).length > 0) {
                    for (const [id, url] of Object.entries(result.thumbnails)) {
                        globalThumbCache.set(id, url);
                    }
                    setThumbs(prev => ({ ...prev, ...result.thumbnails }));
                }
            } catch {
                // Best-effort: cards fall back to <video preload="metadata">.
            }
        })();
    }, [assets]);

    return thumbs;
}
