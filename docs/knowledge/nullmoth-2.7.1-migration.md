# NullMoth 2.7.1 migration notes

Target upstream release: `nullmoth/nvidia-macos-driver` tag `v2.7.1`, commit `6b4752c51b0719862fb46471d383317ef7ecc6f0`.

This is a source-level audit, not a claim that the NMX bridge has been built or boot-tested on the target laptop.

## Verified source comparison: v2.6.6 → v2.7.1

The upstream compare contains 125 commits. The following exact Git blob IDs are identical between the two tags:

| Path | Blob SHA | Finding |
| --- | --- | --- |
| `kexts/NMIntelFB/intelfb.cpp` | `d17df12551303157b71cd9ccbcd6cf16c8b7553c` | unchanged |
| `kexts/NVRM/nvrm_vram_abi.h` | `430fcb431ad443c4ca82b041c4e8d3462c787fcf` | unchanged; ABI version 2 |
| `kexts/NVRM/nvrm_gpuva_abi.h` | `e26646c7ac3c1ec02366366ea7476d3acb2b11c1` | unchanged; GPUVA ABI version 1, flip ABI version 2 |
| `kexts/NVRM/nvrm_pageoff.c` | `b0c2fdb7c2f63ed327849611f04ab5c47ae9162b` | unchanged |

The release diff changes `kexts/NVRM/os-xnu.cpp` (27 additions, 4 deletions), plus the user-space Metal plugin/translator, installer, and supporting files. The upstream README still specifies NVIDIA open-gpu-kernel-modules tag `615.78.08`, matching the NMX build scripts' current OGKM target.

### Consequences for NMX

- **NMIntelFB:** its upstream source and both shared ABI headers are byte-identical to 2.6.6. The build script default is now `REV=v2.7.1`. This establishes source compatibility, not runtime validation; rebuild on the Mac and compare the resulting binary hash with the installed one.
- **NVAccel:** upstream `kexts/NVRM/accel/` is not changed in the v2.6.6 → v2.7.1 compare, and the shared ABI headers are identical. The 2.6.4 NMX patch series should therefore be tried unchanged on a clean 2.7.1 worktree. Do not mark it supported until `git am -3`, build for macOS 15 and 26, compare symbols/strings/sections, and check all NMX sysctls.
- **NVRM copy-engine patch:** `nvrm_pageoff.c` is byte-identical, and the contiguous-run wait still uses the 200000-spin timeout and `osDelayUs(10)`. However, `os-xnu.cpp` changed, which can move code and symbols in the packaged NVRM binary. The 2.6.4 file offsets, rel32 displacement, and SHA-256 must not be reused. The second per-page fallback wait loop also remains in the source; the existing NMX patch description targets only the contiguous-run path.
- **Installer:** 2.7.1 changes `package/install.sh`; read and verify the official package before installation. The release also fixes permissions on `/Library/NullMoth` for the ARM translator.

## Prepare NVAccel on a Mac build host

From the NMX repository root:

```bash
bash tools/upgrade/prepare-2.7.1.sh
```

The helper creates a clean `v2.7.1` worktree and attempts to replay the existing `source-fixes/accel/v2.6.4/*.patch` series with `git am -3`. If a patch conflicts, resolve it in the worktree and do not export a new series until the build passes. The script refuses to overwrite an existing worktree or reuse a dirty source clone.

After the patches apply:

```bash
SRC=~/nmx-build/accel/src-271 OUT=~/nmx-build/accel/out-271 bash tools/accel/build.sh
```

Compare the resulting NVAccel against the unpatched upstream 2.7.1 build before installing. Build both macOS 15 and 26 variants; the upstream helper is `build/accel_build_all.sh kexts/NVRM <out>`. Rebuild both variants whenever either shared ABI header changes.

## NVRM binary patch — still blocked on package evidence

The exact 2.7.1 NVRM binary hash and function offsets have not been obtained from the official release tarball in this environment. Therefore `tools/nvrm/build.sh` intentionally remains fail-closed for 2.7.1.

On the Mac, download `nullmoth-nvidia-2.7.1.tar.gz` and `SHA256SUMS.txt` from the official release. Verify the archive and the inner package manifest, then inspect:

```bash
otool -tV -p _nvrm_ce_copy_to_pages <pkgroot>/Library/Extensions/NVRM.kext/Contents/MacOS/NVRM
nm <pkgroot>/Library/Extensions/NVRM.kext/Contents/MacOS/NVRM | grep -E ' _(os_delay|osDelayUs)$'
shasum -a 256 <pkgroot>/Library/Extensions/NVRM.kext/Contents/MacOS/NVRM
```

Record the exact instructions/disassembly for the contiguous-run loop, the file offsets, the call instruction's rel32 target, and the full binary hash. Only then add a dedicated 2.7.1 case to `tools/nvrm/build.sh`. The script must verify all original bytes before writing, and the patched disassembly must show a call to `_os_delay`. Do not infer offsets from the unchanged C source.

## Validation gate

Do not install the optional NMX NVAccel/NVRM optimizations until all of these are true:

- Official 2.7.1 archive and inner manifest verify.
- NVAccel patch series applies cleanly or has a reviewed rebase.
- NVAccel builds for macOS 15 and 26 against OGKM 615.78.08.
- NMX sysctls used by `tools/intelfb/auto.sh` are present in the built accelerator.
- NMIntelFB builds from `v2.7.1`; shared ABI hashes match.
- NVRM patch uses a dedicated 2.7.1 binary hash and offsets verified from the official package.
- Checkpoint and rollback path are confirmed before reboot.
- Real target-machine boot, display, bridge counters, and rollback are tested.

Until then, keep the NMX bridge optimizations disabled and retain the known-good driver backup.
