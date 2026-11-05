#!/usr/bin/env python3
"""Apply staged NMX source adjustments to NullMoth v2.7.2 NMIntelFB."""
from pathlib import Path
import sys

if len(sys.argv) not in (2, 3):
    raise SystemExit("usage: apply-2.7.2-port.py path/to/intelfb.cpp [early|kapi]")

path = Path(sys.argv[1])
mode = sys.argv[2] if len(sys.argv) == 3 else "early"
source = path.read_text()


def replace_once(old: str, new: str, label: str) -> None:
    global source
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"STOP: {label}: expected one exact source block, found {count}")
    source = source.replace(old, new, 1)


if mode == "early":
    # Replacement for intelfb-0003. Patches 0009 and 0012 refine this code later.
    replace_once(
'''    IOReturn setPowerState(unsigned long ordinal, IOService *) override {
        handleEvent(ordinal ? kIOFBNotifyDidPowerOn : kIOFBNotifyWillPowerOff);
        return kIOPMAckImplied;
    }''',
'''    IOReturn setPowerState(unsigned long ordinal, IOService *) override {
        ifb_trail(ordinal ? "sp1" : "sp0");
        handleEvent(ordinal ? kIOFBNotifyDidPowerOn : kIOFBNotifyWillPowerOff);
        ifb_trail("sp-done");
        return kIOPMAckImplied;
    }''',
        "setPowerState trace",
    )

    replace_once(
'''    publishBacklight();   // before IOFramebuffer::start: IOFramebuffer::open looks for a service named "backlight"
    if (!IOFramebuffer::start(provider)) {
        ifb_trail("fb-start-failed");
        if (fBacklight) { fBacklight->detach(this); OSSafeReleaseNULL(fBacklight); }
        OSSafeReleaseNULL(fMMIO); fRegs = nullptr; return false;
    }
    ifb_trail("fb-started");
    // Head 4 of the NVIDIA accelerator (NVAccel): WindowServer composites this panel on the NVIDIA card and the
    // display pipe copies each frame into fSurfMap. Without NVAccel the panel stays a plain framebuffer.
    if (IODeviceMemory *sm = IODeviceMemory::withRange(fApertureBase + fSurf, (IOPhysicalLength)fRowBytes * fHeight)) {
        fSurfMap = sm->map(kIOMapWriteCombineCache); sm->release();
    }
    if (fSurfMap) {
        setProperty("IOFBDependentID", 0x4E56524D00000001ull, 64);
        setProperty("IOFBDependentIndex", 4ull, 32);
    } else IFBLOG("the surface would not map write-combined: NVIDIA rendering stays off for this panel");''',
'''    publishBacklight();   // before IOFramebuffer::start: IOFramebuffer::open looks for a service named "backlight"
    // Head 4 of the NVIDIA accelerator (NVAccel): WindowServer composites this panel on the NVIDIA card and the
    // display pipe copies each frame into fSurfMap. Without NVAccel the panel stays a plain framebuffer.
    if (IODeviceMemory *sm = IODeviceMemory::withRange(fApertureBase + fSurf, (IOPhysicalLength)fRowBytes * fHeight)) {
        fSurfMap = sm->map(kIOMapWriteCombineCache); sm->release();
    }
    ifb_trail(fSurfMap ? "surf" : "surf-fail");
    // The dependent ID selects the controller IOFramebuffer::start builds, so publish it before start().
    if (fSurfMap && ifb_knob("nullmoth-intelfb-dep", 1)) {
        setProperty("IOFBDependentID", 0x4E56524D00000001ull, 64);
        setProperty("IOFBDependentIndex", 4ull, 32);
        ifb_trail("dep");
    } else IFBLOG("the surface would not map write-combined, or nullmoth-intelfb-dep=0: NVIDIA rendering stays off for this panel");
    if (!IOFramebuffer::start(provider)) {
        ifb_trail("fb-start-failed");
        if (fBacklight) { fBacklight->detach(this); OSSafeReleaseNULL(fBacklight); }
        OSSafeReleaseNULL(fSurfMap); OSSafeReleaseNULL(fMMIO); fRegs = nullptr; return false;
    }
    ifb_trail("fb-started");''',
        "dependent-ID before IOFramebuffer::start",
    )
elif mode == "kapi":
    # Patch 0011 adds kapiInit(); insert its call before patch 0012 refines the VBL/power block.
    replace_once(
'''    armVbl();
    ifb_trail("vbl");
    registerPowerDriver(this, kPowerStates, 2);''',
'''    armVbl();
    ifb_trail("vbl");
    if (fOwnGroup && ifb_knob("nullmoth-intelfb-head", 0) != 4) kapiInit();
    registerPowerDriver(this, kPowerStates, 2);''',
        "initialize the primary NVKMS device after VBL startup",
    )
else:
    raise SystemExit(f"unknown mode: {mode}")

path.write_text(source)
print(f"Applied the v2.7.2 NMX {mode} port: {path}")
