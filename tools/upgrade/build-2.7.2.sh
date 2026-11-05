#!/bin/bash
# Build the NMX Intel framebuffer and NVAccel variants for NullMoth 2.7.2.
# This script builds only; it does not install kexts or change OpenCore/NVRAM.
set -euo pipefail
HERE=$(cd "$(dirname "$0")/../.." && pwd)
NM=${NM:-$HOME/nmx-build/nvidia-macos-driver}
OGKM=${OGKM:-$HOME/ogkm615}
REV=v2.7.2

mkdir -p "$HOME/nmx-build"
if [ ! -d "$NM/.git" ]; then
  git clone https://github.com/nullmoth/nvidia-macos-driver "$NM"
else
  git -C "$NM" fetch --tags origin
fi
git -C "$NM" rev-parse -q --verify "refs/tags/$REV" >/dev/null || {
  echo "missing upstream tag $REV in $NM" >&2; exit 1;
}

if [ ! -d "$OGKM/src/nvidia" ]; then
  git clone --depth 1 --branch 615.78.08 https://github.com/NVIDIA/open-gpu-kernel-modules "$OGKM"
fi

export NM OGKM REV
bash "$HERE/tools/intelfb/build.sh"
bash "$HERE/tools/upgrade/prepare-2.7.2.sh"
bash "$HERE/tools/accel/build.sh"

echo
echo "Build complete (nothing installed):"
echo "  NMIntelFB: $HOME/nmx-build/intelfb/out/NMIntelFB.kext"
echo "  NVAccel 15: $HOME/nmx-build/accel/out/15/NVAccel.kext"
echo "  NVAccel 26: $HOME/nmx-build/accel/out/26/NVAccel.kext"
