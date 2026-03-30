# UGC Engine — Remotion Subtitle Integration Blueprint

**Status:** Definitive Source of Truth  
**Date:** 2026-03-30  
**Prepared by:** Manus AI  

---

## 1. Introduction and Mandate

### 1.1 Purpose

This document is the complete, self-contained technical blueprint for integrating **Remotion** as the primary subtitle rendering engine for the UGC Engine SaaS platform. It supersedes all prior discussions and documents. Antigravity must treat this document as the only source of truth.

The objective is threefold:

1. Replace the current brittle FFmpeg/ASS subtitle pipeline with a robust, frame-accurate Remotion-based rendering service.
2. Give users visual control over subtitle style (Hormozi, MrBeast, Plain) and placement (top, middle, bottom) on the `/create` page, with a live preview.
3. Simplify the user experience by hiding the AI model selector and defaulting all video generation to the Veo 3.1 model family.

### 1.2 Non-Breaking Mandate

This implementation must not break any existing video generation workflows. The strategy to guarantee this is:

- The existing FFmpeg subtitle pipeline in `subtitle_engine.py` and `assemble_video.py` is **preserved in full** and serves as the fallback.
- A single environment variable, `USE_REMOTION_SUBTITLES`, acts as a feature flag. When set to `false`, the system behaves exactly as it does today.
- The Remotion service is an isolated microservice. A failure in it cannot crash the Python backend.
- All new API fields (`subtitles_enabled`, `subtitle_style`, `subtitle_placement`) are optional with defaults that replicate current behaviour.

---

## 2. Root Cause Analysis of Current Subtitle Failures

A thorough analysis of the `main` branch (as of 2026-03-30) has identified three distinct bugs causing subtitle synchronisation and reliability failures on Veo 3.1 native audio models.

### BUG-01 — Fragile Cinematic Assembly Path (`assemble_video.py`)

**Location:** `assemble_video.py`, inside `def assemble_video(...)`, the `if has_cinematic:` branch (approximately lines 310–430).

**What the code does:** When a video contains a mix of influencer (UGC) scenes and cinematic product shots, the code:
1. Creates a temporary file (`ugc_combined.mp4`) by concatenating **only** the UGC clips.
2. Runs Whisper on this partial `ugc_combined.mp4` to get word timestamps.
3. Burns subtitles onto this partial video.
4. Re-concatenates the subtitled UGC with the cinematic clips to produce the final video.

**Why this is wrong:** The Whisper timestamps are correct relative to `ugc_combined.mp4`. But when the UGC is re-concatenated with cinematic clips in Step 4, the final video has a different total duration and potentially different timing. Any cinematic clip that appears *before* a UGC scene in the final video will shift all subtitle timestamps, making them wrong.

**The fix:** Concatenate everything first into one final video, then run Whisper on that complete final video, then burn subtitles. This is what the Remotion path does by design.

### BUG-02 — Missing Per-Scene Transcription for Standard Veo Path (`core_engine.py`)

**Location:** `core_engine.py`, inside `run_generation_pipeline`, the scene generation loop.

**What the code does:** The `if scene_type == "physical_product_scene":` branch correctly calls `extract_transcription_with_whisper` on each individual scene clip after it is downloaded, storing the result in `scene["transcription"]`. The standard `else` branch (used for all digital product videos with Veo 3.1) does **not** do this — it skips per-scene transcription entirely.

**Why this matters for the Remotion path:** The Remotion architecture described in this blueprint runs Whisper once on the final assembled video. This is the correct approach and makes BUG-02 irrelevant for the Remotion path. However, it must be fixed in the FFmpeg fallback path to ensure the fallback is reliable.

### BUG-03 — Ignored Per-Scene Transcription Data (`assemble_video.py`)

**Location:** `assemble_video.py`, the `else` (standard, non-cinematic) path.

**What the code does:** Even when `core_engine.py` correctly generates `scene["transcription"]` data (in the `physical_product_scene` path), `assemble_video.py` never reads it. It always calls `extract_transcription_with_whisper` on the final assembled video from scratch, discarding all pre-computed data.

**Why this matters:** This is the architectural root cause. The Remotion path fixes this by design: Whisper is run once on the final video, and the result is passed directly to Remotion for rendering.

---

## 3. Proposed Architecture

The new subtitle pipeline works as follows:

```
core_engine.py
    │
    ├─ [1] Generate all video scenes (unchanged)
    │
    ├─ [2] assemble_video() → final_video.mp4 (NO subtitles burned)
    │       The assembly step is simplified: it no longer runs Whisper
    │       or burns subtitles. It only concatenates, adds music, and
    │       applies transitions.
    │
    ├─ [3] Run Whisper on final_video.mp4 → transcription JSON
    │       (extract_transcription_with_whisper in subtitle_engine.py)
    │
    ├─ [4a] USE_REMOTION_SUBTITLES=true (PRIMARY PATH)
    │       POST http://localhost:8090/render
    │       { videoPath, transcription, subtitleStyle, subtitlePlacement }
    │       → remotion_renderer service returns captioned_video.mp4
    │
    └─ [4b] USE_REMOTION_SUBTITLES=false OR Remotion fails (FALLBACK)
            subtitle_engine.generate_subtitles_from_whisper() → .ass file
            FFmpeg burns .ass onto video → captioned_video.mp4
```

The `remotion_renderer` is a new, standalone Node.js/Express service that lives in a new directory `remotion_renderer/` at the root of the repository. It accepts a single `POST /render` request and returns the path of the rendered video.

