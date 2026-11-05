#!/bin/bash
# Prepare a clean NullMoth 2.7.1 NVAccel worktree and replay the last known NMX patch series.
# This does not build, install, or patch the NVRM binary.
set -euo pipefail
HERE=$(cd "$(dirname "$0")/../.." && pwd)
NM=${NM:-$HOME/nmx-build/nvidia-macos-driver}
SRC=${SRC:-$HOME/nmx-build/accel/src-271}
PATCHDIR=${PATCHDIR:-$HERE/source-fixes/accel/v2.6.4}
TAG=v2.7.1
BASE=v2.6.6
BRANCH=nmx-accel-271

command -v git >/dev/null || { echo "STOP: git is required" >&2; exit 1; }
[ -d "$NM/.git" ] || { echo "STOP: clone NullMoth to $NM first" >&2; exit 1; }
[ -d "$PATCHDIR" ] || { echo "STOP: missing NMX patch series: $PATCHDIR" >&2; exit 1; }
shopt -s nullglob
patches=("$PATCHDIR"/*.patch)
[ "${#patches[@]}" -gt 0 ] || { echo "STOP: no .patch files in $PATCHDIR" >&2; exit 1; }

git -C "$NM" fetch --tags origin
git -C "$NM" rev-parse --verify "$TAG^{commit}" >/dev/null
git -C "$NM" rev-parse --verify "$BASE^{commit}" >/dev/null
[ ! -e "$SRC" ] || { echo "STOP: worktree path already exists: $SRC" >&2; exit 1; }
if git -C "$NM" show-ref --verify --quiet "refs/heads/$BRANCH"; then
  echo "STOP: branch $BRANCH already exists in $NM; inspect it rather than overwriting it" >&2
  exit 1
fi

# These are the ABI and source files consumed by the NMX bridge. They were
# verified byte-identical between v2.6.6 and v2.7.1 during the source audit.
git -C "$NM" diff --quiet "$BASE" "$TAG" -- \
  kexts/NMIntelFB/intelfb.cpp \
  kexts/NVRM/nvrm_vram_abi.h \
  kexts/NVRM/nvrm_gpuva_abi.h \
  kexts/NVRM/nvrm_pageoff.c \
  kexts/NVRM/accel || {
    echo "STOP: audited upstream paths differ from the expected v2.6.6 baseline; review before rebasing" >&2
    exit 1
  }

git -C "$NM" worktree add -b "$BRANCH" "$SRC" "$TAG"
if ! git -C "$SRC" am -3 "${patches[@]}"; then
  echo
  echo "PATCH REPLAY STOPPED. Resolve conflicts in $SRC, then run:"
  echo "  git -C '$SRC' am --continue"
  echo "Or abandon the replay with: git -C '$SRC' am --abort"
  exit 1
fi

echo
echo "Patch series applied to $TAG."
echo "Next: build plain upstream NVAccel and patched NVAccel, compare symbols/strings/sections,"
echo "build macOS 15 and 26 variants, and verify every NMX sysctl before deployment."
echo "Worktree: $SRC"
echo "Branch:   $BRANCH"
echo "No NVRM binary patch was applied."
