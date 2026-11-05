# NullMoth 2.7.1 upgrade audit

Status: preparation branch; binary patch and runtime validation are deliberately pending.
Target: `nullmoth/nvidia-macos-driver` tag `v2.7.1`.
Previous NMX baseline: `v2.6.4` for the local NVRM/NVAccel build scripts. The repository status notes that upstream 2.6.5 and 2.6.6 were released after that baseline; do not assume the local machine's installed version from this repo metadata.

## Release findings

The upstream changelog for 2.7.1 describes OpenGL render-pass CPU work and ARM-app installer/readability changes. The 2.7.0 release adds experimental ARM-app translation and Tahoe HD Audio support, alongside substantial Metal, shader translator, memory-lifetime and kernel-panic fixes.

A GitHub comparison of `v2.6.6...v2.7.1` reports 125 commits. In the kernel-driver area, the only listed changed file is `kexts/NVRM/os-xnu.cpp`; `kexts/NVRM/nvrm_pageoff.c`, `kexts/NVRM/accel/`, and `kexts/NMIntelFB/` are not listed as changed. The release does add/change a large amount of user-space Metal/plugin and translator code.

Implications:
- The existing NMIntelFB source patch series does not appear to need a source rebase based on the release diff. Still rebuild against the 2.7.1 tree and compare KAPI/header inputs before installing.
- The NVAccel source patch target is unchanged in the upstream diff. Re-apply the existing series to a clean v2.7.1 worktree and verify all three patches apply; rebuild and compare symbols/sysctls.
- The NVRM byte patch MUST NOT be assumed portable. Although the public `nvrm_pageoff.c` wait loop is unchanged, `os-xnu.cpp` changed, so NVRM binary layout, symbol addresses, rel32 call displacement, and SHA-256 may differ. Derive all three byte sequences and offsets from the actual 2.7.1 package binary before adding a hash case.

## Required work on a Mac build host

1. Fetch tag and download the official 2.7.1 release archive plus `SHA256SUMS.txt`; verify archive and every packaged file.
2. Inspect `package/install.sh` before installation. 2.7.1 changes installer behavior and adds ARM-app permissions/readability handling.
3. Create a clean worktree at `v2.7.1`; re-apply the three NMX NVAccel patches with `git am -3`. Resolve only if required, then export a new `source-fixes/accel/v2.7.1/` series.
4. Build plain upstream NVAccel and patched NVAccel using the OGKM tag specified by the 2.7.1 source/release metadata. Confirm symbols and required sysctls, and compare release-vs-plain build sections as in UPG-2.
5. Build NMIntelFB with the 2.7.1 source and matching OGKM KAPI headers. Compare binary and inspect `NvKmsKapiFunctionsTable` if it differs.
6. Derive NVRM patch offsets and bytes from the official 2.7.1 NVRM binary. Require a full SHA-256 match, verify the wait-loop disassembly before and after patching, and add a dedicated 2.7.1 case. Never reuse the 2.6.4 offsets merely because the C source loop is unchanged.
7. Run checkpoint/rollback procedure and test on the actual target Mac. Record OS version, GPU, package hash, kext hashes, boot logs, bridge counters and rollback result before marking this release supported.

## Current status

| Component | 2.7.1 assessment | State |
| --- | --- | --- |
| NMIntelFB | No corresponding upstream path changes reported in v2.6.6...v2.7.1 | Rebuild/KAPI comparison pending |
| NVAccel | `kexts/NVRM/accel/` unchanged in release diff | Rebase/build/sysctl verification pending |
| NVRM byte patch | `os-xnu.cpp` changed; binary offsets/hash unverified | Do not enable yet |
| Installer/Metal plugin | Substantial upstream changes | Official package required; inspect and test |

This branch is not a claim of 2.7.1 runtime compatibility until the binary patch, builds, and target-machine test pass.