---

## 4. Implementation Plan

### Phase 1: Database Migration

**File to create:** `ugc_db/migrations/013_add_subtitle_config.sql`

Create this file and run it in the Supabase SQL Editor.

```sql
-- 013_add_subtitle_config.sql
-- Adds user-configurable subtitle preferences to video_jobs.
-- Safe to run multiple times (IF NOT EXISTS throughout).

ALTER TABLE public.video_jobs
  ADD COLUMN IF NOT EXISTS subtitles_enabled  BOOLEAN  DEFAULT true,
  ADD COLUMN IF NOT EXISTS subtitle_style     TEXT     DEFAULT 'hormozi',
  ADD COLUMN IF NOT EXISTS subtitle_placement TEXT     DEFAULT 'middle';

-- Add a comment for documentation
COMMENT ON COLUMN public.video_jobs.subtitles_enabled  IS 'Whether to burn subtitles onto the final video. Defaults to true.';
COMMENT ON COLUMN public.video_jobs.subtitle_style     IS 'Subtitle visual style: hormozi | mrbeast | plain. Defaults to hormozi.';
COMMENT ON COLUMN public.video_jobs.subtitle_placement IS 'Vertical placement of subtitles: top | middle | bottom. Defaults to middle.';
```

---

### Phase 2: Build the Remotion Renderer Service

Create a new directory `remotion_renderer/` at the root of the repository. This is a completely self-contained Node.js project.

#### 2.1 — `remotion_renderer/package.json`

```json
{
  "name": "remotion-renderer",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "start": "node server.js",
    "build": "npx remotion bundle src/index.ts --out dist/bundle"
  },
  "dependencies": {
    "@remotion/bundler": "4.0.290",
    "@remotion/captions": "4.0.290",
    "@remotion/renderer": "4.0.290",
    "express": "^4.18.2",
    "react": "18.2.0",
    "react-dom": "18.2.0",
    "remotion": "4.0.290"
  },
  "devDependencies": {
    "@types/express": "^4.17.21",
    "@types/react": "18.2.0",
    "typescript": "^5.0.0"
  }
}
```

#### 2.2 — `remotion_renderer/tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "lib": ["ES2020", "DOM"],
    "jsx": "react",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "dist"
  },
  "include": ["src/**/*"]
}
```

#### 2.3 — `remotion_renderer/src/index.ts`

This is the Remotion entry point. It registers the root component.

```typescript
import { registerRoot } from 'remotion';
import { RemotionRoot } from './Root';

registerRoot(RemotionRoot);
```

#### 2.4 — `remotion_renderer/src/Root.tsx`

This file defines all Remotion compositions. Each composition corresponds to a subtitle style.

```typescript
import React from 'react';
import { Composition } from 'remotion';
import { CaptionedVideo, CaptionedVideoSchema } from './CaptionedVideo';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* 
        We define one composition that handles all styles.
        The fps, width, height, and durationInFrames are overridden
        at render time by the server.js using selectComposition().
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
```

#### 2.5 — `remotion_renderer/src/CaptionedVideo.tsx`

This is the main Remotion component. It renders the source video with captions overlaid.

```typescript
import React, { useMemo } from 'react';
import { AbsoluteFill, OffthreadVideo, useCurrentFrame, useVideoConfig } from 'remotion';
import { createTikTokStyleCaptions } from '@remotion/captions';
import { z } from 'zod';

// --- Zod Schema (for type safety and Remotion's schema validation) ---
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

// --- Style Definitions ---
const PLACEMENT_STYLES: Record<string, React.CSSProperties> = {
  top: {
    top: '8%',
    bottom: 'auto',
    transform: 'none',
  },
  middle: {
    top: '50%',
    bottom: 'auto',
    transform: 'translateY(-50%)',
  },
  bottom: {
    top: 'auto',
    bottom: '12%',
    transform: 'none',
  },
};

const POWER_WORDS = new Set([
  'literally', 'insane', 'incredible', 'amazing', 'seriously',
  'actually', 'never', 'best', 'perfect', 'every', 'entire',
  'changed', 'life', 'free', 'now', 'download', 'need',
  'seconds', 'fast', 'easy', 'simple', 'just', 'wow',
  'unbelievable', 'instantly',
]);

// --- Hormozi Style Caption Component ---
const HormoziCaption: React.FC<{ text: string; isActive: boolean }> = ({ text, isActive }) => {
  if (!isActive) return null;
  const words = text.split(' ');
  return (
    <div style={{
      display: 'flex',
      flexWrap: 'wrap',
      justifyContent: 'center',
      gap: '4px',
      padding: '0 40px',
    }}>
      {words.map((word, i) => {
        const clean = word.toLowerCase().replace(/[^\w]/g, '');
        const isPower = POWER_WORDS.has(clean);
        return (
          <span
            key={i}
            style={{
              fontFamily: 'Impact, Arial Black, sans-serif',
              fontSize: '90px',
              fontWeight: 900,
              color: isPower ? '#FFFF00' : '#FFFFFF',
              textShadow: '-4px -4px 0 #000, 4px -4px 0 #000, -4px 4px 0 #000, 4px 4px 0 #000, 0 6px 0 #000',
              lineHeight: 1.1,
              letterSpacing: '-1px',
              textTransform: 'uppercase',
              display: 'inline-block',
              transform: isPower ? 'scale(1.1)' : 'scale(1)',
            }}
          >
            {word}
          </span>
        );
      })}
    </div>
  );
};

