#!/usr/bin/env python3
"""Apply staged NMX source adjustments to NullMoth v2.7.2 NMIntelFB."""
from pathlib import Path
import sys

if len(sys.argv) not in (2, 3):
    raise SystemExit("usage: apply-2.7.2-port.py path/to/intelfb.cpp [early|kapi|agdc|k5]")

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
    IFBLOG("built-in panel published (%ux%u)", fWidth, fHeight);''',
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
elif mode == "k5":
    k5_header = "/*\n * NullMoth NVIDIA driver for macOS\n * Copyright (c) 2026 NullMoth Systems.\n * SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0\n */\n\n#ifndef NVRM_AGDC_K5_H\n#define NVRM_AGDC_K5_H\n#include <stdint.h>\n\n#define NVK5_CMD_LINKCONFIG   0x921u\n#define NVK5_CMD_FBCAPEX      0x711u\n#define NVK5_CAP_PLANESCALER  0x10u\n#define NVK5_TIMING_TAG       0x4b350001u\n#define NVK5_TIMING_WORDS     13\n\nenum { NVK5_T_TAG, NVK5_T_PCLK, NVK5_T_HVIS, NVK5_T_HSS, NVK5_T_HSE, NVK5_T_HTOT, NVK5_T_VVIS, NVK5_T_VSS, NVK5_T_VSE, NVK5_T_VTOT,\n       NVK5_T_REFRESH_MHZ, NVK5_T_HSYNCPOS, NVK5_T_VSYNCPOS };\n\n#pragma pack(push, 1)\nstruct NVAGDCTiming {\n    uint32_t hScaledInset, vScaledInset, scalerFlags, hScaled, vScaled, signalConfig, signalLevels;\n    uint64_t pixelClock, minPixelClock, maxPixelClock;\n    uint32_t hActive, hBlanking, hSyncOffset, hSyncPulseWidth;\n    uint32_t vActive, vBlanking, vSyncOffset, vSyncPulseWidth;\n    uint32_t hBorderLeft, hBorderRight, vBorderTop, vBorderBottom;\n    uint32_t hSyncConfig, hSyncLevel, vSyncConfig, vSyncLevel;\n    uint32_t numLinks, vBlankingExtension;\n    uint16_t pixelEncoding, bitsPerColorComponent, colorimetry, dynamicRange;\n    uint16_t dscBitsPerPixel, dscSliceHeight, dscSliceWidth, field8a;\n    uint8_t  tail[8];\n};\nstruct NVAGDCLinkConfig {\n    int32_t  id;\n    int32_t  groupID;\n    uint64_t flags;\n    struct NVAGDCTiming timing;\n    uint32_t port, stream;\n    uint32_t state;\n};\nstruct NVAGDCFBExtCap {\n    uint32_t fbIndex, type, count;\n    uint8_t  entry[8][0x32c];\n};\n#pragma pack(pop)\n_Static_assert(sizeof(struct NVAGDCTiming) == 0x94, \"AGDC timing is 0x94\");\n_Static_assert(sizeof(struct NVAGDCLinkConfig) == 0xb0, \"AGDCLinkConfig_t is 0xb0\");\n_Static_assert(__builtin_offsetof(struct NVAGDCLinkConfig, port) == 0xa4, \"stream address at +0xa4\");\n_Static_assert(sizeof(struct NVAGDCFBExtCap) == 0x196c, \"AGDCFBGetExtendedCapability_t is 0x196c\");\n\nstatic inline void nvk5_zero(void *p, unsigned long n) { uint8_t *b = (uint8_t *)p; while (n--) *b++ = 0; }\nstatic inline void nvk5_put32(uint8_t *e, unsigned off, uint32_t v) { e[off] = (uint8_t)v; e[off+1] = (uint8_t)(v >> 8); e[off+2] = (uint8_t)(v >> 16); e[off+3] = (uint8_t)(v >> 24); }\n\nstatic inline int nvk5_timing_bad(const uint32_t *t, unsigned long bytes)\n{\n    if (!t || bytes != NVK5_TIMING_WORDS * sizeof(uint32_t)) return 1;\n    if (t[NVK5_T_TAG] != NVK5_TIMING_TAG) return 2;\n    if (!t[NVK5_T_PCLK] || !t[NVK5_T_HVIS] || !t[NVK5_T_VVIS]) return 3;\n    if (!(t[NVK5_T_HVIS] <= t[NVK5_T_HSS] && t[NVK5_T_HSS] < t[NVK5_T_HSE] && t[NVK5_T_HSE] <= t[NVK5_T_HTOT])) return 4;\n    if (!(t[NVK5_T_VVIS] <= t[NVK5_T_VSS] && t[NVK5_T_VSS] < t[NVK5_T_VSE] && t[NVK5_T_VSE] <= t[NVK5_T_VTOT])) return 5;\n    if (t[NVK5_T_HTOT] == t[NVK5_T_HVIS] || t[NVK5_T_VTOT] == t[NVK5_T_VVIS]) return 6;\n    return 0;\n}\n\nstatic inline void nvk5_fill_link(struct NVAGDCLinkConfig *l, const uint32_t *t)\n{\n    int32_t id = l->id; nvk5_zero(l, sizeof *l); l->id = id;\n    l->groupID = -1;\n    l->flags = 0x8 | 0x1 | 0x2;\n    struct NVAGDCTiming *g = &l->timing;\n    g->pixelClock = g->minPixelClock = g->maxPixelClock = t[NVK5_T_PCLK];\n    g->hActive = t[NVK5_T_HVIS]; g->hBlanking = t[NVK5_T_HTOT] - t[NVK5_T_HVIS];\n    g->hSyncOffset = t[NVK5_T_HSS] - t[NVK5_T_HVIS]; g->hSyncPulseWidth = t[NVK5_T_HSE] - t[NVK5_T_HSS];\n    g->vActive = t[NVK5_T_VVIS]; g->vBlanking = t[NVK5_T_VTOT] - t[NVK5_T_VVIS];\n    g->vSyncOffset = t[NVK5_T_VSS] - t[NVK5_T_VVIS]; g->vSyncPulseWidth = t[NVK5_T_VSE] - t[NVK5_T_VSS];\n    g->hSyncConfig = t[NVK5_T_HSYNCPOS] ? 1 : 0; g->vSyncConfig = t[NVK5_T_VSYNCPOS] ? 1 : 0;\n    g->numLinks = 1;\n    g->pixelEncoding = 0x0001;\n    g->bitsPerColorComponent = 0x0002;\n    g->colorimetry = 0x0001;\n    g->dynamicRange = 0x0001;\n    l->port = 1; l->stream = 0;\n    l->state = 1;\n}\nstatic inline void nvk5_fill_link_port(struct NVAGDCLinkConfig *l, const uint32_t *t, uint32_t port)\n{\n    nvk5_fill_link(l, t); l->port = port;\n}\n\nstatic inline void nvk5_fill_planescaler(struct NVAGDCFBExtCap *c, const uint32_t *t)\n{\n    uint32_t idx = c->fbIndex, type = c->type; nvk5_zero(c, sizeof *c); c->fbIndex = idx; c->type = type;\n    c->count = 1;\n    uint8_t *e = c->entry[0]; uint32_t w = t[NVK5_T_HVIS], h = t[NVK5_T_VVIS];\n    nvk5_put32(e, 0x000, 0x80004);\n    nvk5_put32(e, 0x004, 0);\n    nvk5_put32(e, 0x01c, 1);\n    nvk5_put32(e, 0x024, h); nvk5_put32(e, 0x028, w); nvk5_put32(e, 0x02c, h); nvk5_put32(e, 0x030, w);\n    nvk5_put32(e, 0x034, 0x70007);\n    nvk5_put32(e, 0x038, 0);\n    nvk5_put32(e, 0x1a4, 1);\n    nvk5_put32(e, 0x1ac, h); nvk5_put32(e, 0x1b0, w); nvk5_put32(e, 0x1b4, h); nvk5_put32(e, 0x1b8, w);\n    nvk5_put32(e, 0x1bc, 0x70007);\n    nvk5_put32(e, 0x1c0, 0);\n}\n\n#define NVK5_R_UNSUPPORTED  0\n#define NVK5_R_LINK         1\n#define NVK5_R_CAPS         2\n#define NVK5_R_BADARG     (-1)\n#define NVK5_R_NOTFOUND   (-2)\nstruct nvk5_head { const uint32_t *t; unsigned long tBytes; };\nstatic inline int nvk5_answer_heads(unsigned cmd, const void *in, unsigned long inSize, void *out, unsigned long outSize,\n                                    const struct nvk5_head *h, unsigned nh, int *why, int32_t *idxOut)\n{\n    *idxOut = -1;\n    if (cmd != NVK5_CMD_LINKCONFIG && cmd != NVK5_CMD_FBCAPEX) return NVK5_R_UNSUPPORTED;\n    const int link = cmd == NVK5_CMD_LINKCONFIG;\n    const unsigned long want = link ? sizeof(struct NVAGDCLinkConfig) : sizeof(struct NVAGDCFBExtCap);\n    if (!out || outSize != want) { *why = link ? 0x10 : 0x20; return NVK5_R_BADARG; }\n    if (!in || inSize != want) { *why = link ? 0x12 : 0x22; return NVK5_R_BADARG; }\n    if (in != out) {\n        const uint8_t *s = (const uint8_t *)in; uint8_t *d = (uint8_t *)out; unsigned long n = want;\n        if (d < s) while (n--) *d++ = *s++; else while (n--) d[n] = s[n];\n    }\n    uint32_t idx = link ? (uint32_t)((struct NVAGDCLinkConfig *)out)->id : ((struct NVAGDCFBExtCap *)out)->fbIndex;\n    *idxOut = (int32_t)idx;\n    if (!link && ((struct NVAGDCFBExtCap *)out)->type != NVK5_CAP_PLANESCALER) return NVK5_R_UNSUPPORTED;\n    if (idx >= nh) { *why = link ? 0x11 : 0x21; return NVK5_R_BADARG; }\n    const uint32_t *t = h[idx].t;\n    int bad = t ? nvk5_timing_bad(t, h[idx].tBytes) : 0x31;\n    if (bad) { *why = bad; return NVK5_R_NOTFOUND; }\n    if (link) { nvk5_fill_link_port((struct NVAGDCLinkConfig *)out, t, 1u + idx); return NVK5_R_LINK; }\n    nvk5_fill_planescaler((struct NVAGDCFBExtCap *)out, t); return NVK5_R_CAPS;\n}\nstatic inline int nvk5_answer(unsigned cmd, const void *in, unsigned long inSize, void *out, unsigned long outSize,\n                              const uint32_t *t, unsigned long tBytes, int *why)\n{\n    struct nvk5_head h0 = { t, tBytes }; int32_t idx;\n    return nvk5_answer_heads(cmd, in, inSize, out, outSize, &h0, 1, why, &idx);\n}\n#endif\n"
    (root / "nvrm-agdc-k5.h").write_text(k5_header)
    replace_once(
'''#include "AppleGraphicsDeviceControl_re.h"
#define NVRM_GPUVA_ABI_VERSION 1u''',
'''#include "AppleGraphicsDeviceControl_re.h"
#include "nvrm-agdc-k5.h"
#define NVRM_GPUVA_ABI_VERSION 1u''',
        "include the AGDC link and plane-scaler ABI",
    )
    replace_once(
'''static IOService *gIfbNubFB = nullptr;
static void ifb_agdc_register(bool on);''',
'''static IOService *gIfbNubFB = nullptr;
static uint32_t gIfbK5[NVK5_TIMING_WORDS];
static void ifb_agdc_register(bool on);''',
        "NVRM timing state",
    )
    replace_once(
'''    ifb_trail("power");
    if (gIfbNubFB == this) ifb_agdc_register(true);
    IFBLOG("built-in panel published (%ux%u)", fWidth, fHeight);''',
'''    ifb_trail("power");
    if (gIfbNubFB == this) {
        const uint32_t k5[NVK5_TIMING_WORDS] = { NVK5_TIMING_TAG, (uint32_t)fPclk, fWidth, fHSS, fHSE, fHT, fHeight, fVSS, fVSE, fVT,
                                                 (uint32_t)(((uint64_t)fRefresh16 * 1000) >> 16), 1, 1 };
        memcpy(gIfbK5, k5, sizeof k5);
        if (OSData *d = OSData::withBytes(k5, sizeof k5)) { setProperty("NVRMTiming", d); d->release(); }
        int bad = nvk5_timing_bad(gIfbK5, sizeof gIfbK5);
        IFBLOG("K5 timing: pclk %u %ux%u h %u-%u/%u v %u-%u/%u %u mHz%s", k5[1], fWidth, fHeight, fHSS, fHSE, fHT, fVSS, fVSE, fVT,
               k5[10], bad ? " - REJECTED by nvk5_timing_bad" : "");
        ifb_agdc_register(true);
    }
    IFBLOG("built-in panel published (%ux%u)", fWidth, fHeight);''',
        "publish the Intel panel timing before AGDC registration",
    )
    replace_once(
'''        IFB_ONCE("agdc-980");
        return kIOReturnSuccess;
    }
    if (gIfbAgdcLogged < 20)''',
'''        IFB_ONCE("agdc-980");
        return kIOReturnSuccess;
    }
    if (cmd == NVK5_CMD_LINKCONFIG || cmd == NVK5_CMD_FBCAPEX) {
        int why = 0;
        int r = nvk5_answer(cmd, in, inSize, out, outSize ? *outSize : 0, gIfbK5, sizeof gIfbK5, &why);
        if (r == NVK5_R_LINK) { IFB_ONCE("k5-link"); return kIOReturnSuccess; }
        if (r == NVK5_R_CAPS) { IFB_ONCE("k5-caps"); return kIOReturnSuccess; }
        if (r != NVK5_R_UNSUPPORTED) {
            if (gIfbAgdcLogged < 20) { gIfbAgdcLogged++; IFBLOG("AGDC K5: command %#x not answered (why %#x)", cmd, why); }
            return r == NVK5_R_BADARG ? kIOReturnBadArgument : kIOReturnNotFound;
        }
    }
    if (gIfbAgdcLogged < 20)''',
        "answer AGDC link and plane-scaler queries",
    )
