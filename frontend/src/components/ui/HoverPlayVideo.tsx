'use client';

import { useState, CSSProperties } from 'react';
import { thumbUrl } from '@/lib/media';

interface HoverPlayVideoProps {
    /** Full video URL (mp4/webm/mov). */
    src: string;
    /** Raw poster image URL (will be passed through the Supabase transform). */
    poster?: string | null;
    posterWidth?: number;
    style?: CSSProperties;
    /** Called with the poster img once loaded (e.g. aspect-ratio measurement). */
    onPosterLoad?: (img: HTMLImageElement) => void;
    /** Called with the video element once metadata is available. */
    onVideoMetadata?: (video: HTMLVideoElement) => void;
    onError?: () => void;
}

/**
 * Video card that never downloads the MP4 until the user hovers.
 *
 * With a poster: renders a lightweight transformed <img>; the <video> is
 * mounted (and autoplays) only on hover and unmounts on leave.
 * Without a poster: falls back to <video preload="metadata"> hover-to-play
 * (the legacy behavior), so cards still render before a thumbnail exists.
 */
export function HoverPlayVideo({
    src,
    poster,
    posterWidth = 480,
    style,
    onPosterLoad,
    onVideoMetadata,
    onError,
}: HoverPlayVideoProps) {
    const [active, setActive] = useState(false);

    if (!poster) {
        return (
            <video
                src={src}
                muted
                loop
                playsInline
                preload="metadata"
                onMouseEnter={e => (e.target as HTMLVideoElement).play().catch(() => {})}
                onMouseLeave={e => { const v = e.target as HTMLVideoElement; v.pause(); v.currentTime = 0; }}
                onLoadedMetadata={e => onVideoMetadata?.(e.currentTarget)}
                onError={onError}
                style={style}
            />
        );
    }

    if (active) {
        return (
            <video
                src={src}
                muted
                loop
                playsInline
                autoPlay
                preload="auto"
                onMouseLeave={() => setActive(false)}
                onLoadedMetadata={e => onVideoMetadata?.(e.currentTarget)}
                onError={() => setActive(false)}
                style={style}
            />
        );
    }

    return (
        // eslint-disable-next-line @next/next/no-img-element
        <img
            src={thumbUrl(poster, posterWidth)}
            alt=""
            loading="lazy"
            decoding="async"
            onMouseEnter={() => setActive(true)}
            onLoad={e => onPosterLoad?.(e.currentTarget)}
            onError={onError}
            style={style}
        />
    );
}
