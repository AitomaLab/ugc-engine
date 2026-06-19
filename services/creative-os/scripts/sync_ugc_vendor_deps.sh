#!/usr/bin/env bash
# Sync repo-root voiceover deps into services/creative-os for Railway deploys.
# Railway root-directory builds often cannot read ../../ at image build time;
# committed copies under services/creative-os/ are the fallback.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="$(cd "$(dirname "$0")/.." && pwd)"
cp -f "$ROOT/elevenlabs_client.py" "$DEST/elevenlabs_client.py"
cp -f "$ROOT/config.py" "$DEST/config.py"
echo "Synced elevenlabs_client.py and config.py -> $DEST"
