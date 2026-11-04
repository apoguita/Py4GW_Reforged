// Py4GW native dialog host — the "owner" every control-hosting Guild Wars window has
// and Py4GW never did.
//
// Recovered by decompiling Gw.wasm (2026-05-20, sha256 F023FD91…) for two independent
// dialogs; see docs/ui/research/native-dialog-host-owner-contract.md for the evidence.
//
// Contract reproduced from the engine's own TCtlInstance<T>::MsgProc:
//   * FrameProc signature is void __cdecl(uint32_t* msg, void* wparam, void* lparam)
//   * msg[0] = frameId, msg[1] = msgId, msg[2] (byte +0x08) = the param slot
//   * on create the engine passes param pointing at a (possibly null) slot; the owner
//     allocates its instance, stores it through *param, and later reaches it the same way
//   * the instance is 0xD4 bytes: vtable +0x00, frameId +0x04, embedded CCtlLayout +0x08
//   * after the content builder runs, the owner requests the size pass with
//     FrameScheduleSize + FrameNativeSizeChanged (a CRect op on frame+0xD0)
//   * size messages reach the embedded layout through CCtlLayout::Size / SizeQuery
//   * teardown destroys the instance and chains the message to the base proc
//
// UNRESOLVED — do not pretend otherwise:
//   * the numeric message ids for the size / notify / destroy arms were recovered as
//     switch case indices, not ids. The constants below are the ids used elsewhere in
//     Py4GW and MUST be validated against a live client.
//   * the allocator: the engine uses MemAlloc(size, 0, file, line). Py4GW has its own
//     allocator path; whichever is used, the matching free must be used on teardown.

#pragma once

#include <cstddef>
#include <cstdint>

namespace Py4GW::Ui::DialogHost {

// ---------------------------------------------------------------------------
// Message ids (see UNRESOLVED above).
// ---------------------------------------------------------------------------
inline constexpr uint32_t kMsgCreate = 0x09;
inline constexpr uint32_t kMsgSize = 0x37;
inline constexpr uint32_t kMsgSizeQuery = 0x38;
inline constexpr uint32_t kMsgDestroy = 0x0b;

// ---------------------------------------------------------------------------
// Resolved natives. Fill these from the pattern table at startup; a null entry
// disables the feature that needs it rather than crashing.
// ---------------------------------------------------------------------------

using FrameMsgCallBaseFn = void(__cdecl*)(uint32_t* msg, void* wparam, void* lparam);
using FrameScheduleSizeFn = void(__cdecl*)(uint32_t frame_id);
using FrameNativeSizeChangedFn = void(__cdecl*)(uint32_t frame_id);
using FrameCloseFn = void(__cdecl*)(uint32_t frame_id);
using MemAllocFn = void*(__cdecl*)(size_t size, uint32_t flags, const char* file, int line);
using MemFreeFn = void(__cdecl*)(void* ptr);

// CCtlLayout is __thiscall: `this` is the embedded layout buffer.
using CtlLayoutCtorFn = void*(__thiscall*)(void* self);
using CtlLayoutSetFrameIdFn = void(__thiscall*)(void* self, uint32_t frame_id);
using CtlLayoutClearFn = void(__thiscall*)(void* self);
using CtlLayoutChildFn = void(__thiscall*)(void* self, uint32_t child_id, int h, int v, int expand);
using CtlLayoutRowFn = void(__thiscall*)(void* self, int h, int v, int expand);
using CtlLayoutColumnFn = void(__thiscall*)(void* self, int h, int v, int expand);
using CtlLayoutGapFn = void(__thiscall*)(void* self, float gap, int h, int v);
using CtlLayoutEndFn = void(__thiscall*)(void* self);
using CtlLayoutSizeFn = void(__thiscall*)(void* self, void* rect4f);
using CtlLayoutSizeQueryFn = void(__thiscall*)(void* self, const void* coord2f);

struct Natives {
    FrameMsgCallBaseFn frame_msg_call_base = nullptr;
    FrameScheduleSizeFn frame_schedule_size = nullptr;
    FrameNativeSizeChangedFn frame_native_size_changed = nullptr;
    FrameCloseFn frame_close = nullptr;
    MemAllocFn mem_alloc = nullptr;
    MemFreeFn mem_free = nullptr;

