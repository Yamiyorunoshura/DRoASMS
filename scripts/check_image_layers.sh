#!/usr/bin/env bash
set -euo pipefail

# Minimal image-layer sanity check
#
# Usage:
#   scripts/check_image_layers.sh <image:tag>
#
# Performs lightweight checks to reduce risk of leaking secrets into the image:
# - Greps docker history for suspicious strings (.env/token/secret/password)
# - Scans filesystem (via docker create + export) for obvious secret files

IMAGE=${1:-}
if [[ -z "$IMAGE" ]]; then
  echo "Usage: $0 <image:tag>" >&2
  exit 2
fi

echo "[check] docker history $IMAGE"
docker history --no-trunc "$IMAGE" || {
  echo "[error] image not found: $IMAGE" >&2
  exit 1
}

echo "[check] scanning docker history for suspicious tokens"
if docker history --no-trunc "$IMAGE" | \
  rg -i "(\\.env|token|secret|password|apikey|client_secret)" -n; then
  echo "[warn] Potential sensitive markers found in image history (review above)." >&2
fi

echo "[check] scanning filesystem for secret-like files (shallow)"
CID=$(docker create "$IMAGE" sh 2>/dev/null || true)
if [[ -n "$CID" ]]; then
  # Export layer tar and list files (avoid extracting to disk)
  docker export "$CID" | tar -tvf - 2>/dev/null | \
    rg -i "(\\.env($|\\.)|id_[^/]+|\\.pem$|\\.crt$|\\.key$)" -n || true
  docker rm -v "$CID" >/dev/null 2>&1 || true
else
  echo "[info] runtime not available to create container; skipping fs scan" >&2
fi

echo "[ok] checks completed"

