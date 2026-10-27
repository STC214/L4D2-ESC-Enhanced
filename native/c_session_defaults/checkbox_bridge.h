#pragma once
#include <windows.h>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include "local_cvars.h"

// Exact inspected GameUI x86 profile. No game file, CVar flag, or arbitrary
// option dialog is changed. Only our uniquely named ten controls auto-commit.
namespace CheckboxBridge {
using Logger = void (*)(const char*);
using Handler = void (__thiscall*)(void*);
using Slot = int (__cdecl*)();
inline Logger logger = nullptr;
inline unsigned char* module = nullptr;
inline unsigned char* trampoline = nullptr;
inline DWORD owner_thread = 0;
inline bool in_commit = false;
inline constexpr std::size_t EventRva = 0x4550;
inline constexpr unsigned char Prefix[] = {0x56, 0x8b, 0xf1, 0x8b, 0x06};
inline constexpr const char* Names[] = {
    "mat_monitorgamma_tv_enabled", "closecaption", "gameinstructor_enable",
    "sv_disable_glow_survivors", "sv_disable_glow_faritems", "director_show_intensity",
    "mat_fullbright", "nav_edit", "fog_override", "fog_enable"
};
using Clock = ULONGLONG (WINAPI*)();
inline Clock clock = GetTickCount64;
struct Pending {
    CvarPrefix* var = nullptr; // stable CVar parent only, NEVER a UI Panel
    int wanted = 0, flags = 0;
    ULONGLONG earliest = 0, deadline = 0;
};
inline std::array<std::array<Pending, 4>, std::size(Names)> pending{};

inline bool Readable(const void* pointer, std::size_t length) {
    auto at = reinterpret_cast<std::uintptr_t>(pointer);
    if (!at || length > UINTPTR_MAX - at) return false;
    const auto end = at + length;
    while (at < end) {
        MEMORY_BASIC_INFORMATION info{};
        if (!VirtualQuery(reinterpret_cast<void*>(at), &info, sizeof(info)) ||
            info.State != MEM_COMMIT || (info.Protect & (PAGE_GUARD | PAGE_NOACCESS))) return false;
        const DWORD access = info.Protect & 0xff;
        if (access != PAGE_READONLY && access != PAGE_READWRITE && access != PAGE_WRITECOPY &&
            access != PAGE_EXECUTE_READ && access != PAGE_EXECUTE_READWRITE && access != PAGE_EXECUTE_WRITECOPY) return false;
        const auto next = reinterpret_cast<std::uintptr_t>(info.BaseAddress) + info.RegionSize;
        if (next <= at) return false;
        at = next;
    }
    return true;
}

inline bool Equal(const char* actual, const char* expected) {
    const auto count = std::strlen(expected) + 1;
    return Readable(actual, count) && std::memcmp(actual, expected, count) == 0;
}

inline const char* OwnedBinding(void* object, int slot) {
    auto self = static_cast<unsigned char*>(object);
    if (slot < 0 || slot > 3 || !Readable(self, 0x244) ||
        *reinterpret_cast<void**>(self) != module + 0x15f674) return nullptr;
    // Panel::ApplySettings assigns fieldName to its CUtlString at +0x4c.
    const char* field = *reinterpret_cast<const char**>(self + 0x4c);
    auto var = *reinterpret_cast<CvarPrefix**>(self + 0x224 + slot * 8);
    if (!Readable(var, sizeof(CvarPrefix))) return nullptr;
    for (const char* name : Names) {
        char expected[128]{};
        std::snprintf(expected, sizeof(expected), "C_ESC_BOOL_%s", name);
        if (Equal(field, expected) && Equal(var->base.name, name)) return name;
    }
    return nullptr;
}

inline void PollPending() {
    if (!trampoline || GetCurrentThreadId() != owner_thread) return;
    const auto now = clock();
    for (std::size_t index = 0; index < std::size(Names); ++index) {
        for (auto& item : pending[index]) {
            if (!item.var || now < item.earliest) continue;
            const bool valid = Readable(item.var, sizeof(CvarPrefix)) && Equal(item.var->base.name, Names[index]);
            const int actual = valid ? item.var->int_value : -1;
            const bool flags_ok = valid && item.var->base.flags == item.flags;
            const bool accepted = flags_ok && actual == item.wanted;
            if (!accepted && valid && flags_ok && now < item.deadline) continue;
            char message[220]{};
            std::snprintf(message, sizeof(message), "%s: %s requested=%d actual=%d; flags unchanged=%d; deferred=1",
                          accepted ? "CHECKBOX_COMMIT_VERIFIED" : "CHECKBOX_COMMIT_TIMEOUT", Names[index],
                          item.wanted, actual, flags_ok ? 1 : 0);
            if (logger) logger(message);
            item = {};
            // No retry/lock and no stale UI pointer: native Paint synchronizes
            // a rejected/overridden value, even if the ESC panel was destroyed.
        }
    }
}

inline void __fastcall Checked(void* object, void*) {
    // Preserve native ControlModified signalling for all other property pages.
    reinterpret_cast<Handler>(trampoline)(object);
    if (in_commit || GetCurrentThreadId() != owner_thread) return;
    const int slot = reinterpret_cast<Slot>(module + 0x87a30)();
    const char* name = OwnedBinding(object, slot);
    if (!name) return;
    auto self = static_cast<unsigned char*>(object);
    auto var = *reinterpret_cast<CvarPrefix**>(self + 0x224 + slot * 8);
    using Selected = bool (__thiscall*)(void*);
    auto table = *reinterpret_cast<void***>(self);
    const bool wanted = reinterpret_cast<Selected>(table[0x400 / 4])(object);
    std::size_t index = 0;
    while (index < std::size(Names) && Names[index] != name) ++index;
    if (index == std::size(Names)) return;
    auto& item = pending[index][slot];
    if (item.var && item.var != var) item = {}; // a rebuilt binding is a new request context
    // Native Paint refreshes both selection and m_bStartValue; a genuine
    // user toggle changes selection while the start value is still old.
    const bool start = self[0x240] != 0;
    const bool cancelling_queued = item.var && item.wanted != (wanted ? 1 : 0) && start != wanted;
    // Creation/refresh messages must not rewrite manual/default values.
    if ((var->int_value != 0) == wanted && !cancelling_queued) return;
    if (item.var && !cancelling_queued) return; // same pending request: no duplicate write
    const int flags = var->base.flags;
    in_commit = true;
    reinterpret_cast<Handler>(module + 0x4500)(object); // native ApplyChanges
    const bool accepted = (var->int_value == (wanted ? 1 : 0)) && var->base.flags == flags;
    const bool flags_ok = var->base.flags == flags;
    if (!flags_ok) reinterpret_cast<Handler>(module + 0x4320)(object); // definite immediate failure
    in_commit = false;
    if (flags_ok && (!accepted || cancelling_queued)) {
        const auto now = clock();
        item = {var, wanted ? 1 : 0, flags, now + 100, now + 1000};
        char message[200]{};
        std::snprintf(message, sizeof(message), "CHECKBOX_COMMIT_PENDING: %s requested=%d actual=%d; flags unchanged=1",
                      name, wanted ? 1 : 0, var->int_value);
        if (logger) logger(message);
        return; // material-system CVars may apply on a later render frame
    }
    item = {};
    char message[200]{};
    std::snprintf(message, sizeof(message), "%s: %s requested=%d actual=%d; flags unchanged=%d",
                  accepted ? "CHECKBOX_COMMIT_VERIFIED" : "CHECKBOX_COMMIT_FAILED", name,
                  wanted ? 1 : 0, var->int_value, var->base.flags == flags ? 1 : 0);
    if (logger) logger(message);
}

inline void Jump(unsigned char* location, const void* destination) {
    location[0] = 0xe9;
    const auto relative = static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(destination) -
                                                   reinterpret_cast<std::uintptr_t>(location) - 5);
    std::memcpy(location + 1, &relative, sizeof(relative));
}