    CtlLayoutCtorFn ctl_layout_ctor = nullptr;
    CtlLayoutSetFrameIdFn ctl_layout_set_frame_id = nullptr;
    CtlLayoutClearFn ctl_layout_clear = nullptr;
    CtlLayoutChildFn ctl_layout_child = nullptr;
    CtlLayoutRowFn ctl_layout_row = nullptr;
    CtlLayoutColumnFn ctl_layout_column = nullptr;
    CtlLayoutGapFn ctl_layout_gap = nullptr;
    CtlLayoutEndFn ctl_layout_end = nullptr;
    CtlLayoutSizeFn ctl_layout_size = nullptr;
    CtlLayoutSizeQueryFn ctl_layout_size_query = nullptr;
};

inline Natives g_natives{};

// True when every native this host cannot work without is present.
inline bool Ready() {
    return g_natives.frame_msg_call_base != nullptr
        && g_natives.frame_schedule_size != nullptr
        && g_natives.frame_native_size_changed != nullptr
        && g_natives.ctl_layout_ctor != nullptr
        && g_natives.ctl_layout_set_frame_id != nullptr
        && g_natives.ctl_layout_clear != nullptr
        && g_natives.ctl_layout_end != nullptr
        && g_natives.ctl_layout_size != nullptr
        && g_natives.ctl_layout_size_query != nullptr;
}

// ---------------------------------------------------------------------------
// Instance layout — verified against the engine's MemAlloc(0xd4) + ctor sequence.
// ---------------------------------------------------------------------------

inline constexpr uint32_t kInstanceSize = 0xD4;
inline constexpr uint32_t kLayoutOffset = 0x08;

struct Instance {
    void* vtable;          // +0x00  engine identity slot; ours stays null
    uint32_t frame_id;     // +0x04
    uint8_t layout[0x18];  // +0x08  embedded CCtlLayout
    uint8_t reserved[kInstanceSize - 0x20];
};

static_assert(sizeof(Instance) == kInstanceSize, "instance size must match the engine's 0xD4");
static_assert(offsetof(Instance, layout) == kLayoutOffset, "layout must sit at instance+8");

// ---------------------------------------------------------------------------
// Host registry. These are windows, not per-tick objects, so a fixed table is enough.
// ---------------------------------------------------------------------------

using ContentCreateFn = void(__cdecl*)(uint32_t frame_id, Instance* instance, void* user);
using ContentLayoutFn = void(__cdecl*)(Instance* instance, void* ctl_layout, void* user);

struct HostConfig {
    bool in_use = false;
    uint32_t frame_id = 0;
    ContentCreateFn build_content = nullptr;
    ContentLayoutFn build_layout = nullptr;
    void* user = nullptr;
};

inline constexpr uint32_t kMaxHosts = 16;
inline HostConfig g_hosts[kMaxHosts]{};

inline HostConfig* FindHost(uint32_t frame_id) {
    for (uint32_t i = 0; i < kMaxHosts; ++i) {
        if (g_hosts[i].in_use && g_hosts[i].frame_id == frame_id) {
            return &g_hosts[i];
        }
    }
    return nullptr;
}

inline HostConfig* ReserveHost(uint32_t frame_id) {
    HostConfig* existing = FindHost(frame_id);
    if (existing) {
        return existing;
    }
    for (uint32_t i = 0; i < kMaxHosts; ++i) {
        if (!g_hosts[i].in_use) {
            g_hosts[i] = HostConfig{};
            g_hosts[i].in_use = true;
            g_hosts[i].frame_id = frame_id;
            return &g_hosts[i];
        }
    }
    return nullptr;
}

// Call this from the config's build_content after the frame is created and the
// content class has been pointed at it.
inline void SetContentCallbacks(uint32_t frame_id, ContentCreateFn create, ContentLayoutFn layout, void* user) {
    HostConfig* cfg = ReserveHost(frame_id);
    if (!cfg) {
        return;
    }
    cfg->build_content = create;
    cfg->build_layout = layout;
    cfg->user = user;
}

// ---------------------------------------------------------------------------
// The dispatcher. File scope + __cdecl so its address is a plain proc pointer, which
// is what FrameCreate's 4th argument expects.
// ---------------------------------------------------------------------------

inline Instance* InstanceFrom(uint32_t* msg) {
    // msg[2] is the param slot; the instance hangs off one dereference, exactly as the
    // engine's own TCtlInstance<T>::Ptr does.
    uint32_t* slot = reinterpret_cast<uint32_t*>(msg[2]);
    if (!slot) {
        return nullptr;
    }
    return reinterpret_cast<Instance*>(*slot);
}

inline void CreateInstance(uint32_t* msg) {
    uint32_t* slot = reinterpret_cast<uint32_t*>(msg[2]);
    if (!slot || *slot != 0) {
        return;  // already owned
    }
    if (!g_natives.mem_alloc) {
        return;
    }
    auto* instance = static_cast<Instance*>(
        g_natives.mem_alloc(kInstanceSize, 0, "Py4GW/native_dialog_host", 0));
    if (!instance) {
        return;
    }
    instance->vtable = nullptr;
    instance->frame_id = msg[0];

    // The embedded layout must be constructed by the engine's own ctor; Ui::CLayout::Size
    // and friends assume it.
    if (g_natives.ctl_layout_ctor) {
        g_natives.ctl_layout_ctor(instance->layout);
    }
    if (g_natives.ctl_layout_set_frame_id) {
        g_natives.ctl_layout_set_frame_id(instance->layout, instance->frame_id);
    }

    *slot = reinterpret_cast<uint32_t>(instance);

    HostConfig* cfg = FindHost(instance->frame_id);
    if (cfg && cfg->build_content) {
        cfg->build_content(instance->frame_id, instance, cfg->user);
    }

    // Clear the built tree, then request the size pass. Both halves are required:
    // without the schedule call the engine never measures, without the native-size
    // notify direct children keep their stale rects.
    if (g_natives.ctl_layout_clear) {
        g_natives.ctl_layout_clear(instance->layout);
    }
    if (g_natives.frame_schedule_size) {
        g_natives.frame_schedule_size(instance->frame_id);
    }
    if (g_natives.frame_native_size_changed) {
        g_natives.frame_native_size_changed(instance->frame_id);
    }
}

inline void DestroyInstance(uint32_t* msg) {
    Instance* instance = InstanceFrom(msg);
    if (!instance) {
        return;
    }
    uint32_t* slot = reinterpret_cast<uint32_t*>(msg[2]);
    if (slot) {
        *slot = 0;
    }
    HostConfig* cfg = FindHost(instance->frame_id);
    if (cfg) {
        cfg->in_use = false;
        cfg->frame_id = 0;
        cfg->build_content = nullptr;
        cfg->build_layout = nullptr;
        cfg->user = nullptr;
    }
    if (g_natives.mem_free) {
        g_natives.mem_free(instance);
    }
}

inline void __cdecl HostProc(uint32_t* msg, void* wparam, void* lparam) {
    if (!msg) {
        return;
    }
    const uint32_t msg_id = msg[1];

    if (msg_id == kMsgCreate) {
        CreateInstance(msg);
    }
    else if (!Ready()) {
        // Nothing we can safely do; let the base chain handle it.
    }
    else if (msg_id == kMsgSize) {
        Instance* instance = InstanceFrom(msg);
        if (instance && wparam) {
            g_natives.ctl_layout_size(instance->layout, wparam);
        }
    }
    else if (msg_id == kMsgSizeQuery) {
        Instance* instance = InstanceFrom(msg);
        if (instance && lparam) {
            g_natives.ctl_layout_size_query(instance->layout, lparam);
        }
    }
    else if (msg_id == kMsgDestroy) {
        DestroyInstance(msg);
    }

    if (g_natives.frame_msg_call_base) {
        g_natives.frame_msg_call_base(msg, wparam, lparam);
    }
}

}  // namespace Py4GW::Ui::DialogHost
