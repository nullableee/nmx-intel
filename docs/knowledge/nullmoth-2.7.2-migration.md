# NullMoth 2.7.2 migration audit

Target: `nullmoth/nvidia-macos-driver` tag `v2.7.2`.
Comparison: [v2.7.1...v2.7.2](https://github.com/nullmoth/nvidia-macos-driver/compare/v2.7.1...v2.7.2).

This is a source audit plus an initial source-level port. No kext has been built, installed, or boot-tested for 2.7.2.

## Upstream delta

GitHub compare reports 14 commits and changes across NVRM, NVRMFB, NMIntelFB, NVAccel, the Metal plugin, and test tooling.

Relevant source changes include:

- `kexts/NVRM/NVRM.cpp`: adds the `nvDisplayPointers` platform function. It validates `NVRM_DISPLAY_PTRS_ABI_VERSION`, returns the NVKMS KAPI table and physical-address translation function to a requesting kernel extension, and no longer requires those pointers to be published as ordinary IORegistry properties.
- `kexts/NVRM/nvrm_gpuva_abi.h`: adds `NVRM_DISPLAY_PTRS_ABI_VERSION 1`, `NVRM_DISPLAY_PTRS_FN`, and `NVRMDisplayPointers`. Existing `NVRM_GPUVA_ABI_VERSION` remains 1 and `NVRM_FLIP_ABI_VERSION` remains 2. This is an additive API, but every consumer must be reviewed.
- `kexts/NVRMFB/fb/nvrm-fb.cpp`: NVRMFB now calls `nvDisplayPointers` and consumes the returned pointers rather than reading them from the display nub's properties.
- `kexts/NMIntelFB/intelfb.cpp`: the synthetic Intel-panel nub now copies only `gpu-id`; it no longer copies `nvkms-kapi` or `phys-for-va`.
- `kexts/NVRM/os-xnu2.cpp`, `kexts/NVRM/NVRM.cpp`, and NVAccel have further changes. The release changelog also calls out kernel-driver race fixes, removal of kernel-address disclosure, and privilege restrictions on profiling/channel priority.

## NMX compatibility finding

The historical NMX Intel-panel bridge creates a synthetic `NVRMDisplay` nub under NVRM. Its old patch copied
`nvkms-kapi`, `gpu-id`, and `phys-for-va` from the first display nub. In 2.7.2, upstream intentionally removed
the two pointer properties as a security hardening measure.

**Initial source port added on branch `upgrade/nullmoth-2.7.2`:** patch
`source-fixes/intelfb/intelfb-0022-nvdisplaypointers.patch` changes the synthetic nub to copy only `gpu-id`.
The NMIntelFB KAPI setup now calls `nvDisplayPointers` on the NVRM provider, passes ABI version 1, checks the
`callPlatformFunction` result, and keeps the returned pointers in the framebuffer's private fields. The build script
stages the exact `nvrm_gpuva_abi.h` from the selected upstream tag and rejects a resulting source file that still
contains either legacy IORegistry key.

This is a source-level implementation only: patch application against the full 2.7.2 patch series, compilation,
and runtime behavior are not yet verified. Do not install it yet.

## Other migration consequences

- **NVAccel:** `nvrm-accel.cpp` changes again. Replay the four NMX patches onto a clean 2.7.2 worktree, then inspect
  the resulting headless-display-owner logic and all NMX sysctls. A clean cherry-pick is not proof of semantic
  compatibility.
- **NMIntelFB:** the source changed by 5 lines in the compare. The duplicate backlight implementation is already
  upstream; do not reintroduce the old NMX brightness handler. Review every remaining NMX patch against 2.7.2.
- **NVRM binary patch:** NVRM source and binary layout changed. No 2.7.1 or earlier offsets, rel32 displacements, or
  hashes may be reused. Keep `tools/nvrm/build.sh` fail-closed until the official 2.7.2 package is inspected.
- **Release scope:** 2.7.2 is built for macOS 15 and 26 only; other macOS versions are intentionally left without a
  Metal device.

## Validation gates

- [x] Add a source-level port of the synthetic Intel-panel nub to the protected `nvDisplayPointers` API.
- [ ] Verify the complete patch series applies cleanly to the 2.7.2 source and inspect the resulting diff.
- [ ] Confirm no public IORegistry property exposes either kernel pointer.
- [ ] Rebase and review all four NVAccel patches on 2.7.2.
- [ ] Build NMIntelFB and NVAccel on a macOS build host.
- [ ] Verify ABI use and NMX sysctls in built artifacts.
- [ ] Inspect the official 2.7.2 NVRM binary hash, Mach-O layout, offsets and disassembly before any byte patch.
- [ ] Test boot, display, brightness, recovery and rollback on target hardware.

Until the build and runtime gates pass, 2.7.2 support is not established. Preserve the known-good setup and recovery path.
