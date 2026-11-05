# nmx-intel

Hardware acceleration on a hackintosh laptop whose internal panel is wired to the Intel iGPU, with no MUX switch.

macOS has no driver for Intel iGPUs newer than Ice Lake, so on a laptop like this the panel normally runs on the
firmware framebuffer: no Metal, software compositing, choppy animations. This repo uses the NVIDIA card instead. The
RTX runs on [nullmoth's driver](https://github.com/nullmoth/nvidia-macos-driver) and composites the whole desktop with
Metal, and NMIntelFB (a small framebuffer kext from nullmoth's tree, with our patches) shows each frame on the Intel
panel.

Tested on one machine: Acer Nitro V15 ANV15-51, i5-13420H (iGPU `8086:a7a8`, Raptor Lake-P), RTX 3050 Laptop,
macOS Sequoia 15.8.1, nullmoth's driver 2.3.6. There, wallpaper, transparency, animations and YouTube are smooth;
WindowServer dropped from about 225 % CPU to 67 %, and copying a frame to the panel takes 1.4 ms. Brightness keys
work too.

## Compatibility status

The historical bridge was tested on 2.3.6. The 2.7.1 migration was superseded by upstream 2.7.2 before it was
validated. The current source audit targets `v2.7.2`, but the Intel-panel bridge is **not compatible yet**:
2.7.2 removes the `nvkms-kapi` and `phys-for-va` IORegistry properties and replaces them with the protected
`nvDisplayPointers` platform-function API. The NMX bridge's old pointer-copy path must be ported to that API before
building or installing NMIntelFB. See [the 2.7.2 migration audit](docs/knowledge/nullmoth-2.7.2-migration.md).

The optional NVAccel and NVRM optimizations are also unvalidated for 2.7.2. Do not reuse old NVRM binary offsets or
claim compatibility based only on a successful source rebase.

## Will it work on my laptop?

You need all of these:

- An NVIDIA GPU that nullmoth's driver supports. Check its README first; if the driver doesn't run on your card,
  nothing here helps.
- The internal panel on the Intel iGPU. If your HDMI or USB-C port is wired to the NVIDIA card, an external monitor
  already works with nullmoth's driver alone.
- An Intel iGPU with display version 12 or 13 (Alder Lake, Raptor Lake). The accepted device IDs are in
  `kexts/NMIntelFB/display_ids.inc` in nullmoth's repo, generated from Linux's `pciids.h`. Anything outside that
  list is ignored.
- macOS Sequoia already booting with OpenCore, with the panel working on the firmware framebuffer.
- Xcode Command Line Tools (`xcode-select --install`), git, and internet access during the build (it downloads a
  few NVIDIA headers).
- nullmoth's NVIDIA driver. The original Intel-panel bridge was tested on 2.3.6 only; 2.7.2 is under source audit.

To see your iGPU's device ID:

```bash
system_profiler SPDisplaysDataType > ~/gpus.txt
```

Look for the Intel entry and its "Device ID". Only `0xa7a8` has been tested. Other Alder Lake-P and Raptor Lake IDs
use the same display registers and should behave the same, but nobody has tried yet.

## Install

Do not follow the historical install/build procedure for a 2.7.2 setup yet. The bridge is not ported to the new
protected display-pointer API. Keep the known-good 2.3.6 setup and recovery path until the migration audit's gates pass.

## Known limits

- Sleep breaks the panel on the historical bridge (see `tests/sleep-1-hibernate.md`).
- One display only, the internal panel at its native mode.
- The NVIDIA card stays on all the time. Battery cost hasn't been measured.
- The historical bridge adds a 45-second boot wait.

## Faster copies (optional)

The historical bridge also had a patched NVAccel and a byte patch that made NVRM sleep instead of spin while it waited
for the copy engine. Both are release-specific and are not validated for 2.7.2. See
[the 2.7.2 migration audit](docs/knowledge/nullmoth-2.7.2-migration.md) and the historical
[upgrade runbook](docs/knowledge/nullmoth-upgrade.md).

## The i915 experiment

Before the NVIDIA route, this repo ported Linux's i915 to macOS through nullmoth's NMXGPU (its drm-kmod port, enabled
by the 1401 app's "AMD / Intel" test driver). i915 drives the panel at 1920x1080, 144 Hz, and the desktop is stable,
but WindowServer still compos
