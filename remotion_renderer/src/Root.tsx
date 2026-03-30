import React from 'react';
import { Composition } from 'remotion';
import { CaptionedVideo, CaptionedVideoSchema } from './CaptionedVideo';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* 
        Single composition that handles all subtitle styles.
        fps, width, height, and durationInFrames are overridden
        at render time by server.js using selectComposition().
      */}
      <Composition
        id="CaptionedVideo"
        component={CaptionedVideo}
        schema={CaptionedVideoSchema}
        defaultProps={{
          videoSrc: '',
          transcription: { words: [], text: '' },
          subtitleStyle: 'hormozi',
          subtitlePlacement: 'middle',
        }}
        fps={30}
        width={1080}
        height={1920}
        durationInFrames={450}
      />
    </>
  );
};