// --- MrBeast Style Caption Component ---
const MrBeastCaption: React.FC<{ text: string; isActive: boolean }> = ({ text, isActive }) => {
  if (!isActive) return null;
  return (
    <div style={{
      display: 'flex',
      flexWrap: 'wrap',
      justifyContent: 'center',
      gap: '6px',
      padding: '0 40px',
    }}>
      {text.split(' ').map((word, i) => (
        <span
          key={i}
          style={{
            fontFamily: 'Arial Black, Impact, sans-serif',
            fontSize: '80px',
            fontWeight: 900,
            color: '#FFFFFF',
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            padding: '4px 12px',
            borderRadius: '8px',
            lineHeight: 1.2,
            display: 'inline-block',
          }}
        >
          {word}
        </span>
      ))}
    </div>
  );
};

// --- Plain Style Caption Component ---
const PlainCaption: React.FC<{ text: string; isActive: boolean }> = ({ text, isActive }) => {
  if (!isActive) return null;
  return (
    <div style={{
      display: 'flex',
      flexWrap: 'wrap',
      justifyContent: 'center',
      gap: '4px',
      padding: '0 60px',
    }}>
      {text.split(' ').map((word, i) => (
        <span
          key={i}
          style={{
            fontFamily: 'Arial, sans-serif',
            fontSize: '60px',
            fontWeight: 700,
            color: '#FFFFFF',
            textShadow: '2px 2px 6px rgba(0,0,0,0.9)',
            lineHeight: 1.3,
            display: 'inline-block',
          }}
        >
          {word}
        </span>
      ))}
    </div>
  );
};

// --- Main CaptionedVideo Component ---
export const CaptionedVideo: React.FC<Props> = ({
  videoSrc,
  transcription,
  subtitleStyle,
  subtitlePlacement,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTimeSeconds = frame / fps;

  // Group words into caption chunks using Remotion's built-in utility
  const { pages } = useMemo(() => {
    return createTikTokStyleCaptions({
      captions: transcription.words.map(w => ({
        text: w.word,
        startMs: w.start * 1000,
        endMs: w.end * 1000,
        confidence: 1,
        timestampMs: w.start * 1000,
      })),
      combineTokensWithinMilliseconds: 800, // Group words within 800ms into one caption
    });
  }, [transcription.words]);

  // Find the active page for the current frame
  const activePage = useMemo(() => {
    return pages.find(page => {
      const startSec = page.startMs / 1000;
      const endSec = page.endMs / 1000;
      return currentTimeSeconds >= startSec && currentTimeSeconds < endSec;
    });
  }, [pages, currentTimeSeconds]);

  const activeText = activePage ? activePage.tokens.map(t => t.text).join(' ').trim() : '';
  const isActive = Boolean(activeText);

  const placementStyle = PLACEMENT_STYLES[subtitlePlacement];

  return (
    <AbsoluteFill>
      {/* The source video */}
      <OffthreadVideo src={videoSrc} />

      {/* Caption overlay */}
      <AbsoluteFill style={{ pointerEvents: 'none' }}>
        <div style={{
          position: 'absolute',
          left: 0,
          right: 0,
          textAlign: 'center',
          ...placementStyle,
        }}>
          {subtitleStyle === 'hormozi' && (
            <HormoziCaption text={activeText} isActive={isActive} />
          )}
          {subtitleStyle === 'mrbeast' && (
            <MrBeastCaption text={activeText} isActive={isActive} />
          )}
          {subtitleStyle === 'plain' && (
            <PlainCaption text={activeText} isActive={isActive} />
          )}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
```

#### 2.6 — `remotion_renderer/server.js`

This is the Express HTTP server that drives Remotion rendering. It pre-bundles the Remotion project on startup and exposes a `POST /render` endpoint.

```javascript
const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(express.json({ limit: '50mb' }));

const PORT = process.env.REMOTION_PORT || 8090;

// Pre-bundle the Remotion project on startup (cached for all subsequent renders)
let bundlePromise = null;

async function getBundle() {
  if (!bundlePromise) {
    console.log('[Remotion] Bundling project (first-time, may take 30s)...');
    const { bundle } = await import('@remotion/bundler');
    bundlePromise = bundle({
      entryPoint: path.join(__dirname, 'src/index.ts'),
      // No webpack override needed for this use case
    });
    bundlePromise.then(url => console.log('[Remotion] Bundle ready:', url));
  }
  return bundlePromise;
}

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'remotion-renderer' });
});

