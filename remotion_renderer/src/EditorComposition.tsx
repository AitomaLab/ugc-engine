import React from 'react';
import {
  AbsoluteFill,
  OffthreadVideo,
  Img,
  Sequence,
  Audio,
} from 'remotion';

/**
 * Server-side Remotion composition that renders the Editor's UndoableState.
 *
 * Items use `assetId` to reference assets which contain `remoteUrl` for the media.
 * Position is stored as `top`/`left` (not x/y).
 */

type Track = {
  id: string;
  items: string[];
  hidden: boolean;
  muted: boolean;
};

/**
 * Generic item type — we accept 'any' shape from the editor state
 * and resolve the needed fields dynamically.
 */
type AnyItem = {
  id: string;
  type: string;
  from: number;
  durationInFrames: number;
  top: number;
  left: number;
  width: number;
  height: number;
  opacity: number;
  rotation?: number;
  borderRadius?: number;
  assetId?: string;
  // Video-specific
  videoStartFromInSeconds?: number;
  decibelAdjustment?: number;
  playbackRate?: number;
  keepAspectRatio?: boolean;
  // Text-specific
  text?: string;
  fontSize?: number;
  fontFamily?: string;
  fontWeight?: number;
  color?: string;
  backgroundColor?: string;
  textAlign?: string;
  lineHeight?: number;
  letterSpacing?: number;
  // Solid-specific
  fill?: string;
  // Audio-specific
  volume?: number;
};

type Asset = {
  id: string;
  type: string;
  filename: string;
  remoteUrl: string | null;
  remoteFileKey: string | null;
  mimeType: string;
  size: number;
  width?: number;
  height?: number;
  durationInSeconds?: number;
};

type EditorCompositionProps = {
  tracks: Track[];
  items: Record<string, AnyItem>;
  assets: Record<string, Asset>;
  compositionWidth: number;
  compositionHeight: number;
  fps?: number;
};

/**
 * Resolve the media URL for an item by looking up its asset.
 */
function resolveAssetUrl(item: AnyItem, assets: Record<string, Asset>): string {
  if (!item.assetId) return '';
  const asset = assets[item.assetId];
  if (!asset) return '';
  return asset.remoteUrl || '';
}

const RenderItem: React.FC<{
  item: AnyItem;
  assets: Record<string, Asset>;
  compositionWidth: number;
  compositionHeight: number;
  trackMuted: boolean;
}> = ({item, assets, compositionWidth, compositionHeight, trackMuted}) => {
  const src = resolveAssetUrl(item, assets);

  const style: React.CSSProperties = {
    position: 'absolute',
    left: item.left ?? 0,
    top: item.top ?? 0,
    width: item.width ?? compositionWidth,
    height: item.height ?? compositionHeight,
    opacity: item.opacity ?? 1,
    transform: item.rotation ? `rotate(${item.rotation}deg)` : undefined,
    transformOrigin: 'center center',
    borderRadius: item.borderRadius ?? 0,
    overflow: 'hidden',
  };

  switch (item.type) {
    case 'video': {
      if (!src) {
        // No source — render black placeholder instead of crashing
        return <div style={{...style, backgroundColor: '#000'}} />;
      }
      const startFrom = item.videoStartFromInSeconds
        ? Math.round(item.videoStartFromInSeconds * 30)
        : 0;
      return (
        <div style={style}>
          <OffthreadVideo
            src={src}
            style={{width: '100%', height: '100%', objectFit: 'cover'}}
            volume={trackMuted ? 0 : 1}
            startFrom={startFrom}
            playbackRate={item.playbackRate ?? 1}
          />
        </div>
      );
    }

    case 'image': {
      if (!src) {
        return <div style={{...style, backgroundColor: '#333'}} />;
      }
      return (
        <div style={style}>
          <Img
            src={src}
            style={{width: '100%', height: '100%', objectFit: 'cover'}}
          />
        </div>
      );
    }

    case 'audio': {
      if (!src) return null;
      return (
        <Audio
          src={src}
          volume={trackMuted ? 0 : 1}
        />
      );
    }

    case 'text':
      return (
        <div
          style={{
            ...style,
            fontSize: item.fontSize ?? 48,
            fontFamily: item.fontFamily ?? 'sans-serif',
            fontWeight: item.fontWeight ?? 700,
            color: item.color ?? '#ffffff',
            backgroundColor: item.backgroundColor ?? 'transparent',
            textAlign: (item.textAlign as any) ?? 'center',
            lineHeight: item.lineHeight ?? 1.2,
            letterSpacing: item.letterSpacing ?? 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            wordBreak: 'break-word',
          }}
          dangerouslySetInnerHTML={{__html: item.text || ''}}
        />
      );

    case 'solid':
      return (
        <div
          style={{
            ...style,
            backgroundColor: item.fill ?? '#000000',
          }}
        />
      );

    case 'gif': {
      if (!src) return null;
      return (
        <div style={style}>
          <Img
            src={src}
            style={{width: '100%', height: '100%', objectFit: 'cover'}}
          />
        </div>
      );
    }

    case 'captions':
      // Captions rendering would require the full subtitle engine
      return null;

    default:
      return null;
  }
};

export const EditorComposition: React.FC<EditorCompositionProps> = ({
  tracks,
  items,
  assets,
  compositionWidth,
  compositionHeight,
}) => {
  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      {tracks.map((track) => {
        if (track.hidden) return null;

        return track.items.map((itemId) => {
          const item = items[itemId];
          if (!item) return null;

          return (
            <Sequence
              key={item.id}
              from={item.from ?? 0}
              durationInFrames={item.durationInFrames ?? 1}
              layout="none"
            >
              <RenderItem
                item={item}
                assets={assets}
                compositionWidth={compositionWidth}
                compositionHeight={compositionHeight}
                trackMuted={track.muted}
              />
            </Sequence>
          );
        });
      })}
    </AbsoluteFill>
  );
};
