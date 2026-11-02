#pragma once
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include "../../../native/c_session_defaults/local_cvars.h"

namespace CSP {
inline constexpr std::size_t StringSetterSlot = 3; // Pinned engine IConVar: Color, int, float, string.
inline bool Readable(const void* pointer, std::size_t size) {
    auto at = reinterpret_cast<std::uintptr_t>(pointer);
    if (!at || size > UINTPTR_MAX - at) return false;
    const auto end = at + size;
    while (at < end) {
        MEMORY_BASIC_INFORMATION info{};
        if (!VirtualQuery(reinterpret_cast<void*>(at), &info, sizeof(info)) || info.State != MEM_COMMIT ||
            (info.Protect & (PAGE_GUARD | PAGE_NOACCESS))) return false;
        const DWORD access = info.Protect & 0xff;
        if (access != PAGE_READONLY && access != PAGE_READWRITE && access != PAGE_WRITECOPY &&
            access != PAGE_EXECUTE_READ && access != PAGE_EXECUTE_READWRITE && access != PAGE_EXECUTE_WRITECOPY) return false;
        const auto next = reinterpret_cast<std::uintptr_t>(info.BaseAddress) + info.RegionSize;
        if (next <= at) return false;
        at = next;
    }
    return true;
}

inline bool Equal(const char* value, const char* expected) {
    const std::size_t size = std::strlen(expected) + 1;
    return Readable(value, size) && !std::memcmp(value, expected, size);
}

inline bool ApplyValue(CvarPrefix* value, int identifier) {
    if (identifier < 1 || identifier > 40 || !Readable(value, sizeof(CvarPrefix)) ||
        !Readable(value->parent, sizeof(CvarPrefix)) || value->parent->parent != value->parent ||
        !Equal(value->base.name, "cl_logofile") || !Equal(value->parent->base.name, "cl_logofile")) return false;
    auto parent = value->parent;
    const int flags = value->base.flags, parent_flags = parent->base.flags;
    if ((flags | parent_flags) & ((1 << 13) | (1 << 14))) return false;
    auto table = value->interface_table;
    if (!Readable(table, sizeof(void*) * 7)) return false;
    char path[128]{};
    std::snprintf(path, sizeof(path), "materials/vgui/logos/csp_test/test_%03d.vtf", identifier);
    void* iface = reinterpret_cast<char*>(value) + sizeof(CommandPrefix);
    using SetString = void (__thiscall*)(void*, const char*);
    auto methods = reinterpret_cast<void**>(table);
    reinterpret_cast<SetString>(methods[StringSetterSlot])(iface, path);
    return parent->string_length >= static_cast<int>(std::strlen(path) + 1) && Equal(parent->string_value, path) &&
           value->base.flags == flags && parent->base.flags == parent_flags;
}
}