// Main render endpoint
app.post('/render', async (req, res) => {
  const { videoPath, transcription, subtitleStyle, subtitlePlacement } = req.body;

  // Validate required fields
  if (!videoPath || !transcription) {
    return res.status(400).json({ error: 'videoPath and transcription are required' });
  }

  if (!fs.existsSync(videoPath)) {
    return res.status(400).json({ error: `Video file not found: ${videoPath}` });
  }

  try {
    const { renderMedia, selectComposition } = await import('@remotion/renderer');
    const serveUrl = await getBundle();

    // Determine video duration and fps from the source video
    // We use Remotion's getVideoMetadata for this
    const { getVideoMetadata } = await import('@remotion/renderer');
    const metadata = await getVideoMetadata(videoPath);
    const fps = Math.round(metadata.fps) || 30;
    const durationInFrames = Math.ceil(metadata.durationInSeconds * fps);

    const inputProps = {
      videoSrc: videoPath,
      transcription,
      subtitleStyle: subtitleStyle || 'hormozi',
      subtitlePlacement: subtitlePlacement || 'middle',
    };

    const composition = await selectComposition({
      serveUrl,
      id: 'CaptionedVideo',
      inputProps,
    });

    // Override composition duration and fps to match the source video exactly
    composition.durationInFrames = durationInFrames;
    composition.fps = fps;
    composition.width = metadata.width || 1080;
    composition.height = metadata.height || 1920;

    // Output path: same directory as input, with _captioned suffix
    const ext = path.extname(videoPath);
    const outputLocation = videoPath.replace(ext, `_captioned${ext}`);

    console.log(`[Remotion] Rendering: ${path.basename(videoPath)} → ${path.basename(outputLocation)}`);
    console.log(`[Remotion] Style: ${inputProps.subtitleStyle}, Placement: ${inputProps.subtitlePlacement}`);
    console.log(`[Remotion] Duration: ${metadata.durationInSeconds.toFixed(2)}s @ ${fps}fps = ${durationInFrames} frames`);

    await renderMedia({
      composition,
      serveUrl,
      codec: 'h264',
      outputLocation,
      inputProps,
      // Use the same concurrency as available CPU cores
      concurrency: Math.max(1, Math.floor(require('os').cpus().length / 2)),
    });

    console.log(`[Remotion] ✅ Render complete: ${outputLocation}`);
    res.json({ outputLocation, success: true });

  } catch (err) {
    console.error('[Remotion] ❌ Render failed:', err.message);
    res.status(500).json({ error: err.message, success: false });
  }
});

// Start server and pre-warm the bundle
app.listen(PORT, () => {
  console.log(`[Remotion] Renderer listening on port ${PORT}`);
  // Pre-warm the bundle in the background so the first render is fast
  getBundle().catch(err => console.error('[Remotion] Pre-warm failed:', err.message));
});
```

#### 2.7 — `remotion_renderer/.gitignore`

```
node_modules/
dist/
output/
*.mp4
```

---

### Phase 3: Backend Integration

This phase modifies three Python files. No existing logic is deleted — the subtitle burning code in `assemble_video.py` is preserved as the fallback.

#### 3.1 — Modify `ugc_backend/main.py`

**Change 1:** Add the three new fields to `JobCreate` and `BulkJobCreate`.

Find the `JobCreate` class and add these three lines inside it:

```python
class JobCreate(BaseModel):
    influencer_id: str
    script_id: Optional[str] = None
    app_clip_id: Optional[str] = None
    product_id: Optional[str] = None
    product_type: str = "digital"
    hook: Optional[str] = None
    model_api: str = "seedance-1.5-pro"
    assistant_type: str = "Travel"
    length: int = 15
    user_id: Optional[str] = None
    campaign_name: Optional[str] = None
    cinematic_shot_ids: Optional[List[str]] = None
    auto_transition_type: Optional[str] = None
    # NEW: Subtitle configuration fields
    subtitles_enabled: Optional[bool] = True
    subtitle_style: Optional[str] = "hormozi"
    subtitle_placement: Optional[str] = "middle"
```

Apply the same three new fields to `BulkJobCreate`:

```python
class BulkJobCreate(BaseModel):
    influencer_id: str
    count: int = 1
    duration: int = 15
    model_api: str = "seedance-1.5-pro"
    assistant_type: str = "Travel"
    product_type: str = "digital"
    product_id: Optional[str] = None
    hook: Optional[str] = None
    user_id: Optional[str] = None
    campaign_name: Optional[str] = None
    cinematic_shot_ids: Optional[List[str]] = None
    auto_transition_type: Optional[str] = None
    # NEW: Subtitle configuration fields
    subtitles_enabled: Optional[bool] = True
    subtitle_style: Optional[str] = "hormozi"
    subtitle_placement: Optional[str] = "middle"
```

**Change 2:** Add the three new column names to the `db_columns` fallback set.

Find the fallback `db_columns` set (around line 710) and add the three new columns:

```python
if not db_columns:
    db_columns = {
        "id", "user_id", "influencer_id", "app_clip_id", "script_id",
        "status", "progress", "final_video_url", "created_at", "updated_at",
        "product_type", "product_id", "cost_image",
        "hook", "model_api", "assistant_type", "length", "campaign_name",
        "cost_video", "cost_voice", "cost_music", "cost_processing", "total_cost",
        "cinematic_shot_ids", "error_message",
        # NEW: Subtitle configuration columns
        "subtitles_enabled", "subtitle_style", "subtitle_placement",
    }
```

#### 3.2 — Modify `ugc_worker/tasks.py`

**Change:** Read the three new subtitle fields from the job and pass them into the `fields` dictionary.

Find the `fields = { ... }` dictionary construction (around line 248) and add the three new keys:

```python
fields = {
    "Hook": job.get("hook") or job_metadata.get("hook") or script_text,
    "Theme": job.get("assistant_type") or script_cat,
    "Length": f"{job.get('length', 15)}s",
    "model_api": job.get("model_api", "seedance-1.5-pro"),
    "cinematic_shot_ids": job.get("cinematic_shot_ids") or job_metadata.get("cinematic_shot_ids") or [],
    "auto_transition_type": auto_trans_type,
    # NEW: Subtitle configuration — read from job, fall back to safe defaults
    "subtitles_enabled": job.get("subtitles_enabled", True),
    "subtitle_style": job.get("subtitle_style", "hormozi"),
    "subtitle_placement": job.get("subtitle_placement", "middle"),
}
```

#### 3.3 — Modify `core_engine.py`

This is the most important backend change. The subtitle burning logic is moved from `assemble_video.py` into `core_engine.py`, after the assembly step. The `assemble_video` function is simplified to no longer burn subtitles (see Phase 3.4).

**Add the following imports at the top of `core_engine.py`** (if not already present):

```python
import requests
import os
import subtitle_engine
```

**Replace the current `# 5. Assemble final video` block** (from approximately line 578 to the end of `run_generation_pipeline`) with the following complete replacement. This is the full new version of that block:

