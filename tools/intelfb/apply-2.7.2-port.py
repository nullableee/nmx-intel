#!/usr/bin/env python3
"""Apply the NMX start-order and power-guard port to NullMoth v2.7.2 NMIntelFB."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply-2.7.2-port.py path/to/intelfb.cpp")

path = Path(sys.argv[1])
source = path.read_text()


def replace_once(old: str, new: str, label: str) -> None:
    global source
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"STOP: {label}: expected one exact upstream block, found {count}")
    source = source.replace(old, new, 1)


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
    } else IFBLOG("the surface would not map write-combined: NVIDIA rendering stays off for this panel");
    setProperty("NMIntelFBPipe", fPipe, 32);''',
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
    ifb_trail("fb-started");
    setProperty("NMIntelFBPipe", fPipe, 32);''',
"dependent-ID before IOFramebuffer::start",
)

replace_once(
'''    armVbl();
    ifb_trail("vbl");
    registerPowerDriver(this, kPowerStates, 2);
    ifb_trail("power");
    IFBLOG("built-in panel published (%ux%u)", fWidth, fHeight);''',
'''    armVbl();
    ifb_trail("vbl");
    // Some firmware/boards hang while registering power management; keep it disabled until target sleep testing.
    if (ifb_knob("nullmoth-intelfb-pm", 0)) {
        ifb_trail("pm");
        registerPowerDriver(this, kPowerStates, 2);
        ifb_trail("power");
    } else ifb_trail("no-pm");
    IFBLOG("built-in panel published (%ux%u)", fWidth, fHeight);''',
"guarded power registration",
)

path.write_text(source)
print(f"Applied 2.7.2 NMX start-order/power port: {path}")
