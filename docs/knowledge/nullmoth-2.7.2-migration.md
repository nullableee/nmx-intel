# NullMoth 2.7.2 migration audit

Target: `nullmoth/nvidia-macos-driver` tag `v2.7.2`.
Comparison: [v2.7.1...v2.7.2](https://github.com/nullmoth/nvidia-macos-driver/compare/v2.7.1...v2.7.2).

This is a source audit plus a compile-validated source port. CI compiled NMIntelFB with the macOS 15 SDK and built patched NVAccel variants for macOS 15 and 26. No kext has been installed or boot-tested on target hardware.

## Upstream delta

GitHub compare reports 14 commits and changes across NVRM, NVRMFB, NMIntelFB, NVAccel, the Metal plugin, and test tooling.

Relevant source changes include:

- `kexts/NVRM/NVRM.cpp`: adds the `nvDisplayPointers` platform function. It validates `NVRM_DISPLAY_PTRS_ABI_VERSION`, returns the NVKMS KAPI table and physical-address translation function to a requesting kernel extension, and no longer requires those pointers to be published as ordinary IORegistry properties.
- `kexts/NVRM/nvrm_gpuva_abi.h`: adds `NVRM_DISPLAY_PTRS_ABI_VERSION 1`, `NVRM_DISPLAY_PTRS_FN`, and `NVRMDisplayPointers`. Existing `NVRM_GPUVA_ABI_VERSION` remains 1 and `NVRM_FLIP_ABI_VERSION` remains 2.
- `kexts/NVRMFB/fb/nvrm-fb.cpp`: upstream NVRMFB now obtains the pointer pair through `nvDisplayPointers`.
- `kexts/NMIntelFB/intelfb.cpp`: the synthetic Intel-panel nub copies only `gpu-id`; it no longer copies `nvkms-kapi` or `phys-for-va`.
- `kexts/NVRM/os-xnu2.cpp`, `kexts/NVRM/NVRM.cpp`, and NVAccel have further changes. The release changelog also calls out kernel-driver race fixes, removal of kernel-address disclosure, and privilege restrictions on profiling/channel priority.

## NMX compatibility port

The historical NMX Intel-panel bridge creates a synthetic `NVRMDisplay` nub under NVRM. Its old patch copied
`nvkms-kapi`, `gpu-id`, and `phys-for-va` from the first display nub. In 2.7.2, upstream intentionally removed
the two pointer properties as a security hardening measure.

The port on branch `upgrade/nullmoth-2.7.2` makes the following changes:

- The synthetic nub copies only `gpu-id`; it no longer publishes kernel pointers in IORegistry.
- NMIntelFB calls `nvDisplayPointers` on the NVRM provider, passes ABI version 1, checks the `callPlatformFunction` result, and stores the returned KAPI and `physForVa` pointers in private framebuffer state.
- The exact `nvrm_gpuva_abi.h` from the selected upstream tag is staged into the NMIntelFB build.
- The AGDC compatibility path is rebased, including the link-configuration and plane-scaler query responses and panel timing publication.
- The four NMX NVAccel patches are replayed on a clean v2.7.2 worktree.

The 2.7.2 build workflow passed on macOS 15 / Xcode 16.4. NMIntelFB compiled to 120,544 bytes (SHA-256 prefix `c40f9c77`). NVAccel built for macOS 15 (SHA-256 prefix `ce79ccff`) and macOS 26 (prefix `6dbc226e`), from patched source head `28c7edc` with VRAM ABI 2. This is compile validation only; it does not prove that the kexts load, that the panel displays, or that frame pacing is correct.

## Other migration consequences

- **NVAccel:** `nvrm-accel.cpp` changes again. The four NMX patches apply to 2.7.2, but their runtime headless-display-owner logic and sysctls still require target testing.
- **NMIntelFB:** upstream already provides its own backlight handler; do not reintroduce the old NMX brightness handler.
- **NVRM binary patch:** NVRM source and binary layout changed. No 2.7.1 or earlier offsets, rel32 displacements, or hashes may be reused. Keep `tools/nvrm/build.sh` fail-closed until the official 2.7.2 package is inspected.
- **Release scope:** 2.7.2 is built for macOS 15 and 26. NVAccel has CI builds for both. NMIntelFB was compiled with the macOS 15 SDK; Tahoe's private AGDC ABI remains unvalidated. The installer intentionally blocks Tahoe.

## Validation gates

- [x] Port the synthetic Intel-panel nub to the protected `nvDisplayPointers` API.
- [x] Verify the NMIntelFB patch series applies and compiles on a macOS 15 build host.
- [x] Rebase and build the four NMX NVAccel patches for macOS 15 and 26.
- [x] Confirm the resulting NMIntelFB source no longer contains the legacy `nvkms-kapi` or `phys-for-va` IORegistry keys.
- [ ] Verify installed NVRM/NVRMFB ABI on the target machine.
- [ ] Boot and test panel output, frame pacing, brightness, cold boot, sleep/wake, and recovery on the GIGABYTE G6 MF.
- [ ] Validate the NMIntelFB/AGDC private ABI on Tahoe 26 before allowing installation there.
- [ ] Inspect the official 2.7.2 NVRM binary hash, Mach-O layout, offsets and disassembly before any byte patch.

The build is ready for controlled Sequoia hardware testing, not for a claim of general 2.7.2 or Tahoe compatibility. Preserve the existing working kexts and OpenCore recovery path.