```python
    # 5. Assemble final video (WITHOUT subtitles — subtitles are applied after)
    if status_callback:
        status_callback("Assembling")

    version = datetime.now().strftime("%H%M%S")
    output_path = config.OUTPUT_DIR / f"{project_name}_v{version}.mp4"

    # Build brand names list for subtitle correction
    brand_names = []
    if product:
        if product.get("name"):
            brand_names.append(product["name"])
        visuals = product.get("visual_description") or {}
        if visuals.get("brand_name") and visuals["brand_name"] not in brand_names:
            brand_names.append(visuals["brand_name"])
    if brand_names:
        print(f"      [BRAND] Brand names for subtitle correction: {brand_names}")

    final_path = assemble_video.assemble_video(
        video_paths=video_paths,
        output_path=output_path,
        music_path=music_path,
        max_duration=config.get_max_duration(fields.get("Length", "15s")),
        scene_types=[s.get("type", "clip") for s in video_paths],
        brand_names=brand_names or None,
    )

    # 6. Apply subtitles (Remotion primary, FFmpeg fallback)
    subtitles_enabled = fields.get("subtitles_enabled", True)
    subtitle_style = fields.get("subtitle_style", "hormozi")
    subtitle_placement = fields.get("subtitle_placement", "middle")
    use_remotion = os.getenv("USE_REMOTION_SUBTITLES", "true").lower() == "true"

    captioned_path = None

    if subtitles_enabled:
        if status_callback:
            status_callback("Subtitling")

        # Always run Whisper on the FINAL assembled video for accurate timestamps
        print("      [SUBTITLES] Transcribing final assembled video with Whisper...")
        transcription = subtitle_engine.extract_transcription_with_whisper(
            str(final_path), brand_names=brand_names or None
        )

        if transcription and transcription.get("words"):
            # --- PRIMARY PATH: Remotion ---
            if use_remotion:
                try:
                    print(f"      [SUBTITLES] Rendering with Remotion (style={subtitle_style}, placement={subtitle_placement})...")
                    remotion_url = os.getenv("REMOTION_RENDERER_URL", "http://localhost:8090")
                    payload = {
                        "videoPath": str(final_path),
                        "transcription": transcription,
                        "subtitleStyle": subtitle_style,
                        "subtitlePlacement": subtitle_placement,
                    }
                    response = requests.post(
                        f"{remotion_url}/render",
                        json=payload,
                        timeout=300,  # 5 minutes max
                    )
                    response.raise_for_status()
                    result = response.json()
                    if result.get("success") and result.get("outputLocation"):
                        captioned_path = result["outputLocation"]
                        print(f"      [SUBTITLES] ✅ Remotion render complete: {captioned_path}")
                    else:
                        raise ValueError(f"Remotion returned unexpected response: {result}")
                except Exception as remotion_err:
                    print(f"      [SUBTITLES] ⚠️ Remotion failed: {remotion_err}. Falling back to FFmpeg.")
                    captioned_path = None  # Trigger fallback

            # --- FALLBACK PATH: FFmpeg/ASS ---
            if not captioned_path:
                try:
                    print("      [SUBTITLES] Rendering with FFmpeg fallback...")
                    import tempfile
                    from pathlib import Path as _Path
                    subtitle_path = _Path(str(final_path)).parent / "subtitles_synced.ass"
                    subtitle_engine.generate_subtitles_from_whisper(
                        transcription, subtitle_path, brand_names=brand_names or None
                    )
                    if subtitle_path.exists() and subtitle_path.stat().st_size > 250:
                        subtitled_path = _Path(str(final_path)).parent / f"{_Path(str(final_path)).stem}_captioned.mp4"
                        sub_path_safe = str(subtitle_path.resolve()).replace("\\", "/").replace(":", "\\:")
                        import subprocess
                        cmd = [
                            "ffmpeg", "-y",
                            "-i", str(final_path),
                            "-vf", f"ass=\\'{sub_path_safe}\\'",
                            "-c:v", "libx264",
                            "-c:a", "copy",
                            "-preset", "veryfast",
                            str(subtitled_path),
                        ]
                        subprocess.run(cmd, capture_output=True, check=True)
                        captioned_path = str(subtitled_path)
                        print(f"      [SUBTITLES] ✅ FFmpeg fallback complete: {captioned_path}")
                except Exception as ffmpeg_err:
                    print(f"      [SUBTITLES] ❌ FFmpeg fallback also failed: {ffmpeg_err}. Using video without subtitles.")
                    captioned_path = None
        else:
            print("      [SUBTITLES] ⚠️ No transcription words found. Skipping subtitles.")

    # Use captioned video if available, otherwise use the assembled video without subtitles
    final_output_path = captioned_path if captioned_path else str(final_path)

    # 7. Cleanup temp files
    assemble_video.cleanup_temp(project_name)

    return str(final_output_path)
```

#### 3.4 — Modify `assemble_video.py`

