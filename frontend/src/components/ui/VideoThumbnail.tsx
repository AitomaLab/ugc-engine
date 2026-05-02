'use client';

import { useState, useRef, useEffect, useCallback } from 'react';

/**
 * VideoThumbnail — lightweight video preview that avoids loading full video files.
 *
 * Strategy:
 * 1. If `previewUrl` (image) is provided → render <img> instantly (fastest).
 *    - Skips URLs ending in .mp4/.webm/.mov (those are video URLs, not images).
 * 2. Otherwise, load the video in a <video> element. Uses a global sequential
 *    queue so we never saturate the network with concurrent video downloads.
 * 3. Shows a shimmer loading animation while waiting.
 * 4. If the image fails to load, falls back to the video path.
 */

/* ── Helpers ────────────────────────────────────────────────────────── */
const VIDEO_EXTENSIONS = /\.(mp4|webm|mov|avi|mkv)(\?.*)?$/i;

function isImageUrl(url: string | undefined): boolean {
  if (!url) return false;
  // If the URL ends with a video extension (ignoring query params), it's not an image
  return !VIDEO_EXTENSIONS.test(url);
}

/* ── Global sequential queue ────────────────────────────────────────── */
// Only load MAX_CONCURRENT videos at a time to prevent network saturation.
const MAX_CONCURRENT = 2;
let activeLoads = 0;
const queue: Array<() => void> = [];

function enqueue(fn: () => void) {
  if (activeLoads < MAX_CONCURRENT) {
    activeLoads++;
    fn();
  } else {
    queue.push(fn);
  }
}

function dequeue() {
  activeLoads--;
  if (queue.length > 0 && activeLoads < MAX_CONCURRENT) {
    activeLoads++;
    const next = queue.shift()!;
    next();
  }
}

/* ── Component ──────────────────────────────────────────────────────── */
interface Props {
  videoUrl?: string;
  previewUrl?: string;
  alt?: string;
  style?: React.CSSProperties;
}

export default function VideoThumbnail({ videoUrl, previewUrl, alt = '', style }: Props) {
  // Determine if we have a valid image preview (not a video URL)
  const imagePreviewUrl = isImageUrl(previewUrl) ? previewUrl : undefined;

  const [loaded, setLoaded] = useState(false);
  const [imgFailed, setImgFailed] = useState(false);
  const [shouldLoadVideo, setShouldLoadVideo] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const enqueuedRef = useRef(false);

  // The effective video URL: use the videoUrl prop, or fall back to previewUrl
  // if it's a video URL (e.g. .mp4)
  const effectiveVideoUrl = videoUrl || (!isImageUrl(previewUrl) && previewUrl ? previewUrl : undefined);

  // Whether we need to load a video (no image preview, or image failed)
  const needsVideo = (!imagePreviewUrl || imgFailed) && !!effectiveVideoUrl;

  // Intersection Observer — only start loading when visible
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: '100px' }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Enqueue video loading when visible and needed
  useEffect(() => {
    if (!isVisible || !needsVideo || shouldLoadVideo || enqueuedRef.current) return;
    enqueuedRef.current = true;
    enqueue(() => setShouldLoadVideo(true));
  }, [isVisible, needsVideo, shouldLoadVideo]);

  const handleVideoLoaded = useCallback(() => {
    setLoaded(true);
    dequeue();
  }, []);

  const handleVideoError = useCallback(() => {
    setLoaded(true); // stop shimmer
    dequeue();
  }, []);

  const handleImgLoad = useCallback(() => {
    setLoaded(true);
  }, []);

  const handleImgError = useCallback(() => {
    // Image failed — fall back to video path
    setImgFailed(true);
  }, []);

  const baseStyle: React.CSSProperties = {
    position: 'absolute',
    inset: 0,
    width: '100%',
    height: '100%',
    objectFit: 'cover' as const,
    ...style,
  };

  return (
    <div ref={containerRef} style={{ position: 'absolute', inset: 0 }}>
      {/* Shimmer loading state */}
      {!loaded && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'linear-gradient(135deg, #f0f0f5 0%, #e8e8ee 100%)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background:
                'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%)',
              animation: 'vthumb-shimmer 1.5s ease-in-out infinite',
            }}
          />
        </div>
      )}

      {/* Image preview (instant — only if URL is actually an image) */}
      {imagePreviewUrl && !imgFailed && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={imagePreviewUrl}
          alt={alt}
          loading="lazy"
          onLoad={handleImgLoad}
          onError={handleImgError}
          style={{ ...baseStyle, opacity: loaded ? 1 : 0, transition: 'opacity 0.2s ease' }}
        />
      )}

      {/* Video preview (sequential queue) — used when no image or image failed */}
      {needsVideo && shouldLoadVideo && (
        <video
          src={effectiveVideoUrl}
          muted
          playsInline
          preload="auto"
          onLoadedData={handleVideoLoaded}
          onError={handleVideoError}
          style={{ ...baseStyle, opacity: loaded ? 1 : 0, transition: 'opacity 0.2s ease' }}
        />
      )}

      {/* Inject shimmer keyframes */}
      <style>{`
        @keyframes vthumb-shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
}
