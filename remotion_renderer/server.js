const express = require('express');
const path = require('path');
const fs = require('fs');
const { execSync } = require('child_process');

const app = express();
app.use(express.json({ limit: '50mb' }));

const PORT = process.env.PORT || process.env.REMOTION_PORT || 8090;

// Chrome args required for running in Docker/cloud containers
const chromeArgs = [
  '--no-sandbox',
  '--disable-setuid-sandbox',
  '--disable-dev-shm-usage',
  '--disable-gpu',
];

// Memory limit for offthread video cache (50MB to stay within 1GB Railway limit)
const OFFTHREAD_CACHE_SIZE = 50 * 1024 * 1024; // 50MB

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

// Debug endpoint to inspect Chrome Headless Shell and system info
app.get('/debug', (req, res) => {
  const os = require('os');
  const info = {
    chromeArgs,
    offthreadCacheSize: `${OFFTHREAD_CACHE_SIZE / 1024 / 1024}MB`,
    system: {
      totalMemory: `${Math.round(os.totalmem() / 1024 / 1024)}MB`,
      freeMemory: `${Math.round(os.freemem() / 1024 / 1024)}MB`,
      cpus: os.cpus().length,
    },
    note: 'Using Remotion built-in Chrome Headless Shell (pre-downloaded at build time)',
  };
  res.json(info);
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
  const { videoPath, videoUrl, transcription, subtitleStyle, subtitlePlacement } = req.body;

  // Validate required fields
  if ((!videoPath && !videoUrl) || !transcription) {
    return res.status(400).json({ error: 'videoPath or videoUrl, and transcription are required' });
  }

  // Determine which video source to use
  let localVideoPath = videoPath;
  let tempDownloaded = false;

  // If a remote URL is provided (cloud-to-cloud), download it to a temp file
  if (videoUrl && !videoPath) {
    try {
      const os = require('os');
      const https = require('https');
      const http = require('http');
      const tmpDir = os.tmpdir();
      const tmpFile = path.join(tmpDir, `remotion_input_${Date.now()}.mp4`);
      console.log(`[Remotion] Downloading remote video: ${videoUrl}`);

      await new Promise((resolve, reject) => {
        const protocol = videoUrl.startsWith('https') ? https : http;
        const file = fs.createWriteStream(tmpFile);
        protocol.get(videoUrl, (response) => {
          // Handle redirects
          if (response.statusCode === 301 || response.statusCode === 302) {
            const redirectUrl = response.headers.location;
            const redirProtocol = redirectUrl.startsWith('https') ? https : http;
            redirProtocol.get(redirectUrl, (redirRes) => {
              redirRes.pipe(file);
              file.on('finish', () => { file.close(); resolve(); });
            }).on('error', reject);
          } else {
            response.pipe(file);
            file.on('finish', () => { file.close(); resolve(); });
          }
        }).on('error', reject);
      });

      console.log(`[Remotion] Downloaded to: ${tmpFile} (${(fs.statSync(tmpFile).size / 1024 / 1024).toFixed(1)} MB)`);
      localVideoPath = tmpFile;
      tempDownloaded = true;
    } catch (dlErr) {
      console.error('[Remotion] Failed to download remote video:', dlErr.message);
      return res.status(400).json({ error: `Failed to download remote video: ${dlErr.message}` });
    }
  }

  if (!fs.existsSync(localVideoPath)) {
    return res.status(400).json({ error: `Video file not found: ${localVideoPath}` });
  }

  try {
    const { renderMedia, selectComposition, getVideoMetadata } = await import('@remotion/renderer');
    const serveUrl = await getBundle();

    // Determine video duration and fps from the source video
    const metadata = await getVideoMetadata(localVideoPath);
    const fps = Math.round(metadata.fps) || 30;
    const durationInFrames = Math.ceil(metadata.durationInSeconds * fps);

    // Serve the local file over HTTP so Remotion can access it.
    const absoluteVideoPath = path.resolve(localVideoPath);
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
      chromiumOptions: { args: chromeArgs },
      offthreadVideoCacheSizeInBytes: OFFTHREAD_CACHE_SIZE,
    });

    // Override composition duration and fps to match the source video exactly
    composition.durationInFrames = durationInFrames;
    composition.fps = fps;
    composition.width = metadata.width || 1080;
    composition.height = metadata.height || 1920;

    // Output path: same directory as input, with _captioned suffix
    const ext = path.extname(localVideoPath);
    const outputLocation = localVideoPath.replace(ext, `_captioned${ext}`);

    console.log(`[Remotion] Rendering: ${path.basename(localVideoPath)} -> ${path.basename(outputLocation)}`);
    console.log(`[Remotion] Style: ${inputProps.subtitleStyle}, Placement: ${inputProps.subtitlePlacement}`);
    console.log(`[Remotion] Duration: ${metadata.durationInSeconds.toFixed(2)}s @ ${fps}fps = ${durationInFrames} frames`);

    await renderMedia({
      composition,
      serveUrl,
      codec: 'h264',
      outputLocation,
      inputProps,
      concurrency: 1, // Force single-thread for 1GB Railway instances
      timeoutInMilliseconds: 240000, // 4 minute timeout
      chromiumOptions: { args: chromeArgs },
      offthreadVideoCacheSizeInBytes: OFFTHREAD_CACHE_SIZE,
    });

    console.log(`[Remotion] Render complete: ${outputLocation}`);

    // Read the captioned file and return it as a downloadable binary response
    // so the caller (Modal) can save it directly without needing filesystem access.
    const stat = fs.statSync(outputLocation);
    res.writeHead(200, {
      'Content-Type': 'video/mp4',
      'Content-Length': stat.size,
      'Content-Disposition': `attachment; filename="${path.basename(outputLocation)}"`,
      'X-Output-Location': outputLocation,
    });
    fs.createReadStream(outputLocation).pipe(res);

    // Cleanup temp files after response is sent
    res.on('finish', () => {
      try {
        if (tempDownloaded && fs.existsSync(localVideoPath)) fs.unlinkSync(localVideoPath);
        if (fs.existsSync(outputLocation)) fs.unlinkSync(outputLocation);
      } catch (_) {}
    });

  } catch (err) {
    console.error('[Remotion] Render failed:', err.message);
    // Cleanup temp file on failure
    if (tempDownloaded && fs.existsSync(localVideoPath)) {
      try { fs.unlinkSync(localVideoPath); } catch (_) {}
    }
    res.status(500).json({ error: err.message, success: false });
  }
});

// Start server and pre-warm the bundle
app.listen(PORT, () => {
  console.log(`[Remotion] Renderer listening on port ${PORT}`);
  // Pre-warm the bundle in the background so the first render is fast
  getBundle().catch(err => console.error('[Remotion] Pre-warm failed:', err.message));
});