The `assemble_video` function must be simplified to **remove all subtitle burning logic**. Subtitles are now applied in `core_engine.py` after assembly. The rest of the function (normalization, transitions, concatenation, music mixing) is completely unchanged.

**In the `if has_cinematic:` branch**, remove the subtitle burning block (Steps 2b and the subtitle-related parts of 2c). The cinematic path should only concatenate and normalize — it should no longer call `extract_transcription_with_whisper` or `generate_subtitles_from_whisper`.

Replace the entire `if has_cinematic:` block with this simplified version:

```python
    if has_cinematic:
        # Cinematic path: separate UGC and cinematic scenes, then concatenate in order.
        # NOTE: Subtitle burning has been moved to core_engine.py and is applied
        # AFTER assembly on the complete final video. Do NOT add subtitle logic here.
        ugc_types = {"veo", "physical_product_scene"}
        ugc_scenes = [s for s in scene_metadata if s["type"] in ugc_types]
        cinematic_scenes = [s for s in scene_metadata if s["type"] not in ugc_types]

        print(f"   [CINEMATIC] {len(ugc_scenes)} UGC scenes + {len(cinematic_scenes)} cinematic scenes")

        # Concatenate all scenes in original order (UGC + cinematic interleaved)
        final_concat_list = work_dir / "final_concat.txt"
        with open(final_concat_list, "w") as f:
            for s in scene_metadata:
                norm_path = work_dir / f"norm_{s['index']}.mp4"
                normalize_video(s["path"], norm_path)
                safe_path = str(Path(norm_path).resolve()).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        combined = work_dir / "combined.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(final_concat_list),
            "-c", "copy",
            str(combined),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        current_input = str(combined)
        total_dur = get_video_duration(combined)
        print(f"      Combined: {total_dur:.1f}s (UGC + cinematic, no subtitles)")
    else:
        # Standard path: no cinematic scenes — concatenate everything.
        # NOTE: Subtitle burning has been moved to core_engine.py.
        print("   [LINK] Concatenating scenes...")
        concat_list = work_dir / "concat.txt"
        with open(concat_list, "w") as f:
            for path in normalized_paths:
                safe_path = str(Path(path).resolve()).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")
        combined = work_dir / "combined.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(combined),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        total_dur = get_video_duration(combined)
        print(f"      Combined: {total_dur:.1f}s")
        current_input = str(combined)
```

**Important:** Keep all other code in `assemble_video.py` completely unchanged. The music mixing block, the final output copy, the `cleanup_temp` function, and all helper functions (`normalize_video`, `get_video_duration`, `ensure_audio_stream`, etc.) must not be touched.

---

### Phase 4: Frontend UI Changes

#### 4.1 — Add new state variables to `/create` page

**File:** `frontend/src/app/create/page.tsx`

Add these three new state variables near the other state declarations at the top of the component:

```typescript
const [subtitlesEnabled, setSubtitlesEnabled] = useState<boolean>(true);
const [subtitleStyle, setSubtitleStyle] = useState<string>('hormozi');
const [subtitlePlacement, setSubtitlePlacement] = useState<string>('middle');
```

#### 4.2 — Hide the AI Model selector

**File:** `frontend/src/app/create/page.tsx`

Find the `{/* STEP 3 — AI Model */}` JSX block and comment it out entirely. Do **not** delete it. Also, change the default value of `modelApi` state to `'veo-3.1-fast'`:

```typescript
// Change this:
const [modelApi, setModelApi] = useState('seedance-1.5-pro');
// To this:
const [modelApi, setModelApi] = useState('veo-3.1-fast');
```

Then wrap the entire AI Model config section in a comment:

```jsx
{/* AI MODEL SELECTOR — HIDDEN: Defaulting to Veo 3.1. Uncomment to re-enable.
<div className="config-section">
    <div className="config-step">
        <div className="step-num">3</div>
        <div className="step-text">AI Model</div>
    </div>
    <div className="pill-group">
        {AI_MODELS.map(model => (
            <button key={model.value} className={`btn-secondary ${modelApi === model.value ? 'active' : ''}`} onClick={() => setModelApi(model.value)} style={{padding:'8px 16px'}}>
                {model.label}
            </button>
        ))}
    </div>
</div>
*/}
```

#### 4.3 — Add the Subtitle Configuration UI

**File:** `frontend/src/app/create/page.tsx`

Add the following JSX block immediately after the Duration config section. This adds the subtitle toggle, style selector, placement selector, and live preview:

