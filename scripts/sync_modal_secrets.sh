#!/usr/bin/env bash
# sync_modal_secrets.sh — reads env.saas and pushes all key=value pairs
# to Modal as the "ugc-engine-secrets" secret.
#
# Usage:  ./scripts/sync_modal_secrets.sh [path/to/env.saas]

set -euo pipefail

ENV_FILE="${1:-env.saas}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: $ENV_FILE not found. Run from the project root or pass the path."
  exit 1
fi

# Collect KEY=VALUE pairs, skipping comments and blank lines
args=()
while IFS= read -r line; do
  # Skip comments and blank lines
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  # Skip lines without '='
  [[ "$line" != *"="* ]] && continue
  args+=("$line")
done < "$ENV_FILE"

if [[ ${#args[@]} -eq 0 ]]; then
  echo "No secrets found in $ENV_FILE"
  exit 1
fi

echo "Syncing ${#args[@]} secrets from $ENV_FILE to Modal 'ugc-engine-secrets'..."
modal secret create ugc-engine-secrets "${args[@]}" --force
echo "Done. Run 'modal deploy modal_worker.py' to pick up the new secrets."
