#!/bin/bash
# Create a clean NullMoth 2.7.2 NVAccel worktree and replay the four NMX copy-path commits.
set -euo pipefail
HERE=$(cd "$(dirname "$0")/../.." && pwd)
NM=${NM:-$HOME/nmx-build/nvidia-macos-driver}
REV=${REV:-v2.7.2}
SRC=${SRC:-$HOME/nmx-build/accel/src-272}
BRANCH=${BRANCH:-nmx-accel-272}
[ -d "$NM/.git" ] || { echo "missing NullMoth clone: $NM" >&2; exit 1; }
git -C "$NM" rev-parse -q --verify "refs/tags/$REV" >/dev/null || {
  echo "missing tag $REV in $NM; fetch upstream tags first" >&2; exit 1;
}
[ ! -e "$SRC" ] || { echo "worktree path already exists: $SRC" >&2; exit 1; }
if git -C "$NM" show-ref --verify --quiet "refs/heads/$BRANCH"; then
  echo "branch already exists: $BRANCH" >&2; exit 1
fi
mkdir -p "$(dirname "$SRC")"
git -C "$NM" worktree add -b "$BRANCH" "$SRC" "$REV"
for p in "$HERE"/source-fixes/accel/v2.6.4/*.patch; do
  [ -f "$p" ] || continue
  git -C "$SRC" am -3 "$p"
done
echo "Prepared $SRC at $(git -C "$SRC" rev-parse --short HEAD)"
echo "Source base: $REV; replayed NMX's four copy-path commits."
