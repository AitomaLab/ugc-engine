'use client';

import { useState, useRef, useEffect } from 'react';

/**
 * VideoThumbnail — lightweight video preview using server-generated JPEG thumbnails.
 *
 * Strategy:
 * 1. If `previewUrl` (image) is provided → render <img> (instant).
 *    - Skips URLs ending in .mp4/.webm/.mov (those are video URLs, not images).
 * 2. If `videoUrl` is provided → render <video preload="metadata"> so the
 *    browser paints the first frame once metadata loads (fallback while a
 *    server poster is being generated).
 * 3. Otherwise → show a styled placeholder with a play icon.
 * 4. Shows a shimmer loading animation while the image/video loads.
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

export default function VideoThumbnail({ previewUrl, videoUrl, alt = '', style }: Props) {
  const imageUrl = isImageUrl(previewUrl) ? previewUrl : undefined;
  const [imgLoaded, setImgLoaded] = useState(false);
  const [imgError, setImgError] = useState(false);
  const prevUrlRef = useRef(imageUrl);
  const prevVideoRef = useRef(videoUrl);

  // Reset loading state when sources change (e.g. thumbMap populates async)
  useEffect(() => {
    if (prevUrlRef.current !== imageUrl || prevVideoRef.current !== videoUrl) {
      prevUrlRef.current = imageUrl;
      prevVideoRef.current = videoUrl;
      setImgLoaded(false);
      setImgError(false);
    }
  }, [imageUrl, videoUrl]);

  const showVideo = !imageUrl && !!videoUrl && !imgError;
  const showImage = !!imageUrl && !imgError;
  const showPlaceholder = (!showImage && !showVideo) || !imgLoaded;

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
      {/* Shimmer / placeholder — shown until media loads or as permanent fallback */}
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
          {(showImage || showVideo) && (
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
          {!showImage && !showVideo && (
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" style={{ opacity: 0.25 }}>
              <path d="M8 5.14v13.72a1 1 0 001.5.86l11.24-6.86a1 1 0 000-1.72L9.5 4.28A1 1 0 008 5.14z" fill="currentColor"/>
            </svg>
          )}
        </div>
      )}

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

      {showVideo && (
        <video
          src={videoUrl}
          muted
          playsInline
          preload="metadata"
          aria-label={alt}
          onLoadedData={() => setImgLoaded(true)}
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