```jsx
{/* SUBTITLE CONFIGURATION */}
<div className="config-section">
    <div className="config-label" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span>Subtitles</span>
        {/* Toggle — uses the existing Switch component pattern from the codebase */}
        <button
            onClick={() => setSubtitlesEnabled(!subtitlesEnabled)}
            style={{
                width: '44px',
                height: '24px',
                borderRadius: '12px',
                border: 'none',
                cursor: 'pointer',
                backgroundColor: subtitlesEnabled ? '#337AFF' : '#D1D5DB',
                position: 'relative',
                transition: 'background-color 0.2s',
            }}
        >
            <span style={{
                position: 'absolute',
                top: '2px',
                left: subtitlesEnabled ? '22px' : '2px',
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                backgroundColor: '#FFFFFF',
                transition: 'left 0.2s',
                boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
            }} />
        </button>
    </div>

    {subtitlesEnabled && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '12px' }}>

            {/* Style Selector */}
            <div>
                <div className="config-label-sm" style={{ marginBottom: '8px', fontSize: '12px', color: '#6B7280' }}>Style</div>
                <div className="pill-group">
                    {[
                        { value: 'hormozi', label: 'Hormozi' },
                        { value: 'mrbeast', label: 'MrBeast' },
                        { value: 'plain', label: 'Plain' },
                    ].map(s => (
                        <button
                            key={s.value}
                            className={`btn-secondary ${subtitleStyle === s.value ? 'active' : ''}`}
                            onClick={() => setSubtitleStyle(s.value)}
                        >
                            {s.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Placement Selector */}
            <div>
                <div className="config-label-sm" style={{ marginBottom: '8px', fontSize: '12px', color: '#6B7280' }}>Placement</div>
                <div className="pill-group">
                    {[
                        { value: 'top', label: 'Top' },
                        { value: 'middle', label: 'Middle' },
                        { value: 'bottom', label: 'Bottom' },
                    ].map(p => (
                        <button
                            key={p.value}
                            className={`btn-secondary ${subtitlePlacement === p.value ? 'active' : ''}`}
                            onClick={() => setSubtitlePlacement(p.value)}
                        >
                            {p.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Live Preview */}
            <div>
                <div className="config-label-sm" style={{ marginBottom: '8px', fontSize: '12px', color: '#6B7280' }}>Preview</div>
                <div style={{
                    position: 'relative',
                    width: '100%',
                    paddingTop: '177.78%', /* 9:16 aspect ratio */
                    backgroundColor: '#1a1a2e',
                    borderRadius: '12px',
                    overflow: 'hidden',
                    backgroundImage: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
                }}>
                    {/* Preview caption positioned based on placement */}
                    <div style={{
                        position: 'absolute',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        width: '90%',
                        textAlign: 'center',
                        ...(subtitlePlacement === 'top' ? { top: '8%' } : {}),
                        ...(subtitlePlacement === 'middle' ? { top: '50%', transform: 'translate(-50%, -50%)' } : {}),
                        ...(subtitlePlacement === 'bottom' ? { bottom: '12%' } : {}),
                    }}>
                        {subtitleStyle === 'hormozi' && (
                            <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '3px' }}>
                                {['THIS', 'APP', 'IS', 'INSANE'].map((word, i) => (
                                    <span key={i} style={{
                                        fontFamily: 'Impact, Arial Black, sans-serif',
                                        fontSize: '22px',
                                        fontWeight: 900,
                                        color: word === 'INSANE' ? '#FFFF00' : '#FFFFFF',
                                        textShadow: '-2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000',
                                        textTransform: 'uppercase',
                                        display: 'inline-block',
                                        transform: word === 'INSANE' ? 'scale(1.1)' : 'scale(1)',
                                    }}>
                                        {word}
                                    </span>
                                ))}
                            </div>
                        )}
                        {subtitleStyle === 'mrbeast' && (
                            <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '4px' }}>
                                {['THIS', 'APP', 'IS', 'INSANE'].map((word, i) => (
                                    <span key={i} style={{
                                        fontFamily: 'Arial Black, sans-serif',
                                        fontSize: '18px',
                                        fontWeight: 900,
                                        color: '#FFFFFF',
                                        backgroundColor: 'rgba(0,0,0,0.75)',
                                        padding: '2px 8px',
                                        borderRadius: '6px',
                                        display: 'inline-block',
                                    }}>
                                        {word}
                                    </span>
                                ))}
                            </div>
                        )}
                        {subtitleStyle === 'plain' && (
                            <span style={{
                                fontFamily: 'Arial, sans-serif',
                                fontSize: '16px',
                                fontWeight: 700,
                                color: '#FFFFFF',
                                textShadow: '1px 1px 4px rgba(0,0,0,0.9)',
                            }}>
                                This app is insane
                            </span>
                        )}
                    </div>
                </div>
            </div>

        </div>
    )}
</div>
```

#### 4.4 — Update `handleCreateVideo` to send the new fields

**File:** `frontend/src/app/create/page.tsx`

In the `handleCreateVideo` function, add the three new fields to **both** the single job and bulk job API call bodies.

For the **single job** (`/jobs` endpoint):

```typescript
await apiFetch('/jobs', {
    method: 'POST',
    body: JSON.stringify({
        influencer_id: selectedInfluencer,
        script_id: scriptSource === 'specific' ? selectedScript : undefined,
        app_clip_id: (productType === 'digital' && appClipId !== 'auto') ? appClipId : undefined,
        product_id: productId || undefined,
        product_type: productType,
        hook: effectiveHook,
        model_api: modelApi,
        assistant_type: selectedInf?.style || 'Travel',
        length: duration,
        cinematic_shot_ids: selectedCinematicShots.length > 0 ? selectedCinematicShots : undefined,
        auto_transition_type: enableAutoTransitions ? autoTransitionType : undefined,
        // NEW: Subtitle configuration
        subtitles_enabled: subtitlesEnabled,
        subtitle_style: subtitleStyle,
        subtitle_placement: subtitlePlacement,
    }),
});
```

For the **bulk job** (`/jobs/bulk` endpoint):

```typescript
await apiFetch('/jobs/bulk', {
    method: 'POST',
    body: JSON.stringify({
        influencer_id: selectedInfluencer,
        count: quantity,
        duration,
        model_api: modelApi,
        campaign_name: campaignName || undefined,
        assistant_type: selectedInf?.style || 'Travel',
        product_type: productType,
        product_id: productId || undefined,
        hook: bulkHook,
        cinematic_shot_ids: selectedCinematicShots.length > 0 ? selectedCinematicShots : undefined,
        auto_transition_type: enableAutoTransitions ? autoTransitionType : undefined,
        // NEW: Subtitle configuration
        subtitles_enabled: subtitlesEnabled,
        subtitle_style: subtitleStyle,
        subtitle_placement: subtitlePlacement,
    }),
});
```

