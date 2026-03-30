import React, { useMemo } from 'react';
import { AbsoluteFill, OffthreadVideo, useCurrentFrame, useVideoConfig } from 'remotion';
import { z } from 'zod';

// Google Fonts CSS import — ensures Impact-like fonts are available on Linux/cloud
const GOOGLE_FONTS_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Anton&family=Archivo+Black&family=Roboto:wght@700;900&display=swap');
`;

// --- Zod Schema ---
export const CaptionedVideoSchema = z.object({
  videoSrc: z.string(),
  transcription: z.object({
    words: z.array(z.object({
      word: z.string(),
      start: z.number(),
      end: z.number(),
    })),
    text: z.string().optional(),
  }),
  subtitleStyle: z.enum(['hormozi', 'mrbeast', 'plain']),
  subtitlePlacement: z.enum(['top', 'middle', 'bottom']),
});

type Props = z.infer<typeof CaptionedVideoSchema>;
type WordChunk = { words: string[]; startSec: number; endSec: number };

// --- Placement ---
const PLACEMENT_STYLES: Record<string, React.CSSProperties> = {
  top:    { top: '8%',  bottom: 'auto', transform: 'none' },
  middle: { top: '50%', bottom: 'auto', transform: 'translateY(-50%)' },
  bottom: { top: 'auto', bottom: '12%', transform: 'none' },
};

// --- Power words for Hormozi yellow emphasis ---
const POWER_WORDS = new Set([
  'literally', 'insane', 'incredible', 'amazing', 'seriously',
  'actually', 'never', 'best', 'perfect', 'every', 'entire',
  'changed', 'life', 'free', 'now', 'download', 'need',
  'seconds', 'fast', 'easy', 'simple', 'just', 'wow',
  'unbelievable', 'instantly', 'saved', 'minutes', 'everything',
]);

// --- Chunk words into groups of N ---
function chunkWords(words: { word: string; start: number; end: number }[], maxPerChunk = 3): WordChunk[] {
  const chunks: WordChunk[] = [];
  for (let i = 0; i < words.length; i += maxPerChunk) {
    const slice = words.slice(i, i + maxPerChunk);
    chunks.push({
      words: slice.map(w => w.word),
      startSec: slice[0].start,
      endSec: slice[slice.length - 1].end,
    });
  }
  return chunks;
}

// --- Hormozi Style ---
const HormoziCaption: React.FC<{ words: string[] }> = ({ words }) => (
  <div style={{
    display: 'flex', flexWrap: 'wrap', justifyContent: 'center',
    gap: '20px', padding: '0 40px',
  }}>
    {words.map((word, i) => {
      const clean = word.toLowerCase().replace(/[^\w]/g, '');
      const isPower = POWER_WORDS.has(clean);
      return (
        <span key={i} style={{
          fontFamily: "'Anton', Impact, 'Arial Black', sans-serif",
          fontSize: isPower ? '88px' : '80px', fontWeight: 900,
          color: isPower ? '#FFFF00' : '#FFFFFF',
          textShadow: '-4px -4px 0 #000, 4px -4px 0 #000, -4px 4px 0 #000, 4px 4px 0 #000, 0 6px 0 #000',
          lineHeight: 1.1, letterSpacing: '1px',
          textTransform: 'uppercase', display: 'inline-block',
          margin: isPower ? '0 4px' : '0',
        }}>
          {word}
        </span>
      );
    })}
  </div>
);

// --- MrBeast Style ---
const MrBeastCaption: React.FC<{ words: string[] }> = ({ words }) => (
  <div style={{
    display: 'flex', flexWrap: 'wrap', justifyContent: 'center',
    gap: '14px', padding: '0 40px',
  }}>
    {words.map((word, i) => (
      <span key={i} style={{
        fontFamily: "'Archivo Black', 'Arial Black', Impact, sans-serif",
        fontSize: '80px', fontWeight: 900, color: '#FFFFFF',
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        padding: '4px 14px', borderRadius: '8px',
        lineHeight: 1.2, display: 'inline-block',
      }}>
        {word}
      </span>
    ))}
  </div>
);

// --- Plain Style ---
const PlainCaption: React.FC<{ words: string[] }> = ({ words }) => (
  <div style={{
    display: 'flex', flexWrap: 'wrap', justifyContent: 'center',
    gap: '12px', padding: '0 60px',
  }}>
    {words.map((word, i) => (
      <span key={i} style={{
        fontFamily: "'Roboto', Arial, sans-serif",
        fontSize: '60px', fontWeight: 700, color: '#FFFFFF',
        textShadow: '2px 2px 6px rgba(0,0,0,0.9)',
        lineHeight: 1.3, display: 'inline-block',
      }}>
        {word}
      </span>
    ))}
  </div>
);

// --- Main Component ---
export const CaptionedVideo: React.FC<Props> = ({
  videoSrc, transcription, subtitleStyle, subtitlePlacement,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  // Split words into 3-word chunks with exact timing from Whisper
  const chunks = useMemo(() => {
    if (!transcription.words || transcription.words.length === 0) return [];
    return chunkWords(transcription.words, 3);
  }, [transcription.words]);

  // Find which chunk should display right now
  const activeChunk = useMemo(() => {
    return chunks.find(c => currentTime >= c.startSec && currentTime < c.endSec);
  }, [chunks, currentTime]);

  const placement = PLACEMENT_STYLES[subtitlePlacement];

  return (
    <AbsoluteFill>
      {/* Load Google Fonts for cross-platform consistency */}
      <style dangerouslySetInnerHTML={{ __html: GOOGLE_FONTS_CSS }} />
      <OffthreadVideo src={videoSrc} />

      {activeChunk && (
        <AbsoluteFill style={{ pointerEvents: 'none' }}>
          <div style={{
            position: 'absolute', left: 0, right: 0,
            textAlign: 'center', ...placement,
          }}>
            {subtitleStyle === 'hormozi'  && <HormoziCaption words={activeChunk.words} />}
            {subtitleStyle === 'mrbeast'  && <MrBeastCaption words={activeChunk.words} />}
            {subtitleStyle === 'plain'    && <PlainCaption   words={activeChunk.words} />}
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
