#!/usr/bin/env bash
# preview.sh — build linkyee with a chosen theme and serve locally
#
# Usage:
#   ./preview.sh                  # build with the theme currently set in config.yml
#   ./preview.sh <theme-name>     # temporarily switch to <theme-name>, build, serve;
#                                 # restores config.yml on Ctrl-C
#
# Requires: bundler + ruby (for the build), and python3 (or ruby) for the static server.

set -euo pipefail

THEME="${1:-}"
PORT="${PORT:-8080}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
CONFIG="$ROOT/config.yml"
BACKUP="$ROOT/config.yml.preview-backup"

if [ ! -f "$CONFIG" ]; then
  echo "Error: $CONFIG not found." >&2
  exit 1
fi

restore_config() {
  if [ -f "$BACKUP" ]; then
    mv "$BACKUP" "$CONFIG"
    echo
    echo "Restored config.yml."
  fi
}

cleanup() {
  trap - INT TERM EXIT
  if [ -n "${SERVER_PID:-}" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  restore_config
}
trap cleanup INT TERM EXIT

if [ -n "$THEME" ]; then
  if [ ! -d "$ROOT/themes/$THEME" ]; then
    echo "Error: themes/$THEME does not exist." >&2
    echo "Available themes:" >&2
    ls -1 "$ROOT/themes/" | sed 's/^/  - /' >&2
    exit 1
  fi
  cp "$CONFIG" "$BACKUP"
  # Replace the first 'theme:' line. Works for both 'theme: x' and 'theme:x'.
  if command -v gsed >/dev/null 2>&1; then
    gsed -i -E "0,/^theme:.*/s//theme: $THEME/" "$CONFIG"
  else
    # macOS BSD sed has no -i in-place GNU style; use a portable two-step.
    awk -v t="$THEME" 'BEGIN{done=0} /^theme:/ && !done {print "theme: " t; done=1; next} {print}' "$CONFIG" > "$CONFIG.tmp"
    mv "$CONFIG.tmp" "$CONFIG"
  fi
  echo "Switched theme to: $THEME"
fi

echo "Building site..."
( cd "$ROOT" && bundle exec ruby ./scaffold.rb )

echo
echo "Preview: http://localhost:$PORT"
echo "Press Ctrl-C to stop and restore config.yml."
echo

cd "$ROOT/_output"
if command -v python3 >/dev/null 2>&1; then
  python3 -m http.server "$PORT" >/dev/null 2>&1 &
elif command -v ruby >/dev/null 2>&1; then
  ruby -run -e httpd . -p "$PORT" >/dev/null 2>&1 &
else
  echo "Error: need python3 or ruby to serve." >&2
  exit 1
fi
SERVER_PID=$!
wait "$SERVER_PID"
