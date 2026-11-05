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

The historical bridge was tested on 2.3.6 only. The current port targets NullMoth `v2.7.2` and adapts the
Intel-panel bridge to the protected `nvDisplayPointers` API: the synthetic display nub carries only `gpu-id`, while
NMIntelFB obtains KAPI and physical-VA pointers from its NVRM provider and keeps them kernel-private. The port also
rebases the NMX AGDC link/timing path and NVAccel changes. A macOS 15 compile check is running in
[GitHub Actions](https://github.com/nullableee/nmx-intel/actions); there is not yet a boot test on target hardware.
See [the 2.7.2 migration audit](docs/knowledge/nullmoth-2.7.2-migration.md).

The NVRM binary sleep patch remains disabled: no exact 2.7.2 package hash, offsets, and disassembly have been verified.
Do not reuse old NVRM binary offsets. Tahoe 26 builds are prepared for NVAccel, but installation of the Intel-panel
bridge remains blocked until its AGDC ABI is validated on Tahoe.

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

The 2.7.2 build is separate from installation. From the repository root:

```bash
bash tools/upgrade/build-2.7.2.sh
```

This builds NMIntelFB and NVAccel for Sequoia 15 and NVAccel for Tahoe 26; it does not install anything. The
transactional installer is Sequoia-only and checks that the installed NVRM/NVRMFB expose `nvDisplayPointers`:

```bash
sudo bash tools/upgrade/install-2.7.2.sh
```

Rollback to the NMIntelFB and NVAccel kexts saved before the first install:

```bash
sudo bash tools/upgrade/install-2.7.2.sh restore
```

The macOS 15 compile workflow has passed, so a controlled Sequoia hardware test is now possible. Neither Sequoia nor
Tahoe has been boot-tested on the GIGABYTE G6 MF. The installer checks the installed NVRM/NVRMFB pointer API and
backs up the current kexts before replacing them. Tahoe 26 remains blocked until the private AGDC ABI is validated
there. Keep a bootable OpenCore recovery path.

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
but WindowServer still composites in software, so it is parked. Build steps and history are in
[docs/index.md](docs/index.md); the sources live in `build/` and `source-fixes/`.

## Repo layout

```
tools/intelfb/   build, install and boot job for NMIntelFB (historical route)
tools/accel/     patched NVAccel (optional speedup)
tools/nvrm/      NVRM byte patch (optional speedup)
tools/sleep/     hibernation experiment (parked)
tools/upgrade/   2.7.2 build, install and rollback helpers
tools/wifi/      MediaTek MT7921 Wi-Fi
source-fixes/    our patches: intelfb/, accel/, and the i915 port
build/           i915 port: set up ~/nmx-build, apply fixes, build NMXGPU
docs/            status, test logs, knowledge base (start at docs/status.md)
```

## License

nullmoth's code is PolyForm Noncommercial 1.0.0 (personal and research use). This repo ships only scripts and diffs,
never binaries, so you build the kexts yourself.
