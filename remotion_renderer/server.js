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
    });
    bundlePromise.then(url => console.log('[Remotion] Bundle ready:', url));
  }
  return bundlePromise;
}

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'remotion-renderer' });
});

// Serve local video files over HTTP so Remotion's OffthreadVideo can access them.
// Remotion only supports http:// and https:// URLs — not file:// URLs.
app.get('/video', (req, res) => {
  const filePath = req.query.path;
  if (!filePath || !fs.existsSync(filePath)) {
    return res.status(404).json({ error: 'File not found' });
  }

  const stat = fs.statSync(filePath);
  const range = req.headers.range;

  // Support range requests (Remotion uses these for seeking)
  if (range) {
    const parts = range.replace(/bytes=/, '').split('-');
    const start = parseInt(parts[0], 10);
    const end = parts[1] ? parseInt(parts[1], 10) : stat.size - 1;
    const chunkSize = end - start + 1;
    const stream = fs.createReadStream(filePath, { start, end });
    res.writeHead(206, {
      'Content-Range': `bytes ${start}-${end}/${stat.size}`,
      'Accept-Ranges': 'bytes',
      'Content-Length': chunkSize,
      'Content-Type': 'video/mp4',
    });
    stream.pipe(res);
  } else {
    res.writeHead(200, {
      'Content-Length': stat.size,
      'Content-Type': 'video/mp4',
      'Accept-Ranges': 'bytes',
    });
    fs.createReadStream(filePath).pipe(res);
  }
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
    const { renderMedia, selectComposition, getVideoMetadata } = await import('@remotion/renderer');
    const serveUrl = await getBundle();

    // Determine video duration and fps from the source video
    const metadata = await getVideoMetadata(videoPath);
    const fps = Math.round(metadata.fps) || 30;
    const durationInFrames = Math.ceil(metadata.durationInSeconds * fps);

    // Serve the local file over HTTP so Remotion can access it.
    // Remotion's OffthreadVideo only supports http/https URLs, not file:// URLs.
    const absoluteVideoPath = path.resolve(videoPath);
    const videoSrc = `http://localhost:${PORT}/video?path=${encodeURIComponent(absoluteVideoPath)}`;

    const inputProps = {
      videoSrc,
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

    console.log(`[Remotion] Rendering: ${path.basename(videoPath)} -> ${path.basename(outputLocation)}`);
    console.log(`[Remotion] Style: ${inputProps.subtitleStyle}, Placement: ${inputProps.subtitlePlacement}`);
    console.log(`[Remotion] Duration: ${metadata.durationInSeconds.toFixed(2)}s @ ${fps}fps = ${durationInFrames} frames`);
    console.log(`[Remotion] Video URL: ${videoSrc}`);

    await renderMedia({
      composition,
      serveUrl,
      codec: 'h264',
      outputLocation,
      inputProps,
      // Use half the available CPU cores for rendering
      concurrency: Math.max(1, Math.floor(require('os').cpus().length / 2)),
    });

    console.log(`[Remotion] Render complete: ${outputLocation}`);
    res.json({ outputLocation, success: true });

  } catch (err) {
    console.error('[Remotion] Render failed:', err.message);
    res.status(500).json({ error: err.message, success: false });
  }
});

// Start server and pre-warm the bundle
app.listen(PORT, () => {
  console.log(`[Remotion] Renderer listening on port ${PORT}`);
  // Pre-warm the bundle in the background so the first render is fast
  getBundle().catch(err => console.error('[Remotion] Pre-warm failed:', err.message));
});
