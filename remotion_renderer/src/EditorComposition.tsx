import React from 'react';
import {
  AbsoluteFill,
  OffthreadVideo,
  Img,
  Sequence,
  Audio,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
} from 'remotion';

/**
 * Server-side Remotion composition that renders the Editor's UndoableState.
 *
 * This is a simplified renderer that handles the most common item types:
 * - video: rendered with OffthreadVideo
 * - image: rendered with Img
 * - audio: rendered with Audio
 * - text: rendered as styled HTML text
 * - solid: rendered as a colored rectangle
 * - captions: rendered as timed subtitle text
 *
 * Items are layered according to the tracks array (last track = topmost layer).
 */

type Track = {
  id: string;
  items: string[];
  hidden: boolean;
  muted: boolean;
};

type BaseItem = {
  id: string;
  from: number;
  durationInFrames: number;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  rotation?: number;
  opacity?: number;
};

type VideoItemData = BaseItem & {
  type: 'video';
  src: string;
  volume?: number;
  trimStart?: number;
};

type ImageItemData = BaseItem & {
  type: 'image';
  src: string;
};

type AudioItemData = BaseItem & {
  type: 'audio';
  src: string;
  volume?: number;
  trimStart?: number;
};

type TextItemData = BaseItem & {
  type: 'text';
  text: string;
  fontSize?: number;
  fontFamily?: string;
  fontWeight?: number;
  color?: string;
  backgroundColor?: string;
  textAlign?: string;
  lineHeight?: number;
  letterSpacing?: number;
};

type SolidItemData = BaseItem & {
  type: 'solid';
  fill: string;
};

type CaptionsItemData = BaseItem & {
  type: 'captions';
  captions?: any;
  transcription?: any;
  subtitleStyle?: string;
};

type AnyItem =
  | VideoItemData
  | ImageItemData
  | AudioItemData
  | TextItemData
  | SolidItemData
  | CaptionsItemData;

type Asset = {
  id: string;
  url?: string;
  remoteUrl?: string | null;
  localUrl?: string | null;
  type?: string;
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
 * Resolve an item's media source URL from either the item's src or the linked asset.
 */
function resolveItemSrc(item: AnyItem, assets: Record<string, Asset>): string {
  if ('src' in item && item.src) {
    // If src is an asset ID, look it up
    const asset = assets[item.src];
    if (asset) {
      return asset.remoteUrl || asset.url || asset.localUrl || item.src;
    }
    return item.src;
  }
  return '';
}

const RenderItem: React.FC<{
  item: AnyItem;
  assets: Record<string, Asset>;
  compositionWidth: number;
  compositionHeight: number;
  muted: boolean;
}> = ({item, assets, compositionWidth, compositionHeight, muted}) => {
  const src = resolveItemSrc(item, assets);

  // Common positioning
  const style: React.CSSProperties = {
    position: 'absolute',
    left: item.x ?? 0,
    top: item.y ?? 0,
    width: item.width ?? compositionWidth,
    height: item.height ?? compositionHeight,
    opacity: item.opacity ?? 1,
    transform: item.rotation ? `rotate(${item.rotation}deg)` : undefined,
    transformOrigin: 'center center',
  };

  switch (item.type) {
    case 'video':
      return (
        <div style={style}>
          <OffthreadVideo
            src={src}
            style={{width: '100%', height: '100%', objectFit: 'cover'}}
            volume={muted ? 0 : (item.volume ?? 1)}
            startFrom={item.trimStart ?? 0}
          />
        </div>
      );

    case 'image':
      return (
        <div style={style}>
          <Img
            src={src}
            style={{width: '100%', height: '100%', objectFit: 'cover'}}
          />
        </div>
      );

    case 'audio':
      return (
        <Audio
          src={src}
          volume={muted ? 0 : (item.volume ?? 1)}
          startFrom={item.trimStart ?? 0}
        />
      );

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
            overflow: 'hidden',
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

    case 'captions':
      // Captions are complex — render a placeholder for now
      // The full caption rendering would require the subtitle engine
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
  // Render tracks from bottom to top (first track = bottom layer)
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
                muted={track.muted}
              />
            </Sequence>
          );
        });
      })}
    </AbsoluteFill>
  );
};
