# Status

> **Summary.** Last updated 2026-11-05. The NullMoth 2.7.2 NMX source port now passes the macOS 15 CI build: NMIntelFB compiles, all four NMX NVAccel patches apply, and NVAccel builds for macOS 15 and 26. No kext has been installed or boot-tested on the target GIGABYTE G6 MF.

## NullMoth 2.7.2 migration

- Target: upstream `nullmoth/nvidia-macos-driver` tag `v2.7.2`.
- Critical upstream change: NVRM no longer publishes `nvkms-kapi` and `phys-for-va` as IORegistry properties. It exposes `nvDisplayPointers` through `callPlatformFunction`; upstream NVRMFB uses that API.
- NMX port: NMIntelFB now calls `nvDisplayPointers` on its NVRM provider, validates the API result, and keeps the returned pointers in private fields. The synthetic Intel-panel nub copies only `gpu-id`.
- The NMX AGDC timing/link path has been rebased. The four NMX NVAccel patches apply to a clean v2.7.2 worktree.
- CI on macOS 15 / Xcode 16.4 compiled NMIntelFB and built NVAccel for both macOS 15 and 26. This verifies source patch application and compilation only; it does not establish runtime or display compatibility.
- NMIntelFB CI artifact: `c40f9c77`, 120,544 bytes.
- NVAccel CI artifacts: macOS 15 `ce79ccff`; macOS 26 `6dbc226e`. Patched NVAccel source head: `28c7edc`, VRAM ABI 2.
- `tools/upgrade/build-2.7.2.sh` builds both components. `tools/upgrade/install-2.7.2.sh` backs up the existing kexts, checks for the protected pointer API in installed NVRM/NVRMFB, and can restore the saved NMIntelFB/NVAccel kexts.
- Installer is deliberately Sequoia 15-only. Tahoe 26 has an NVAccel build, but the NMIntelFB/AGDC private ABI has not been validated or boot-tested on Tahoe.
- NVRM byte patch remains disabled: no exact official 2.7.2 package hash, disassembly, offsets, or call-target verification.

Details: [2.7.2 migration audit](knowledge/nullmoth-2.7.2-migration.md).

## Historical known-good setup

- Intel-panel bridge: tested on nullmoth 2.3.6 on Acer Nitro V15 ANV15-51, i5-13420H, RTX 3050 Laptop, macOS 15.8.1.
- The old setup uses NMIntelFB and optional NVAccel/NVRM optimizations; do not infer its behavior on 2.7.x.
- Preserve the current working G6 MF setup and OpenCore recovery route until the new kexts pass hardware testing.

## Required next work

1. Install/test the 2.7.2 build on the GIGABYTE G6 MF with a verified rollback path.
2. Verify internal-panel output, WindowServer composition, frame pacing, brightness, cold boot, sleep/wake, and recovery.
3. Compare Sequoia 15 with Tahoe 26 only after the Sequoia hardware test passes; Tahoe requires separate AGDC ABI validation.
4. Inspect the official 2.7.2 NVRM binary before considering any byte patch.

## Other areas

- WhateverXe hybrid and Wi-Fi work are documented in their dedicated test notes; this status page tracks the NullMoth bridge migration only.
