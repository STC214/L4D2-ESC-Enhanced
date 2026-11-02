#pragma once
#include <windows.h>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>

namespace CSP {
constexpr char Prefix[] = "CSP_TEST_APPLY_";
constexpr unsigned char Prologue[] = {0x55, 0x8b, 0xec, 0x81, 0xec, 0x2c, 0x01, 0, 0};
using Handler = void (__thiscall*)(void*, const char*);
using Apply = bool (*)(int);
inline Handler original = nullptr;
inline Apply apply = nullptr;
inline DWORD owner = 0;
inline unsigned char* patched = nullptr;
inline unsigned char* trampoline = nullptr;

inline int Parse(const char* command) {
    if (!command || std::strncmp(command, Prefix, sizeof(Prefix) - 1)) return -1;
    const char* number = command + sizeof(Prefix) - 1;
    if (std::strlen(number) != 3) return 0;
    int value = 0;
    for (int i = 0; i < 3; ++i) {
        if (number[i] < '0' || number[i] > '9') return 0;
        value = value * 10 + number[i] - '0';
    }
    return value >= 1 && value <= 40 ? value : 0;
}

inline void Dispatch(void* object, const char* command) {
    const int value = Parse(command);
    if (GetCurrentThreadId() != owner || value < 0) {
        if (original) original(object, command);
        return;
    }
    // Unknown IDs in our namespace never reach the engine or an arbitrary command.
    if (value && apply && apply(value) && original) original(object, "Back");
}

inline void __fastcall Hook(void* object, void*, const char* command) {
    Dispatch(object, command);
}

inline bool Install(unsigned char* target, DWORD thread, Apply callback) {
    if (!target || !thread || !callback || patched ||
        std::memcmp(target, Prologue, sizeof(Prologue))) return false;
    auto buffer = static_cast<unsigned char*>(VirtualAlloc(nullptr, 32, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    if (!buffer) return false;
    std::memcpy(buffer, Prologue, sizeof(Prologue));
    buffer[9] = 0xe9;
    const auto jump_back = static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(target + 9) -
                                                    reinterpret_cast<std::uintptr_t>(buffer + 14));
    std::memcpy(buffer + 10, &jump_back, 4);
    DWORD previous = 0;
    if (!VirtualProtect(buffer, 32, PAGE_EXECUTE_READ, &previous)) {
        VirtualFree(buffer, 0, MEM_RELEASE);
        return false;
    }
    FlushInstructionCache(GetCurrentProcess(), buffer, 32);
    std::array<unsigned char, 9> patch{};
    patch.fill(0x90);
    patch[0] = 0xe9;
    const auto jump = static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(&Hook) -
                                               reinterpret_cast<std::uintptr_t>(target + 5));
    std::memcpy(patch.data() + 1, &jump, 4);
    if (!VirtualProtect(target, patch.size(), PAGE_EXECUTE_READWRITE, &previous)) {
        VirtualFree(buffer, 0, MEM_RELEASE);
        return false;
    }
    owner = thread;
    apply = callback;
    trampoline = buffer;
    original = reinterpret_cast<Handler>(buffer);
    patched = target;
    std::memcpy(target, patch.data(), patch.size());
    FlushInstructionCache(GetCurrentProcess(), target, patch.size());
    DWORD ignored = 0;
    VirtualProtect(target, patch.size(), previous, &ignored);
    return true;
}

// Fixture-only teardown. The production DLL is pinned until process exit.
inline bool RemoveForTest() {
    if (!patched) return false;
    DWORD previous = 0;
    if (!VirtualProtect(patched, sizeof(Prologue), PAGE_EXECUTE_READWRITE, &previous)) return false;
    std::memcpy(patched, Prologue, sizeof(Prologue));
    FlushInstructionCache(GetCurrentProcess(), patched, sizeof(Prologue));
    DWORD ignored = 0;
    VirtualProtect(patched, sizeof(Prologue), previous, &ignored);
    VirtualFree(trampoline, 0, MEM_RELEASE);
    original = nullptr;
    apply = nullptr;
    patched = trampoline = nullptr;
    owner = 0;
    return true;
}
}
