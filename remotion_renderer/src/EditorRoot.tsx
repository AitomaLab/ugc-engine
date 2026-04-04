import React from 'react';
import {Composition} from 'remotion';
import {EditorComposition} from './EditorComposition';

/**
 * Remotion Root for editor server-side rendering.
 * The composition metadata (fps, width, height, duration)
 * is overridden at render time by server.js via selectComposition().
 */
export const EditorRoot: React.FC = () => {
  return (
    <Composition
      id="EditorComposition"
      component={EditorComposition}
      defaultProps={{
        tracks: [],
        items: {},
        assets: {},
        compositionWidth: 1080,
        compositionHeight: 1920,
        fps: 24,
      }}
      fps={24}
      width={1080}
      height={1920}
      durationInFrames={720}
    />
  );
};