elif mode == "nvdisplay":
    replace_once(
'''#include "nvrm-agdc-k5.h"
#define NVRM_GPUVA_ABI_VERSION 1u
#define NVRM_GPUVA_FN_HANDLES  "nvRmHandles"
struct NVRMRmHandles { unsigned int version; void *kapiDevice; unsigned int hClient, hDevice, hSubDevice; };''',
'''#include "nvrm-agdc-k5.h"
#include "nvrm_gpuva_abi.h"''',
        "use the upstream protected display-pointer ABI header",
    )
    replace_once(
'''// The NVRMDisplay nubs NVRM publishes carry the NVKMS function table, the GPU id and RM's VA-to-physical lookup
// (what NVRMFB starts from). Ownership is not grabbed: it is for mode sets, and NVRMFB may still hold it.''',
'''// NVRM exposes the NVKMS function table and VA-to-physical lookup through nvDisplayPointers.
// The NVRMDisplay nub supplies only gpu-id; keep returned kernel pointers private, never in IORegistry.''',
        "document the protected pointer contract",
    )
    replace_once(
'''    OSNumber *k = OSDynamicCast(OSNumber, nub->getProperty("nvkms-kapi"));
    OSNumber *g = OSDynamicCast(OSNumber, nub->getProperty("gpu-id"));
    OSNumber *pv = OSDynamicCast(OSNumber, nub->getProperty("phys-for-va"));
    fKms = k ? (struct NvKmsKapiFunctionsTable *)(uintptr_t)k->unsigned64BitValue() : nullptr;
    fPhysForVa = pv ? (NvU64 (*)(const void *))(uintptr_t)pv->unsigned64BitValue() : nullptr;
    uint64_t bar = 0;
    IOService *rm = nub->getProvider();''',
'''    OSNumber *g = OSDynamicCast(OSNumber, nub->getProperty("gpu-id"));
    IOService *rm = nub->getProvider();
    struct NVRMDisplayPointers displayPtrs = {};
    displayPtrs.version = NVRM_DISPLAY_PTRS_ABI_VERSION;
    const OSSymbol *displayPtrsFn = OSSymbol::withCString(NVRM_DISPLAY_PTRS_FN);
    IOReturn displayPtrsResult = kIOReturnNotFound;
    if (rm && displayPtrsFn)
        displayPtrsResult = rm->callPlatformFunction(displayPtrsFn, false, &displayPtrs, NULL, NULL, NULL);
    if (displayPtrsFn) displayPtrsFn->release();
    fKms = displayPtrsResult == kIOReturnSuccess
        ? (struct NvKmsKapiFunctionsTable *)displayPtrs.kapi : nullptr;
    fPhysForVa = displayPtrsResult == kIOReturnSuccess
        ? (NvU64 (*)(const void *))displayPtrs.physForVa : nullptr;
    uint64_t bar = 0;''',
        "obtain NVKMS pointers through nvDisplayPointers",
    )
    replace_once(
'''        ifb_trail("kapi-none"); IFBLOG("kapi: nub lacks nvkms-kapi/gpu-id/phys-for-va or BAR1 (%llu)", bar); nub->release(); return;''',
'''        ifb_trail("kapi-none"); IFBLOG("kapi: nvDisplayPointers failed (0x%x), gpu-id or BAR1 missing (%llu)",
                                      (unsigned)displayPtrsResult, bar); nub->release(); return;''',
        "report protected pointer API failure",
    )
    replace_once(
'''        static const char *const kCopy[] = {"nvkms-kapi", "gpu-id", "phys-for-va"};''',
'''        // Kernel pointers are obtained from the NVRM provider through nvDisplayPointers; never publish them in IORegistry.
        static const char *const kCopy[] = {"gpu-id"};''',
        "stop copying kernel pointers into the synthetic display nub",
    )
else:
    raise SystemExit(f"unknown mode: {mode}")

path.write_text(source)
print(f"Applied the v2.7.2 NMX {mode} port: {path}")
