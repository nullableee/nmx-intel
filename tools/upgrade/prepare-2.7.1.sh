#!/bin/bash
# Rebase the 2.6.4 NMX NVAccel patch series onto NullMoth 2.7.1.
# This does not build, install, or patch the NVRM binary.
set -euo pipefail
HERE=$(cd "$(dirname "$0")/../.." && pwd)
NM=${NM:-$HOME/nmx-build/nvidia-macos-driver}
PATCH_SRC=${PATCH_SRC:-$HOME/nmx-build/accel/rebase-264}
SRC=${SRC:-$HOME/nmx-build/accel/src-271}
PATCHDIR=${PATCHDIR:-$HERE/source-fixes/accel/v2.6.4}
BASE=v2.6.4
TAG=v2.7.1
PATCH_BRANCH=nmx-accel-264-rebase-271
BRANCH=nmx-accel-271

command -v git >/dev/null || { echo "STOP: git is required" >&2; exit 1; }
[ -d "$NM/.git" ] || { echo "STOP: clone NullMoth to $NM first" >&2; exit 1; }
[ -d "$PATCHDIR" ] || { echo "STOP: missing NMX patch series: $PATCHDIR" >&2; exit 1; }
compgen -G "$PATCHDIR/*.patch" >/dev/null || { echo "STOP: no .patch files in $PATCHDIR" >&2; exit 1; }
shopt -s nullglob
patches=("$PATCHDIR"/*.patch)
PATCH_COUNT=${#patches[@]}
[ "$PATCH_COUNT" -eq 4 ] || { echo "STOP: expected the four-patch v2.6.4 series, found $PATCH_COUNT" >&2; exit 1; }

mkdir -p "$(dirname "$PATCH_SRC")" "$(dirname "$SRC")"
git -C "$NM" fetch --tags origin
git -C "$NM" rev-parse --verify "$BASE^{commit}" >/dev/null
git -C "$NM" rev-parse --verify "$TAG^{commit}" >/dev/null
[ ! -e "$PATCH_SRC" ] || { echo "STOP: patch worktree path already exists: $PATCH_SRC" >&2; exit 1; }
[ ! -e "$SRC" ] || { echo "STOP: target worktree path already exists: $SRC" >&2; exit 1; }
for b in "$PATCH_BRANCH" "$BRANCH"; do
  if git -C "$NM" show-ref --verify --quiet "refs/heads/$b"; then
    echo "STOP: branch $b already exists in $NM; inspect it rather than overwriting it" >&2
    exit 1
  fi
done

# NMIntelFB and the shared ABIs are unchanged in 2.6.6..2.7.1. NVAccel itself
# has a separate upstream headless-display-owner change since 2.6.4; replay
# from the original base first, then cherry-pick onto the new tag.
git -C "$NM" diff --quiet v2.6.6 "$TAG" -- \
  kexts/NMIntelFB/intelfb.cpp \
  kexts/NVRM/nvrm_vram_abi.h \
  kexts/NVRM/nvrm_gpuva_abi.h \
  kexts/NVRM/nvrm_pageoff.c || {
    echo "STOP: audited shared source/ABI paths differ from expected; review before rebasing" >&2
    exit 1
  }

git -C "$NM" worktree add -b "$PATCH_BRANCH" "$PATCH_SRC" "$BASE"
if ! git -C "$PATCH_SRC" am -3 "${patches[@]}"; then
  echo "Patch replay onto $BASE stopped. Resolve in $PATCH_SRC, then run git am --continue (or --abort)." >&2
  exit 1
fi
APPLIED=$(git -C "$PATCH_SRC" rev-list --count "$BASE..HEAD")
[ "$APPLIED" -eq "$PATCH_COUNT" ] || { echo "STOP: expected $PATCH_COUNT patch commits, found $APPLIED" >&2; exit 1; }

git -C "$NM" worktree add -b "$BRANCH" "$SRC" "$TAG"
commits=$(git -C "$PATCH_SRC" rev-list --reverse "$BASE..HEAD")
[ -n "$commits" ] || { echo "STOP: no NMX patch commits were created on $PATCH_BRANCH" >&2; exit 1; }
if ! git -C "$SRC" cherry-pick -x $commits; then
  echo
  echo "Rebase onto $TAG needs conflict resolution in $SRC."
  echo "Resolve each conflict, stage the files, then run: git -C '$SRC' cherry-pick --continue"
  echo "To abandon only the target replay: git -C '$SRC' cherry-pick --abort"
  exit 1
fi
REPLAYED=$(git -C "$SRC" rev-list --count "$TAG..HEAD")
[ "$REPLAYED" -eq "$PATCH_COUNT" ] || { echo "STOP: expected $PATCH_COUNT replayed commits, found $REPLAYED" >&2; exit 1; }

echo
echo "NMX patch commits replayed onto $TAG."
echo "Review the 2.7.1 headlessDisplayOwner change and all patch hunks before building."
echo "Build plain upstream NVAccel and patched NVAccel; compare symbols/strings/sections."
echo "Build/test macOS 15 and 26 variants and verify every NMX sysctl before deployment."
echo "Patch-base worktree: $PATCH_SRC"
echo "Target worktree:     $SRC"
echo "Target branch:       $BRANCH"
echo "No NVRM binary patch was applied."
