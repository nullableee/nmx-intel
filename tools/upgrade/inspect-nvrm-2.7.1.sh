#!/bin/bash
# Inspect the official NullMoth 2.7.1 NVRM binary before deriving any byte-patch offsets.
# Read-only: this script never modifies the supplied kext.
set -euo pipefail
SRCK=${SRCK:-}
[ -n "$SRCK" ] || { echo "Usage: SRCK=/path/to/pkgroot/Library/Extensions/NVRM.kext bash $0" >&2; exit 2; }
BIN="$SRCK/Contents/MacOS/NVRM"
[ -f "$BIN" ] || { echo "STOP: missing $BIN" >&2; exit 1; }
command -v otool >/dev/null || { echo "STOP: run this on macOS with Xcode command line tools" >&2; exit 1; }
OUT=${OUT:-$HOME/nmx-build/nvrm/inspect-2.7.1.txt}
mkdir -p "$(dirname "$OUT")"
{
  echo "NVRM bundle: $SRCK"
  echo "Binary: $BIN"
  echo "SHA-256:"
  shasum -a 256 "$BIN"
  echo
  echo "Bundle version:"
  /usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$SRCK/Contents/Info.plist" 2>&1 || true
  echo
  echo "Mach-O __TEXT segments:"
  otool -l "$BIN" | grep -A30 -B2 "segname __TEXT"
  echo
  echo "Symbols:"
  nm -gU "$BIN" | grep -E '(^| )_?(os_delay|osDelayUs)$' || true
  echo
  echo "nvrm_ce_copy_to_pages disassembly around delay calls:"
  otool -tV -p _nvrm_ce_copy_to_pages "$BIN" | grep -n -B10 -A10 'osDelayUs' || true
} | tee "$OUT"
echo
echo "Read-only inspection saved to $OUT"
echo "Do not patch until the contiguous-run wait is identified by control flow and all old bytes/rel32 are recorded."
