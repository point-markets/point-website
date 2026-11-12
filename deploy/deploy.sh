#!/bin/bash
# ------------------------------------------------------------------
# Runs on the cPanel server via Cron (every 5 minutes).
# Pulls the latest build from GitHub and copies it into place.
#
#   PREVIEW_DIR  -> test subdomain folder (drafts + published)
#   LIVE_DIR     -> main site folder; leave EMPTY until launch day
#
# Cron command (cPanel > Cron Jobs):
#   PREVIEW_DIR=$HOME/public_html/test.pointmarkets.sa LIVE_DIR= /bin/bash $HOME/repositories/point-website/deploy/deploy.sh >> $HOME/point-deploy.log 2>&1
#
# Daily release of scheduled posts (cPanel cron, 09:05 server time = Riyadh):
#   FORCE=1 BUILD=1 PREVIEW_DIR=$HOME/public_html/test.pointmarkets.sa LIVE_DIR=$HOME/public_html /bin/bash $HOME/repositories/point-website/deploy/deploy.sh >> $HOME/point-deploy.log 2>&1
#
# Second daily release for 4 PM posts (cPanel cron, 16:05 server time = Riyadh): same command as above at 16:05.
# ------------------------------------------------------------------
set -e
export PATH="/usr/local/cpanel/3rdparty/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

git fetch -q origin main
if [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] && [ -z "$FORCE" ]; then
  exit 0
fi
git reset -q --hard origin/main
echo "$(date '+%F %T') deploying $(git rev-parse --short HEAD)"

# BUILD=1: rebuild the site here (releases scheduled posts without waiting for GitHub Actions)
if [ -n "$BUILD" ]; then
  if python3 tools/build.py >/dev/null 2>&1; then echo "  built on server"; else echo "  BUILD FAILED - deploying the committed build instead"; git checkout -q -- public preview; fi
fi

copy() {  # copy SRC/ into DEST/ without deleting anything else in DEST
  if command -v rsync >/dev/null 2>&1; then rsync -a "$1"/ "$2"/; else cp -a "$1"/. "$2"/; fi
}

if [ -n "$PREVIEW_DIR" ] && [ -d "$PREVIEW_DIR" ]; then
  copy "$REPO/preview" "$PREVIEW_DIR"
  git log -1 --format='%h %ci %s' > "$PREVIEW_DIR/version.txt"
  echo "  preview -> $PREVIEW_DIR"
fi
if [ -n "$LIVE_DIR" ] && [ -d "$LIVE_DIR" ]; then
  copy "$REPO/public" "$LIVE_DIR"
  git log -1 --format='%h %ci %s' > "$LIVE_DIR/version.txt"
  echo "  live    -> $LIVE_DIR"
fi
