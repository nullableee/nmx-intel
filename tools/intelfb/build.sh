#!/bin/bash
# Build the NMX Intel-panel bridge against a selected NullMoth release.
set -euo pipefail
HERE=$(cd "$(dirname "$0")/../.." && pwd)
NM=${NM:-$HOME/nmx-build/nvidia-macos-driver}
REV=${REV:-v2.7.2}
[ "$REV" = "v2.7.2" ] || { echo "STOP: this rebased build helper targets v2.7.2 only." >&2; exit 1; }
W=$HOME/nmx-build/intelfb
rm -rf "$W/src" "$W/out" && mkdir -p "$W/src" "$W/out/NMIntelFB.kext/Contents/MacOS"
git -C "$NM" archive "$REV" kexts/NMIntelFB | tar -x -C "$W/src" --strip-components 2
if [ "$REV" = "v2.7.2" ]; then
  # The protected display-pointer ABI is shared with NVRM; compile against the exact header from the selected tag.
  git -C "$NM" show "$REV:kexts/NVRM/nvrm_gpuva_abi.h" > "$W/src/nvrm_gpuva_abi.h"
fi
for p in "$HERE"/source-fixes/intelfb/intelfb-*.patch; do
  [ -f "$p" ] || continue
  case "$(basename "$p"):$REV" in
    intelfb-0020-panel-brightness.patch:v2.7.1|intelfb-0020-panel-brightness.patch:v2.7.2)
      echo "skip: upstream $REV already provides NMIntelBacklight; do not register a second backlight service"
      continue ;;
    intelfb-0022-nvdisplaypointers.patch:v2.7.2)
      echo "skip: superseded by the rebased 2.7.2 patch 0023"
      continue ;;
    intelfb-0022-nvdisplaypointers.patch:*)
      echo "skip: nvDisplayPointers patch is specific to v2.7.2"
      continue ;;
    intelfb-0023-nvdisplaypointers-2.7.2.patch:v2.7.2)
      echo "apply: protected nvDisplayPointers migration through exact-context helper"
      continue ;;
    intelfb-0023-nvdisplaypointers-2.7.2.patch:*)
      echo "skip: rebased nvDisplayPointers patch is specific to v2.7.2"
      continue ;;
    intelfb-0014-agdc-lists-the-panel.patch:v2.7.2|intelfb-0015-agdc-link-and-plane-scaler.patch:v2.7.2)
      echo "apply: AGDC compatibility through exact-context 2.7.2 helper"
      continue ;;
  esac
  if [ "$(basename "$p")" = "intelfb-0003-dependent-id-before-start.patch" ]; then
    python3 "$HERE/tools/intelfb/apply-2.7.2-port.py" "$W/src/intelfb.cpp" early
  elif ! patch --verbose -l -d "$W/src" -p1 < "$p"; then
    echo "SOURCE CONTEXT AROUND THE REJECT:" >&2
    nl -ba "$W/src/intelfb.cpp" | sed -n '440,500p;580,680p;870,1150p' >&2
    for rej in "$W/src"/*.rej; do
      [ -f "$rej" ] || continue
      echo "REJECTED HUNKS: $rej" >&2
      cat "$rej" >&2
    done
    exit 1
  fi
  echo "patch: $(basename "$p")"
  if [ "$(basename "$p")" = "intelfb-0011-nvkms-device-answers-nvaccel.patch" ]; then
    python3 "$HERE/tools/intelfb/apply-2.7.2-port.py" "$W/src/intelfb.cpp" kapi
  elif [ "$(basename "$p")" = "intelfb-0013-panel-under-nvrm.patch" ]; then
    python3 "$HERE/tools/intelfb/apply-2.7.2-port.py" "$W/src/intelfb.cpp" agdc
    python3 "$HERE/tools/intelfb/apply-2.7.2-port.py" "$W/src/intelfb.cpp" k5
  fi
done
if [ "$REV" = "v2.7.2" ]; then
  python3 "$HERE/tools/intelfb/apply-2.7.2-port.py" "$W/src/intelfb.cpp" nvdisplay
  grep -Fq 'NVRMDisplayPointers displayPtrs' "$W/src/intelfb.cpp" || { echo "STOP: protected display-pointer call was not applied" >&2; exit 1; }
  grep -Fq 'NVRM_DISPLAY_PTRS_FN' "$W/src/intelfb.cpp" || { echo "STOP: nvDisplayPointers ABI symbol missing" >&2; exit 1; }
  if grep -Eq '"nvkms-kapi"|"phys-for-va"' "$W/src/intelfb.cpp"; then
    echo "STOP: legacy public kernel-pointer IORegistry properties remain in NMIntelFB" >&2
    exit 1
  fi
  echo "2.7.2 AGDC source tail:"
  nl -ba "$W/src/intelfb.cpp" | sed -n '1135,1165p'
fi
# intelfb-0011 needs NVKMS's kernel API headers, from NVIDIA's open-gpu-kernel-modules at the tag NVRM is built from.
OGKM_TAG=${OGKM_TAG:-615.78.08}; KAPI=$W/kapi-hdr-$OGKM_TAG
if [ ! -s "$KAPI/nvkms-kapi.h" ]; then
  mkdir -p "$KAPI"
  for f in nvidia-modeset/kapi/interface/nvkms-kapi.h common/sdk/nvidia/inc/nvtypes.h common/inc/nv_mig_types.h \
           nvidia/arch/nvalloc/unix/include/nv-gpu-info.h common/unix/common/inc/nv_dpy_id.h \
           common/unix/common/inc/nv_common_utils.h nvidia-modeset/interface/nvkms-api-types.h \
           nvidia-modeset/interface/nvkms-format.h common/sdk/nvidia/inc/cpuopsys.h common/sdk/nvidia/inc/nvlimits.h \
           common/sdk/nvidia/inc/nvmisc.h common/sdk/nvidia/inc/nvstatus.h common/sdk/nvidia/inc/nvstatuscodes.h; do
    curl -sfL -o "$KAPI/$(basename "$f")" "https://raw.githubusercontent.com/NVIDIA/open-gpu-kernel-modules/$OGKM_TAG/src/$f" \
      || { echo "could not fetch $f"; rm -f "$KAPI/nvkms-kapi.h"; exit 1; }
  done
fi
SDK=$(xcrun --show-sdk-path); KHDR="$SDK/System/Library/Frameworks/Kernel.framework/Headers"
xcrun clang++ -arch x86_64 -fapple-kext -mkernel -nostdinc -I"$KHDR" -I"$W/src" -I"$KAPI" \
  -DKERNEL -DKERNEL_PRIVATE -DDRIVER_PRIVATE -DAPPLE -DNeXT -UNMINTELFB_VIRTUAL \
  -mmacosx-version-min=15.0 -g0 -ffile-prefix-map="$W/src"=driver -ffile-prefix-map="$HOME"=/build \
  -std=c++17 -fno-rtti -fno-exceptions -fno-builtin -fno-common \
  -Wall -Wno-unused-parameter -Wno-inconsistent-missing-override -O2 \
  -c "$W/src/intelfb.cpp" -o "$W/out/intelfb.o"
xcrun clang++ -arch x86_64 -mmacosx-version-min=15.0 -fapple-kext -nostdlib -Xlinker -kext -lkmodc++ -lkmod -lcc_kext "$W/out/intelfb.o" \
  -o "$W/out/NMIntelFB.kext/Contents/MacOS/NMIntelFB"
cp "$W/src/Info.plist" "$W/out/NMIntelFB.kext/Contents/Info.plist"
plutil -lint "$W/out/NMIntelFB.kext/Contents/Info.plist"
nm "$W/out/NMIntelFB.kext/Contents/MacOS/NMIntelFB" > "$W/out/nm-symbols.txt"
grep -q '_kmod_info' "$W/out/nm-symbols.txt" || { echo "STOP: linked kext has no _kmod_info" >&2; exit 1; }
grep -q 'gMetaClass' "$W/out/nm-symbols.txt" || { echo "STOP: IOKit metaclasses missing from linked kext" >&2; exit 1; }
codesign -f -s - "$W/out/NMIntelFB.kext" >/dev/null 2>&1 || true
echo "NMIntelFB $(shasum -a 256 "$W/out/NMIntelFB.kext/Contents/MacOS/NMIntelFB" | cut -c1-8) $(stat -f %z "$W/out/NMIntelFB.kext/Contents/MacOS/NMIntelFB") B ($REV)"
