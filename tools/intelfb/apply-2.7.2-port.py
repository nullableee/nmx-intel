#!/usr/bin/env python3
"""Apply staged NMX source adjustments to NullMoth v2.7.2 NMIntelFB."""
from pathlib import Path
import sys

if len(sys.argv) not in (2, 3):
    raise SystemExit("usage: apply-2.7.2-port.py path/to/intelfb.cpp [early|kapi|agdc]")

path = Path(sys.argv[1])
mode = sys.argv[2] if len(sys.argv) == 3 else "early"
source = path.read_text()
root = path.parent


def replace_once(old: str, new: str, label: str) -> None:
    global source
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"STOP: {label}: expected one exact source block, found {count}")
    source = source.replace(old, new, 1)


if mode == "early":
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
    replace_once(
'''#include "nvrm_vram_abi.h"
#include <IOKit/IOBufferMemoryDescriptor.h>''',
'''#include "nvrm_vram_abi.h"
extern "C" {
#include "nvkms-kapi.h"
}
#define NVRM_GPUVA_ABI_VERSION 1u
#define NVRM_GPUVA_FN_HANDLES  "nvRmHandles"
struct NVRMRmHandles { unsigned int version; void *kapiDevice; unsigned int hClient, hDevice, hSubDevice; };
#include <IOKit/IOBufferMemoryDescriptor.h>''',
        "NVKMS KAPI and RM handles ABI declarations",
    )
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
elif mode == "agdc":
    header = "/*\n * NullMoth NVIDIA driver for macOS\n * Copyright (c) 2026 NullMoth Systems.\n * SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0\n */\n\n#pragma once\n#include <IOKit/IOService.h>\n#include <IOKit/IOUserClient.h>\nstruct AGDCClientState_t;\nstruct IOExternalMethodArguments;\nclass AppleGraphicsDeviceControl : public IOService {\n    OSDeclareDefaultStructors(AppleGraphicsDeviceControl)\n    uint8_t _agdc_private[0x110 - sizeof(IOService)];\npublic:\n    virtual bool     start(IOService *provider) APPLE_KEXT_OVERRIDE;\n    virtual void     stop(IOService *provider) APPLE_KEXT_OVERRIDE;\n    virtual IOReturn message(UInt32 type, IOService *provider, void *argument = 0) APPLE_KEXT_OVERRIDE;\n    virtual bool     terminate(IOOptionBits options = 0) APPLE_KEXT_OVERRIDE;\n    virtual IOReturn newUserClient(task_t owningTask, void *securityID, UInt32 type, OSDictionary *properties, IOUserClient **handler) APPLE_KEXT_OVERRIDE;\n    virtual IOReturn vendor_doDeviceAttribute(unsigned int cmd, unsigned long *in, unsigned long inSize,\n                                              unsigned long *out, unsigned long *outSize, IOExternalMethodArguments *args) = 0;\n    virtual IOReturn vendor_doDeviceAttribute(unsigned int cmd, unsigned long *in, unsigned long inSize,\n                                              unsigned long *out, unsigned long *outSize, AGDCClientState_t *state);\n    virtual void _RESERVEDAppleGraphicsDeviceControl0(); virtual void _RESERVEDAppleGraphicsDeviceControl1();\n    virtual void _RESERVEDAppleGraphicsDeviceControl2(); virtual void _RESERVEDAppleGraphicsDeviceControl3();\n    virtual void _RESERVEDAppleGraphicsDeviceControl4(); virtual void _RESERVEDAppleGraphicsDeviceControl5();\n    virtual void _RESERVEDAppleGraphicsDeviceControl6(); virtual void _RESERVEDAppleGraphicsDeviceControl7();\n};\nstatic_assert(sizeof(AppleGraphicsDeviceControl) == 0x110, \"AppleGraphicsDeviceControl is 0x110 bytes in 15.7.9\");\n"
    agdc = "}\n\n// intelfb-0014. WindowServer builds one display pipe per framebuffer that the GPU's AppleGraphicsDeviceControl lists\n// in its reply to command 0x980 (nullmoth's NVRMAGDC); without an AGDC, IOPresentment logged \"Unable to get AGDC\n// information ... Unable to acquire map\" and CoreDisplay \"System set to use IOP but no display pipes are present\"\n// (RTX-12, with the panel already under the NVIDIA GPU). NVRMAGDC lists only NVRMFB framebuffers, so this one lists\n// the panel: vendor info (1) and the framebuffer table (0x980), as NVRMAGDC answers them. Started by sysctl\n// debug.nmintelfb_agdc=1 (tools/intelfb/enable.sh), in the order NVRM's auto-go uses: accelerator, AGDC, iop.\n#pragma pack(push, 1)\nstruct IfbAgdcVendorInfo { uint32_t version; char vendor[0x20]; uint32_t vendorID, vendorClass; };\nstruct IfbAgdcGPUCapability {\n    uint64_t portMask, portFeatureA, portFeatureB, portFeatureC;\n    uint32_t countA, countB, countC, countD, maxFramebuffers;\n    IOService *pciDevice;\n    IOService *framebuffer[20];\n};\n#pragma pack(pop)\nstatic_assert(sizeof(IfbAgdcVendorInfo) == 0x2c, \"AGDCVendorInfo_t is 0x2c\");\nstatic_assert(sizeof(IfbAgdcGPUCapability) == 0xdc, \"AGDCGPUCapability_t is 0xdc\");\n\nclass NMIntelFBAGDC : public AppleGraphicsDeviceControl {\n    OSDeclareDefaultStructors(NMIntelFBAGDC)\npublic:\n    IOService *fPci = nullptr, *fFB = nullptr;\n    using AppleGraphicsDeviceControl::vendor_doDeviceAttribute;\n    IOReturn vendor_doDeviceAttribute(unsigned int cmd, unsigned long *in, unsigned long inSize, unsigned long *out,\n                                      unsigned long *outSize, IOExternalMethodArguments *args) override;\n};\nOSDefineMetaClassAndStructors(NMIntelFBAGDC, AppleGraphicsDeviceControl)\n\nstatic int gIfbAgdcState = 0;   // 0 off, 2 starting, 1 up, < 0 failed\nstatic unsigned gIfbAgdcLogged = 0;\n\nIOReturn NMIntelFBAGDC::vendor_doDeviceAttribute(unsigned int cmd, unsigned long *in, unsigned long inSize,\n                                                 unsigned long *out, unsigned long *outSize, IOExternalMethodArguments *)\n{\n    if (cmd == 1) {\n        if (!out || !outSize || *outSize != sizeof(IfbAgdcVendorInfo)) return kIOReturnBadArgument;\n        IfbAgdcVendorInfo *v = (IfbAgdcVendorInfo *)out; bzero(v, sizeof *v);\n        v->version = 0x30000; strlcpy(v->vendor, \"NVIDIA\", sizeof v->vendor); v->vendorID = 0x10de; v->vendorClass = 2;\n        return kIOReturnSuccess;\n    }\n    if (cmd == 0x980) {\n        if (!out || !outSize || *outSize != sizeof(IfbAgdcGPUCapability)) return kIOReturnBadArgument;\n        IfbAgdcGPUCapability *c = (IfbAgdcGPUCapability *)out; bzero(c, sizeof *c);\n        c->portMask = 1ull << 1;\n        c->countA = c->countB = c->countC = c->countD = 1;\n        c->maxFramebuffers = 1; c->pciDevice = fPci; c->framebuffer[0] = fFB;\n        IFB_ONCE(\"agdc-980\");\n        return kIOReturnSuccess;\n    }\n    if (gIfbAgdcLogged < 20) { gIfbAgdcLogged++; IFBLOG(\"AGDC: command %#x (in %lu bytes) -> Unsupported\", cmd, inSize); }\n    return kIOReturnUnsupported;\n}\n\nstatic void ifb_agdc_up(void *, wait_result_t)\n{\n    IOService *fb = gIfbNubFB, *pci = fb ? fb->getProvider() : nullptr;\n    for (int hops = 0; pci && !OSDynamicCast(IOPCIDevice, pci) && hops < 8; hops++) pci = pci->getProvider();\n    NMIntelFBAGDC *d = (fb && OSDynamicCast(IOPCIDevice, pci)) ? OSTypeAlloc(NMIntelFBAGDC) : nullptr;\n    int st = !d ? -1 : !d->init(nullptr) ? -2 : 0;\n    if (!st) {\n        d->fPci = pci; d->fFB = fb;\n        if (!d->attach(pci)) st = -3;\n        else if (!d->start(pci)) { d->detach(pci); st = -4; }\n        else st = 1;\n    }\n    if (st != 1) OSSafeReleaseNULL(d);   // an AGDC that came up stays until the next boot\n    gIfbAgdcState = st;\n    ifb_trail(st == 1 ? \"agdc\" : \"agdc-fail\");\n    IFBLOG(\"AGDC: %s (state %d) on %s\", st == 1 ? \"UP\" : \"not started\", st, pci ? pci->getName() : \"no NVIDIA PCI device\");\n    thread_terminate(current_thread());\n}\n\nstatic int ifb_agdc_sysctl SYSCTL_HANDLER_ARGS\n{\n    int v = gIfbAgdcState, err = sysctl_handle_int(oidp, &v, 0, req);\n    if (err || !req->newptr) return err;\n    if (v != 1) return EINVAL;\n    if (gIfbAgdcState == 1 || gIfbAgdcState == 2) return 0;\n    if (!gIfbNubFB) return ENXIO;\n    gIfbAgdcState = 2;\n    thread_t t = nullptr;\n    if (kernel_thread_start(ifb_agdc_up, nullptr, &t) != KERN_SUCCESS) { gIfbAgdcState = -5; return ENOMEM; }\n    thread_deallocate(t);\n    return 0;\n}\nSYSCTL_PROC(_debug, OID_AUTO, nmintelfb_agdc, CTLTYPE_INT | CTLFLAG_RW | CTLFLAG_LOCKED | CTLFLAG_KERN, nullptr, 0,\n            ifb_agdc_sysctl, \"I\", \"1 = list the Intel panel in an AppleGraphicsDeviceControl on the NVIDIA GPU (1 up, 2 starting, < 0 failed)\");\nstatic void ifb_agdc_register(bool on)\n{\n    if (on) sysctl_register_oid(&sysctl__debug_nmintelfb_agdc); else sysctl_unregister_oid(&sysctl__debug_nmintelfb_agdc);\n"
    (root / "AppleGraphicsDeviceControl_re.h").write_text(header)
    replace_once(
'''#include "nvkms-kapi.h"
}
#define NVRM_GPUVA_ABI_VERSION 1u''',
'''#include "nvkms-kapi.h"
}
#include "AppleGraphicsDeviceControl_re.h"
#define NVRM_GPUVA_ABI_VERSION 1u''',
        "AppleGraphicsDeviceControl header include",
    )
    replace_once(
'''static IOPCIDevice *gIfbPCI = nullptr;
static bool ifb_pci_ok(IOPCIDevice *pci, uint8_t *ver);''',
'''static IOPCIDevice *gIfbPCI = nullptr;
static IOService *gIfbNubFB = nullptr;
static void ifb_agdc_register(bool on);
static bool ifb_pci_ok(IOPCIDevice *pci, uint8_t *ver);''',
        "AGDC framebuffer state",
    )
    replace_once(
'''    if (!fPCI) fPCI = gIfbPCI;   // intelfb-0013: under NVRM, the Intel GPU the claim holds''',
'''    if (!fPCI) { fPCI = gIfbPCI; gIfbNubFB = this; }   // intelfb-0013: under NVRM, the Intel GPU the claim holds''',
        "remember the framebuffer published under NVRM",
    )
    replace_once(
'''    fPwmPeriod = 0;
    kapiFree();''',
'''    fPwmPeriod = 0;
    if (gIfbNubFB == this) { ifb_agdc_register(false); gIfbNubFB = nullptr; }
    kapiFree();''',
        "unregister AGDC when the synthetic framebuffer stops",
    )
    replace_once(
'''    ifb_trail("power");
    if (gIfbNubFB == this) ifb_agdc_register(true);
    IFBLOG("built-in panel published (%ux%u)", fWidth, fHeight);''',
        "register the synthetic Intel panel with AGDC",
    )
    replace_once(
'''    thread_terminate(current_thread());
}

#ifdef NMINTELFB_VIRTUAL''',
'''    thread_terminate(current_thread());
}
''' + agdc + '''}

#ifdef NMINTELFB_VIRTUAL''',
        "append the NMX AGDC implementation",
    )
    plist = root / "Info.plist"
    info = plist.read_text()
    key = '<key>com.apple.iokit.IOGraphicsFamily</key><string>1.0.0</string>'
    if "com.apple.AppleGraphicsDeviceControl" not in info:
        if info.count(key) != 1:
            raise SystemExit("STOP: Info.plist graphics dependency anchor not found exactly once")
        info = info.replace(key, key + '\n    <key>com.apple.AppleGraphicsDeviceControl</key><string>1.0.0</string>', 1)
        plist.write_text(info)
else:
    raise SystemExit(f"unknown mode: {mode}")

path.write_text(source)
print(f"Applied the v2.7.2 NMX {mode} port: {path}")
