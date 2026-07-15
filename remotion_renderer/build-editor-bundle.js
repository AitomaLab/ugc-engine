/**
 * build-editor-bundle.js — bundle the REAL editor composition for server rendering.
 *
 * The entry (frontend/src/remotion/index.ts) renders the same MainComposition the
 * browser editor previews, so the render can't silently diverge from what the user
 * sees. It must be bundled in place: the module graph reaches sonner, @supabase/ssr
 * and @radix-ui, which resolve from frontend/node_modules, not this package's.
 *
 * Usage:
 *   node build-editor-bundle.js                  # ../frontend
 *   FRONTEND_SRC=/root/frontend node build-editor-bundle.js
 */
const path = require('path');
const fs = require('fs');

const FRONTEND = path.resolve(
  process.env.FRONTEND_SRC || path.join(__dirname, '..', 'frontend'),
);
const OUT_DIR = path.join(__dirname, 'editor-bundle');
const EMPTY_PUBLIC_DIR = path.join(__dirname, '.empty-public');

async function main() {
  const entryPoint = path.join(FRONTEND, 'src', 'remotion', 'index.ts');
  if (!fs.existsSync(entryPoint)) {
    throw new Error(
      `Editor entry not found: ${entryPoint}\n` +
        `Set FRONTEND_SRC to the frontend/ directory (needs its node_modules installed).`,
    );
  }

  const { bundle } = await import('@remotion/bundler');

  fs.mkdirSync(EMPTY_PUBLIC_DIR, { recursive: true });

  console.log(`[build-editor-bundle] entry:  ${entryPoint}`);
  console.log(`[build-editor-bundle] outDir: ${OUT_DIR}`);

  const serveUrl = await bundle({
    entryPoint,
    outDir: OUT_DIR,
    // Nothing in the render path calls staticFile(); left to itself Remotion copies
    // all of frontend/public (~23MB of tutorial screenshots) into the bundle.
    // `null` means "auto-detect", not "none" — point it at an empty dir.
    publicDir: EMPTY_PUBLIC_DIR,
    // Note: don't disable source maps here — Remotion reads them to symbolicate
    // render errors and fails with ENOENT on index.js.map if they're missing.
    webpackOverride: (config) => ({
      ...config,
      resolve: {
        ...config.resolve,
        alias: {
          ...(config.resolve || {}).alias,
          // Next resolves this via tsconfig paths; webpack needs it spelled out.
          '@': path.join(FRONTEND, 'src'),
          // Pin to one copy — the entry lives in frontend/ while the bundler runs
          // from this package, so these can otherwise resolve from two trees and
          // produce "Invalid hook call" at render time.
          react: path.join(FRONTEND, 'node_modules', 'react'),
          'react-dom': path.join(FRONTEND, 'node_modules', 'react-dom'),
          remotion: path.join(FRONTEND, 'node_modules', 'remotion'),
        },
      },
    }),
    onProgress: (p) => {
      if (p % 25 === 0) console.log(`[build-editor-bundle] ${p}%`);
    },
  });

  console.log(`[build-editor-bundle] ✓ ${serveUrl}`);
}

main().catch((err) => {
  console.error('[build-editor-bundle] FAILED');
  console.error(err);
  process.exit(1);
});
