# Status

> **Summary.** Last updated 2026-11-05. NullMoth 2.7.2 has superseded the unfinished 2.7.1 migration. The original
> Intel-panel bridge remains proven only on 2.3.6. The 2.7.2 source audit found a display-pointer API/security change
> that requires an NMX bridge port before build or install.

## NullMoth 2.7.2 migration (initial source port; build validation pending)

- Target: upstream `v2.7.2`, 14 commits after `v2.7.1`.
- Critical change: upstream no longer publishes `nvkms-kapi` and `phys-for-va` as IORegistry properties. It adds
  `nvDisplayPointers` on NVRM's `callPlatformFunction`; NVRMFB now requests the pointers through that API.
- Upstream NMIntelFB's attach path now copies only `gpu-id`. The old NMX bridge path copied the two removed properties into its synthetic Intel-panel nub. A source-level patch now
  changes that path to copy only `gpu-id` and request the pointer pair through `nvDisplayPointers` on the NVRM provider.
- `nvrm_gpuva_abi.h` adds `NVRMDisplayPointers` and ABI version 1; existing GPUVA ABI version 1 and flip ABI version 2
  remain unchanged. Rebuild and inspect all consumers.
- `NVRM.cpp`, `os-xnu2.cpp`, `nvrm-accel.cpp`, `NMIntelFB`, and Metal plugin sources also changed. Review NVAccel
  patch interactions and the new security hardening before any build claim.
- The NMIntelFB source patch and build-script ABI staging are committed on `upgrade/nullmoth-2.7.2`; patch-series application and compilation are not yet verified. No 2.7.2 kext has been built or boot-tested. NVRM byte patch remains unsupported pending exact official package hash,
  disassembly, offsets, and call-target verification.

Details: [2.7.2 migration audit](knowledge/nullmoth-2.7.2-migration.md).

## Historical known-good setup

- Intel-panel bridge: tested on nullmoth 2.3.6 on Acer Nitro V15 ANV15-51, i5-13420H, RTX 3050 Laptop, macOS 15.8.1.
- The old setup uses NMIntelFB and optional NVAccel/NVRM optimizations; do not infer their compatibility with 2.7.x.
- Preserve the 2.3.6 package backup and OpenCore recovery route until the 2.7.2 migration is validated.

## Required next work

1. Verify the NMIntelFB patch series applies to 2.7.2 and compile the resulting kext on macOS.
2. Rebase the NVAccel patch series onto 2.7.2 and review the new headless-display and ABI logic.
3. Build plain and patched kexts on macOS, inspect symbols/sections and ABI consumers, and validate sysctls.
4. Inspect the official 2.7.2 NVRM package before adding any binary patch case.
5. Test boot, panel output, brightness, recovery and rollback on the target machine.

## Other areas

- WhateverXe hybrid and Wi-Fi work are documented in their dedicated test notes; this status page tracks the NullMoth bridge migration only.
