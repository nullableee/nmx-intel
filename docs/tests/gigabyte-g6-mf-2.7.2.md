# GIGABYTE G6 MF — NullMoth 2.7.2 NMX test plan

Target hardware supplied for this test: GIGABYTE G6 MF, Core i5-13500H, RTX 4050 Laptop, no MUX. The internal panel is routed through the Intel iGPU; NVIDIA renders the desktop through NMX.

This is a controlled Sequoia test plan. CI compilation passed, but this machine has not yet been boot-tested with the new kexts. Tahoe 26 installation is intentionally blocked.

## Preconditions

- macOS Sequoia 15 boots normally with the current working NMX setup.
- NullMoth v2.7.2 is installed. The installer verifies that both NVRM and NVRMFB contain the `nvDisplayPointers` API string.
- Keep the existing OpenCore recovery route, current working kexts, and NVRAM/boot-job settings. The installer does not change OpenCore or boot arguments.
- Save work before installation; a reboot is required.

## Build

From the repository root:

```bash
bash tools/upgrade/build-2.7.2.sh
```

Expected outputs:

- `~/nmx-build/intelfb/out/NMIntelFB.kext`
- `~/nmx-build/accel/out/15/NVAccel.kext`
- `~/nmx-build/accel/out/26/NVAccel.kext`

The build script does not install anything.

## Install and rollback

Install the Sequoia 15 variants:

```bash
sudo bash tools/upgrade/install-2.7.2.sh
```

Reboot and test the internal panel. If the new kexts fail, boot through the existing OpenCore recovery path and restore the saved kexts:

```bash
sudo bash tools/upgrade/install-2.7.2.sh restore
```

The installer stores the first pre-install NMIntelFB/NVAccel backups in `~/nmx-nullmoth-2.7.2-backup`. It refuses to install unless the installed NVRM/NVRMFB expose the 2.7.2 pointer API.

## Validation sequence

- [ ] Cold boot reaches the login window on the internal panel.
- [ ] `kmutil showloaded --list-only | grep -E 'NVRM|NVRMFB|NVRMAGDC|NVAccel|NMIntelFB'` shows the expected kexts.
- [ ] `system_profiler SPDisplaysDataType` reports the RTX 4050 with Metal support and the internal display remains active through Intel.
- [ ] WindowServer compositing, transparency, Mission Control, window dragging, and video playback are stable.
- [ ] Brightness keys and brightness slider work.
- [ ] Check for tearing, flashes, black frames, and cursor artifacts during sustained movement.
- [ ] Record frame-copy counters and WindowServer CPU before/after using the existing diagnostics in `docs/knowledge/diagnostics.md`.
- [ ] Verify a second cold boot before testing sleep/wake.

Do not treat sleep/wake as supported based on the build result. The historical bridge had a panel-resume failure after sleep; test it separately and keep a recovery route available.

## Tahoe 26

NVAccel has a macOS 26 build, but the NMIntelFB/AGDC private ABI has not been validated on Tahoe. The installer blocks Tahoe 26 deliberately. Do not bypass that guard until the AGDC layout and runtime behavior are verified on Tahoe.
