#!/bin/bash
# Install only the NMX 2.7.2 NMIntelFB/NVAccel builds. NullMoth NVRM/NVRMFB must already be 2.7.2.
# Usage: sudo bash tools/upgrade/install-2.7.2.sh [restore]
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run with sudo." >&2; exit 1; }
MODE=${1:-install}
HOMEU=$(eval echo "~${SUDO_USER:-root}")
EXT=/Library/Extensions
KC=/Library/KernelCollections/AuxiliaryKernelExtensions.kc
KB=/System/Library/KernelCollections/BootKernelExtensions.kc
KS=/System/Library/KernelCollections/SystemKernelExtensions.kc
K=/System/Library/Kernels/kernel
KARG=(--allow-missing-kdk)
[ -f "$K" ] && KARG+=(--kernel "$K")
BACKUP="$HOMEU/nmx-nullmoth-2.7.2-backup"
ORIG_IFB="$BACKUP/NMIntelFB.kext"
ORIG_ACCEL="$BACKUP/NVAccel.kext"
ORIG_KC="$BACKUP/AuxiliaryKernelExtensions.kc"
TMP=$(mktemp -d)
NEWKC="$KC.nmx-2.7.2-new"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

MAJOR=$(sw_vers -productVersion | cut -d. -f1)
case "$MAJOR" in
  15) ;;
  26)
    if [ "$MODE" = install ]; then
      echo "STOP: Tahoe 26 is not boot-validated for the NMX Intel framebuffer/AGDC bridge yet." >&2
      echo "The NVAccel 26 build is available, but this installer remains Sequoia-only until the AGDC ABI is validated." >&2
      exit 1
    fi ;;
  *) echo "Unsupported macOS major version $MAJOR; expected Sequoia 15." >&2; exit 1 ;;
esac

for k in NVRM NVRMFB NVAccel NMIntelFB; do
  [ -f "$EXT/$k.kext/Contents/MacOS/$k" ] || {
    echo "Missing installed $k.kext. Install NullMoth 2.7.2 first; no files changed." >&2; exit 1;
  }
done

# This API string is present in both 2.7.2 NVRM and NVRMFB. It prevents mixing the new bridge with 2.7.1/older kexts.
strings "$EXT/NVRM.kext/Contents/MacOS/NVRM" | grep -q 'nvDisplayPointers' || {
  echo "Installed NVRM does not expose nvDisplayPointers. Install NullMoth 2.7.2 first; no files changed." >&2; exit 1;
}
strings "$EXT/NVRMFB.kext/Contents/MacOS/NVRMFB" | grep -q 'nvDisplayPointers' || {
  echo "Installed NVRMFB does not use nvDisplayPointers. Install the matching NullMoth 2.7.2 package first; no files changed." >&2; exit 1;
}

if [ "$MODE" = restore ]; then
  [ -d "$ORIG_IFB" ] && [ -d "$ORIG_ACCEL" ] || {
    echo "Missing original-kext backups in $BACKUP; cannot restore." >&2; exit 1;
  }
  SRC_IFB="$ORIG_IFB"
  SRC_ACCEL="$ORIG_ACCEL"
elif [ "$MODE" = install ]; then
  SRC_IFB="$HOMEU/nmx-build/intelfb/out/NMIntelFB.kext"
  SRC_ACCEL="$HOMEU/nmx-build/accel/out/$MAJOR/NVAccel.kext"
  [ -f "$SRC_IFB/Contents/MacOS/NMIntelFB" ] || { echo "Missing $SRC_IFB; run tools/upgrade/build-2.7.2.sh first." >&2; exit 1; }
  [ -f "$SRC_ACCEL/Contents/MacOS/NVAccel" ] || { echo "Missing $SRC_ACCEL; run tools/upgrade/build-2.7.2.sh first." >&2; exit 1; }
else
  echo "Usage: $0 [restore]" >&2; exit 2
fi

mkdir -p "$BACKUP"
if [ ! -d "$ORIG_IFB" ]; then ditto "$EXT/NMIntelFB.kext" "$ORIG_IFB"; fi
if [ ! -d "$ORIG_ACCEL" ]; then ditto "$EXT/NVAccel.kext" "$ORIG_ACCEL"; fi
if [ ! -f "$ORIG_KC" ]; then cp -p "$KC" "$ORIG_KC"; fi

# Keep a transaction-local copy so a failed kmutil build restores exactly the currently installed files.
ditto "$EXT/NMIntelFB.kext" "$TMP/NMIntelFB.kext"
ditto "$EXT/NVAccel.kext" "$TMP/NVAccel.kext"
rollback_files() {
  rm -rf "$EXT/NMIntelFB.kext" "$EXT/NVAccel.kext"
  ditto "$TMP/NMIntelFB.kext" "$EXT/NMIntelFB.kext"
  ditto "$TMP/NVAccel.kext" "$EXT/NVAccel.kext"
  chown -R root:wheel "$EXT/NMIntelFB.kext" "$EXT/NVAccel.kext"
  chmod -R 755 "$EXT/NMIntelFB.kext" "$EXT/NVAccel.kext"
}
rm -f "$NEWKC"
ditto "$SRC_IFB" "$EXT/NMIntelFB.kext.new"
ditto "$SRC_ACCEL" "$EXT/NVAccel.kext.new"
rm -rf "$EXT/NMIntelFB.kext" "$EXT/NVAccel.kext"
mv "$EXT/NMIntelFB.kext.new" "$EXT/NMIntelFB.kext"
mv "$EXT/NVAccel.kext.new" "$EXT/NVAccel.kext"
chown -R root:wheel "$EXT/NMIntelFB.kext" "$EXT/NVAccel.kext"
chmod -R 755 "$EXT/NMIntelFB.kext" "$EXT/NVAccel.kext"

echo "Rebuilding Auxiliary Kernel Collection..."
if ! kmutil create -n aux --volume-root / "${KARG[@]}" -B "$KB" -S "$KS" --repository "$EXT" -A "$NEWKC" -z >"$TMP/kmutil.log" 2>&1; then
  tail -40 "$TMP/kmutil.log" >&2
  echo "kmutil failed; restoring the previously installed kext files." >&2
  rollback_files
  rm -f "$NEWKC"
  exit 1
fi
if ! INS=$(kmutil inspect -a x86_64 -A "$NEWKC" 2>/dev/null); then
  echo "Could not inspect the new collection; restoring previous kext files." >&2
  rollback_files; rm -f "$NEWKC"; exit 1
fi
for k in NVRM NVRMFB NVRMAGDC NVAccel NMIntelFB; do
  if ! printf '%s\n' "$INS" | grep -qw "com.nullmoth.$k"; then
    echo "New collection is missing com.nullmoth.$k; restoring previous kext files." >&2
    rollback_files; rm -f "$NEWKC"; exit 1
  fi
done
mv -f "$NEWKC" "$KC"
nvram -d nullmoth-intelfb-attaching 2>/dev/null || true
nvram -d nullmoth-intelfb-trail 2>/dev/null || true
nvram -d nullmoth-intelfb-beat 2>/dev/null || true
echo "$MODE complete. Backup: $BACKUP"
echo "No OpenCore boot-args were changed. Reboot to activate the kexts."
