#!/usr/bin/env node
/**
 * render_captions.js — Standalone CLI Remotion renderer
 *
 * Called from Python via subprocess. Renders captions onto a video file.
 *
 * Usage:
 *   node render_captions.js \
 *     --input  /path/to/video.mp4 \
 *     --props  /path/to/props.json \
 *     --output /path/to/output.mp4
 *
 * props.json format:
 * {
 *   "transcription": { "words": [{ "word": "...", "start": 0.0, "end": 0.5 }] },
 *   "subtitleStyle": "hormozi",
 *   "subtitlePlacement": "bottom"
 * }
 */

const path = require('path');
const fs = require('fs');

// Parse CLI arguments
function parseArgs() {
  const args = process.argv.slice(2);
  const parsed = {};
  for (let i = 0; i < args.length; i += 2) {
    const key = args[i].replace(/^--/, '');
    parsed[key] = args[i + 1];
  }
  return parsed;
}

async function main() {
  const { input, props: propsFile, output } = parseArgs();

  if (!input || !propsFile || !output) {
    console.error('Usage: node render_captions.js --input <video> --props <json> --output <output>');
    process.exit(1);
  }

  if (!fs.existsSync(input)) {
    console.error(`[Remotion] Input video not found: ${input}`);
    process.exit(1);
  }

  // Read props from JSON file
  const propsData = JSON.parse(fs.readFileSync(propsFile, 'utf-8'));
  const { transcription, subtitleStyle, subtitlePlacement } = propsData;

  console.log(`[Remotion] Input: ${path.basename(input)}`);
  console.log(`[Remotion] Output: ${path.basename(output)}`);
  console.log(`[Remotion] Style: ${subtitleStyle}, Placement: ${subtitlePlacement}`);
  console.log(`[Remotion] Words: ${transcription.words?.length || 0}`);

  // Chrome args for running in Docker/cloud containers
  const chromeArgs = [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
  ];

  // Import Remotion modules
  const { bundle } = await import('@remotion/bundler');
  const { renderMedia, selectComposition, getVideoMetadata } = await import('@remotion/renderer');

  // Bundle the Remotion project
  console.log('[Remotion] Bundling project...');
  const bundleDir = path.resolve(__dirname, 'src', 'index.ts');
  const serveUrl = await bundle({
    entryPoint: bundleDir,
    onProgress: (p) => {
      if (p === 100) console.log('[Remotion] Bundle ready');
    },
  });

  // Get video metadata
  const metadata = await getVideoMetadata(input);
  const fps = Math.round(metadata.fps) || 30;
  const durationInFrames = Math.ceil(metadata.durationInSeconds * fps);

  console.log(`[Remotion] Duration: ${metadata.durationInSeconds.toFixed(2)}s @ ${fps}fps = ${durationInFrames} frames`);

  // We need to serve the video over HTTP for OffthreadVideo to access it.
  // Start a tiny express-less HTTP server just for the video file.
  const http = require('http');
  const VIDEO_PORT = 9876;
  const server = http.createServer((req, res) => {
    if (!fs.existsSync(input)) {
      res.writeHead(404);
      res.end('Not found');
      return;
    }
    const stat = fs.statSync(input);
    const range = req.headers.range;
    if (range) {
      const parts = range.replace(/bytes=/, '').split('-');
      const start = parseInt(parts[0], 10);
      const end = parts[1] ? parseInt(parts[1], 10) : stat.size - 1;
      res.writeHead(206, {
        'Content-Range': `bytes ${start}-${end}/${stat.size}`,
        'Accept-Ranges': 'bytes',
        'Content-Length': end - start + 1,
        'Content-Type': 'video/mp4',
      });
      fs.createReadStream(input, { start, end }).pipe(res);
    } else {
      res.writeHead(200, { 'Content-Length': stat.size, 'Content-Type': 'video/mp4' });
      fs.createReadStream(input).pipe(res);
    }
  });

  await new Promise((resolve) => server.listen(VIDEO_PORT, resolve));
  const videoSrc = `http://localhost:${VIDEO_PORT}/video`;

  const inputProps = {
    videoSrc,
    transcription,
    subtitleStyle: subtitleStyle || 'hormozi',
    subtitlePlacement: subtitlePlacement || 'middle',
  };

  // Select composition
  const composition = await selectComposition({
    serveUrl,
    id: 'CaptionedVideo',
    inputProps,
    chromiumOptions: { args: chromeArgs },
  });

  // Override composition to match source video
  composition.durationInFrames = durationInFrames;
  composition.fps = fps;
  composition.width = metadata.width || 1080;
  composition.height = metadata.height || 1920;

  // Render
  console.log(`[Remotion] Rendering ${durationInFrames} frames...`);
  await renderMedia({
    composition,
    serveUrl,
    codec: 'h264',
    outputLocation: output,
    inputProps,
    concurrency: 1,
    timeoutInMilliseconds: 300000, // 5 minutes
    chromiumOptions: { args: chromeArgs },
    offthreadVideoCacheSizeInBytes: 100 * 1024 * 1024, // 100MB cache (Modal has plenty of RAM)
  });

  // Cleanup
  server.close();
  console.log(`[Remotion] ✅ Render complete: ${output}`);
  const stat = fs.statSync(output);
  console.log(`[Remotion] Output size: ${(stat.size / 1024 / 1024).toFixed(1)} MB`);
}

main().catch((err) => {
  console.error(`[Remotion] ❌ Render failed: ${err.message}`);
  process.exit(1);
});