---

### Phase 5: Deployment Configuration

#### 5.1 — Environment Variables

Add the following environment variables to the Railway/Render deployment for the **main API and worker services**:

| Variable | Value | Description |
| :--- | :--- | :--- |
| `USE_REMOTION_SUBTITLES` | `true` | Set to `false` to disable Remotion and use FFmpeg fallback |
| `REMOTION_RENDERER_URL` | `http://remotion-renderer:8090` | Internal URL of the Remotion service (use `localhost` for local dev) |

#### 5.2 — Update `railway.toml`

Add the new Remotion renderer service to the existing `railway.toml`:

```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "PYTHONPATH=. uvicorn app:app --host 0.0.0.0 --port $PORT"

[services.worker]
startCommand = "PYTHONPATH=. celery -A ugc_worker.tasks worker --loglevel=info"

# NEW: Remotion renderer microservice
[services.remotion-renderer]
src = "./remotion_renderer"
startCommand = "npm start"
```

#### 5.3 — Update `nixpacks.toml`

The Remotion renderer needs Node.js and Chromium (for headless rendering). Add a separate `nixpacks.toml` inside `remotion_renderer/`:

**File:** `remotion_renderer/nixpacks.toml`

```toml
providers = ["node"]

[variables]
NODE_VERSION = "20"

[phases.setup]
aptPkgs = ["chromium-browser", "fonts-liberation", "fonts-noto-color-emoji"]

[start]
cmd = "npm start"
```

---

## 5. Non-Breaking Guarantee

The following table documents every existing code path and confirms it is safe.

| Component | Existing Behaviour | After This Change | Safe? |
| :--- | :--- | :--- | :--- |
| `subtitle_engine.py` | Generates ASS files and burns with FFmpeg | **Unchanged.** Used as fallback in `core_engine.py`. | ✅ Yes |
| `assemble_video.py` subtitle logic | Runs Whisper + burns ASS in assembly | Removed from assembly. Subtitle burning moved to `core_engine.py`. | ✅ Yes — same result |
| `assemble_video.py` music/concat logic | Concatenates scenes, adds music | **Completely unchanged.** | ✅ Yes |
| `core_engine.py` scene generation | Generates Veo 3.1 scenes | **Completely unchanged.** | ✅ Yes |
| `core_engine.py` Veo Extend pipeline | Multi-scene chaining | **Completely unchanged.** | ✅ Yes |
| `core_engine.py` physical product path | Physical product scene generation | **Completely unchanged.** | ✅ Yes |
| `ugc_worker/tasks.py` | Calls `run_generation_pipeline` | Three new optional fields added to `fields` dict. Defaults preserve existing behaviour. | ✅ Yes |
| `ugc_backend/main.py` | Accepts job creation requests | Three new optional fields added to models. All have defaults. No existing field changed. | ✅ Yes |
| Existing jobs in DB | Have no subtitle columns | New columns have `DEFAULT` values. Existing rows unaffected. | ✅ Yes |
| `USE_REMOTION_SUBTITLES=false` | N/A (new variable) | System falls back to FFmpeg path, exactly as before. | ✅ Yes |

---

## 6. Local Development Setup

To run the full stack locally with Remotion:

**Terminal 1 — Python backend:**
```bash
cd ~/ugc-engine
source ugc_backend/venv/bin/activate
PYTHONPATH=. USE_REMOTION_SUBTITLES=true REMOTION_RENDERER_URL=http://localhost:8090 uvicorn app:app --reload --port 8000
```

**Terminal 2 — Celery worker:**
```bash
cd ~/ugc-engine
source ugc_backend/venv/bin/activate
PYTHONPATH=. USE_REMOTION_SUBTITLES=true REMOTION_RENDERER_URL=http://localhost:8090 celery -A ugc_worker.tasks worker --loglevel=info
```

**Terminal 3 — Remotion renderer:**
```bash
cd ~/ugc-engine/remotion_renderer
npm install
npm start
```

**Terminal 4 — Next.js frontend:**
```bash
cd ~/ugc-engine/frontend
pnpm dev
```

---

## 7. Testing and Acceptance Criteria

The implementation is complete when all of the following are true:

1. The SQL migration `013_add_subtitle_config.sql` has been applied to the Supabase database and the three new columns exist on `video_jobs`.
2. The `remotion_renderer/` directory exists with all files from Phase 2 and `npm install` runs without errors.
3. The Remotion renderer service starts and responds to `GET /health` with `{"status": "ok"}`.
4. A test video can be rendered by sending a `POST /render` request to the Remotion service with a valid video path and transcription JSON.
5. The Python backend correctly reads `subtitles_enabled`, `subtitle_style`, and `subtitle_placement` from the `fields` dict and passes them to the Remotion service.
6. The `/create` page shows the subtitle configuration UI (toggle, style pills, placement pills, live preview) and the model selector is hidden.
7. An end-to-end video generation job completes successfully with Remotion subtitles burned in.
8. Setting `USE_REMOTION_SUBTITLES=false` causes the system to use the FFmpeg fallback and still produce a video with subtitles.
9. No existing API endpoints return different response shapes.
10. No existing video generation workflows (physical products, digital products, Veo Extend, single video, bulk campaign) are broken.