inline bool Install(HMODULE image, Logger log) {
    if (trampoline) return image == reinterpret_cast<HMODULE>(module);
    auto base = reinterpret_cast<unsigned char*>(image);
    if (!Readable(base + EventRva, sizeof(Prefix)) || std::memcmp(base + EventRva, Prefix, sizeof(Prefix))) return false;
    auto code = static_cast<unsigned char*>(VirtualAlloc(nullptr, 10, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    if (!code) return false;
    std::memcpy(code, Prefix, sizeof(Prefix));
    Jump(code + 5, base + EventRva + 5);
    DWORD old = 0;
    if (!VirtualProtect(code, 10, PAGE_EXECUTE_READ, &old)) {
        VirtualFree(code, 0, MEM_RELEASE);
        return false;
    }
    DWORD protection = 0;
    if (!VirtualProtect(base + EventRva, 5, PAGE_EXECUTE_READWRITE, &protection)) {
        VirtualFree(code, 0, MEM_RELEASE);
        return false;
    }
    module = base;
    logger = log;
    owner_thread = GetCurrentThreadId();
    trampoline = code;
    pending = {};
    Jump(base + EventRva, reinterpret_cast<void*>(&Checked));
    DWORD ignored = 0;
    const bool restored = VirtualProtect(base + EventRva, 5, protection, &ignored) != 0;
    FlushInstructionCache(GetCurrentProcess(), code, 10);
    FlushInstructionCache(GetCurrentProcess(), base + EventRva, 5);
    if (!restored) {
        std::memcpy(base + EventRva, Prefix, 5);
        VirtualProtect(base + EventRva, 5, protection, &ignored);
        FlushInstructionCache(GetCurrentProcess(), base + EventRva, 5);
        VirtualFree(trampoline, 0, MEM_RELEASE);
        trampoline = nullptr;
        module = nullptr;
        if (logger) logger("CHECKBOX_DISABLED: code-page protection restoration failed; original handler restored");
        return false;
    }
    return true;
}

// Tests/controlled shutdown only, on the installing UI thread. Production DLL
// and GameUI are pinned until exit; uninstalling the mod takes effect on restart.
inline bool Remove() {
    if (!trampoline || GetCurrentThreadId() != owner_thread) return false;
    // Verify the live relative target, rather than assuming sole hook ownership.
    std::int32_t displacement = 0;
    std::memcpy(&displacement, module + EventRva + 1, 4);
    const auto target = reinterpret_cast<std::uintptr_t>(module + EventRva + 5) + displacement;
    if (module[EventRva] != 0xe9 || target != reinterpret_cast<std::uintptr_t>(&Checked)) return false;
    DWORD protection = 0;
    if (!VirtualProtect(module + EventRva, 5, PAGE_EXECUTE_READWRITE, &protection)) return false;
    std::memcpy(module + EventRva, Prefix, 5);
    DWORD ignored = 0;
    const bool restored = VirtualProtect(module + EventRva, 5, protection, &ignored) != 0;
    FlushInstructionCache(GetCurrentProcess(), module + EventRva, 5);
    VirtualFree(trampoline, 0, MEM_RELEASE);
    trampoline = nullptr;
    module = nullptr;
    pending = {};
    return restored;
}
}
