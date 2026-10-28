#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$SCRIPT_DIR/../frontend" ]; then
    REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
elif [ -d "$SCRIPT_DIR/../../frontend" ]; then
    REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
else
    REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

FRONTEND_DIR="$REPO_ROOT/frontend"
echo "Building frontend assets in $FRONTEND_DIR..."
cd "$FRONTEND_DIR"
npm run build
echo "[OK] Frontend production build completed. Dist assets updated for port 8000."
