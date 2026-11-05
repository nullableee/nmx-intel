# NullMoth 2.7.1 upgrade audit

This short audit is superseded by the detailed, corrected [2.7.1 migration notes](nullmoth-2.7.1-migration.md). Keep that page as the source of truth for the rebase.

Verified upstream:
- Target: `nullmoth/nvidia-macos-driver` tag `v2.7.1`, commit `6b4752c51b0719862fb46471d383317ef7ecc6f0`.
- `v2.6.6...v2.7.1`: 125 commits; `os-xnu.cpp`, installer, and user-space Metal/translator files change; the shared ABI headers, `nvrm_pageoff.c`, and `NMIntelFB/intelfb.cpp` are unchanged over this narrower range.
- `v2.6.4...v2.7.1`: 180 commits; `nvrm-accel.cpp` also gains the Metal-accelerator check in headless-display detection.
- `NMIntelFB/intelfb.cpp` changed between the existing NMX builder base `v2.5.4` and `v2.7.1` (backlight handler and start-failure cleanup). Do not change the builder default until the NMX patch series applies and the kext builds.
- The NVRM byte patch is not supported for 2.7.1 until the official package binary hash, offsets, and rel32 call are verified.

No kext has been built or boot-tested as part of this audit. See the migration notes for the Mac-host commands, patch replay order, and validation gate.
