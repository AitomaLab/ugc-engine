'use client';

import { useState, useRef, useEffect } from 'react';

/**
 * VideoThumbnail — lightweight video preview using server-generated JPEG thumbnails.
 *
 * Strategy:
 * 1. If `previewUrl` (image) is provided → render <img> (instant).
 *    - Skips URLs ending in .mp4/.webm/.mov (those are video URLs, not images).
 * 2. If no image is available → show a styled placeholder with a play icon.
 *    (We do NOT try <video preload> — it's unreliable for CDN-hosted videos.)
 * 3. Shows a shimmer loading animation while the image loads.
 */

const VIDEO_EXTENSIONS = /\.(mp4|webm|mov|avi|mkv)(\?.*)?$/i;

function isImageUrl(url: string | undefined): boolean {
  if (!url) return false;
  return !VIDEO_EXTENSIONS.test(url);
}

interface Props {
  videoUrl?: string;
  previewUrl?: string;
  alt?: string;
  style?: React.CSSProperties;
}

export default function VideoThumbnail({ previewUrl, alt = '', style }: Props) {
  const imageUrl = isImageUrl(previewUrl) ? previewUrl : undefined;
  const [imgLoaded, setImgLoaded] = useState(false);
  const [imgError, setImgError] = useState(false);
  const prevUrlRef = useRef(imageUrl);

  // Reset loading state when imageUrl changes (e.g. thumbMap populates async)
  useEffect(() => {
    if (prevUrlRef.current !== imageUrl) {
      prevUrlRef.current = imageUrl;
      setImgLoaded(false);
      setImgError(false);
    }
  }, [imageUrl]);

  const showImage = imageUrl && !imgError;
  const showPlaceholder = !showImage || !imgLoaded;

  const baseStyle: React.CSSProperties = {
    position: 'absolute',
    inset: 0,
    width: '100%',
    height: '100%',
    objectFit: 'cover' as const,
    ...style,
  };

  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      {/* Shimmer / placeholder — shown until image loads or as permanent fallback */}
      {showPlaceholder && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'linear-gradient(135deg, #e8e8f0 0%, #d8d8e4 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden',
          }}
        >
          {/* Shimmer animation while image is loading */}
          {showImage && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                background:
                  'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.3) 50%, transparent 100%)',
                animation: 'vthumb-shimmer 1.5s ease-in-out infinite',
              }}
            />
          )}
          {/* Play icon fallback when no image available */}
          {!showImage && (
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" style={{ opacity: 0.25 }}>
              <path d="M8 5.14v13.72a1 1 0 001.5.86l11.24-6.86a1 1 0 000-1.72L9.5 4.28A1 1 0 008 5.14z" fill="currentColor"/>
            </svg>
          )}
        </div>
      )}

      {/* Image thumbnail */}
      {showImage && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={imageUrl}
          alt={alt}
          loading="lazy"
          onLoad={() => setImgLoaded(true)}
          onError={() => setImgError(true)}
          style={{ ...baseStyle, opacity: imgLoaded ? 1 : 0, transition: 'opacity 0.2s ease' }}
        />
      )}

      <style>{`
        @keyframes vthumb-shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
}
