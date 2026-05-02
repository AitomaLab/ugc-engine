'use client';

import { useState, useRef, useEffect, useCallback } from 'react';

/**
 * VideoThumbnail — lightweight video preview that avoids loading full video files.
 *
 * Strategy:
 * 1. If `previewUrl` (image) is provided → render <img> instantly (fastest).
 * 2. Otherwise, load the video in a hidden <video> element, wait for the first
 *    frame to render, then show it. Uses a global sequential queue so we never
 *    saturate the network with concurrent video downloads.
 * 3. Shows a shimmer loading animation while waiting.
 */

/* ── Global sequential queue ────────────────────────────────────────────── */
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

/* ── Component ──────────────────────────────────────────────────────────── */
interface Props {
  videoUrl?: string;
  previewUrl?: string;
  alt?: string;
  style?: React.CSSProperties;
}

export default function VideoThumbnail({ videoUrl, previewUrl, alt = '', style }: Props) {
  const [loaded, setLoaded] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const [shouldLoad, setShouldLoad] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

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
      { rootMargin: '100px' } // Start loading slightly before visible
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // If we have a previewUrl (image), skip the queue entirely
  const hasImagePreview = !!previewUrl;

  // Enqueue video loading when visible and no image preview
  useEffect(() => {
    if (!isVisible || hasImagePreview || !videoUrl || shouldLoad) return;
    enqueue(() => setShouldLoad(true));
    return () => {
      // If unmounted before loaded, free the queue slot
      if (!loaded) dequeue();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isVisible, hasImagePreview, videoUrl]);

  const handleVideoLoaded = useCallback(() => {
    setLoaded(true);
    dequeue();
  }, []);

  const handleVideoError = useCallback(() => {
    // Free queue slot on error too
    setLoaded(true); // stop shimmer
    dequeue();
  }, []);

  const baseStyle: React.CSSProperties = {
    position: 'absolute',
    inset: 0,
    width: '100%',
    height: '100%',
    objectFit: 'cover',
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
              animation: 'shimmer 1.5s ease-in-out infinite',
            }}
          />
        </div>
      )}

      {/* Image preview (instant) */}
      {hasImagePreview && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={previewUrl}
          alt={alt}
          loading="lazy"
          onLoad={() => setLoaded(true)}
          onError={() => setLoaded(true)}
          style={{ ...baseStyle, opacity: loaded ? 1 : 0, transition: 'opacity 0.2s ease' }}
        />
      )}

      {/* Video preview (sequential queue) */}
      {!hasImagePreview && shouldLoad && videoUrl && (
        <video
          ref={videoRef}
          src={videoUrl}
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
        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
}
