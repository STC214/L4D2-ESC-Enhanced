#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <string>
#include <vector>
#include "session_state.h"

// Deliberately version 1, matching the already installed Evolved core contract.
class IL4NPluginV1 {
public:
    virtual ~IL4NPluginV1() = default;
    virtual unsigned int GetInterfaceVersion() { return 1; }
    virtual const char* GetName() { return "C session defaults"; }
    virtual const char* GetVersion() { return "1.1.0"; }
    virtual void OnModuleLoaded(const char*, std::uintptr_t) {}
    virtual void OnGameLaunch() {}
    virtual void OnD3DCreated(void*) {}
    virtual void OnD3DDeviceCreated(void*, bool) {}
};

static HMODULE self_module = nullptr;
static void* engine_client = nullptr;
static UINT_PTR timer_id = 0;
static SessionState session;
static FirstEscState first_escape;
static HHOOK keyboard_hook = nullptr;
static DWORD keyboard_thread = 0;
static std::atomic<bool> accept_escape{false};
static std::atomic<bool> escape_requested{false};
static bool disabled = false;
static bool timer_observed = false;

static std::filesystem::path GameRoot() {
    wchar_t path[32768] = {};
    if (!GetModuleFileNameW(self_module, path, 32768)) return {};
    return std::filesystem::path(path).parent_path().parent_path().parent_path().parent_path();
}

static void Log(const char* message) {
    const auto root = GameRoot();
    if (root.empty()) return;
    FILE* file = nullptr;
    if (_wfopen_s(&file, (root / L"CSessionDefaults.log").c_str(), L"ab") != 0 || !file) return;
    std::fprintf(file, "[%llu] %s\r\n", static_cast<unsigned long long>(GetTickCount64()), message);
    std::fclose(file);
}

static LRESULT CALLBACK Keyboard(int code, WPARAM key, LPARAM details) {
    // Only fresh ESC key-downs on a game window. Never consume/remap input or
    // execute engine functions from the keyboard callback's window thread.
    if (code == HC_ACTION && key == VK_ESCAPE &&
        (static_cast<ULONG_PTR>(details) & 0xC0000000u) == 0 && accept_escape.load()) {
        DWORD process = 0;
        GetWindowThreadProcessId(GetForegroundWindow(), &process);
        if (process == GetCurrentProcessId()) escape_requested.store(true);
    }
    return CallNextHookEx(nullptr, code, key, details);
}

static void EnsureKeyboardHook() {
    DWORD process = 0;
    const DWORD thread = GetWindowThreadProcessId(GetForegroundWindow(), &process);
    if (!thread || process != GetCurrentProcessId() ||
        (keyboard_hook && keyboard_thread == thread)) return;
    if (keyboard_hook) UnhookWindowsHookEx(keyboard_hook);
    keyboard_hook = SetWindowsHookExW(WH_KEYBOARD, Keyboard, self_module, thread);
    keyboard_thread = keyboard_hook ? thread : 0;
    static bool failure_logged = false;
    if (keyboard_hook) {
        Log("INPUT_READY: thread-local game keyboard hook; no input remap or global keyboard hook");
    } else if (!failure_logged) {
        failure_logged = true;
        Log("INPUT_ERROR: first-ESC input hook unavailable; connection defaults remain separate");
    }
}

static bool EngineIdentityMatches(HMODULE module) {
    // This profile was inspected against this exact local x86 engine binary.
    // A game update must receive a newly reviewed ABI profile, not old slots.
    constexpr char expected[] = "8a6d468059394bf4cfce32f11dcba12ef45de88da1373084d5a2916d0bf7ba86";
    wchar_t path[32768] = {};
    if (!GetModuleFileNameW(module, path, 32768)) return false;
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                             nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return false;
    BCRYPT_ALG_HANDLE algorithm = nullptr;
    BCRYPT_HASH_HANDLE hash = nullptr;
    DWORD object_size = 0, returned = 0;
    bool ok = BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) >= 0;
    if (ok) ok = BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH, reinterpret_cast<PUCHAR>(&object_size),
                                  sizeof(object_size), &returned, 0) >= 0;
    std::vector<UCHAR> object(object_size);
    if (ok) ok = BCryptCreateHash(algorithm, &hash, object.data(), object_size, nullptr, 0, 0) >= 0;
    std::array<UCHAR, 65536> buffer{};
    DWORD bytes = 0;
    while (ok) {
        if (!ReadFile(file, buffer.data(), static_cast<DWORD>(buffer.size()), &bytes, nullptr)) {
            ok = false;
            break;
        }
        if (!bytes) break;
        ok = BCryptHashData(hash, buffer.data(), bytes, 0) >= 0;
    }
    std::array<UCHAR, 32> digest{};
    if (ok) ok = BCryptFinishHash(hash, digest.data(), static_cast<ULONG>(digest.size()), 0) >= 0;
    if (hash) BCryptDestroyHash(hash);
    if (algorithm) BCryptCloseAlgorithmProvider(algorithm, 0);
    CloseHandle(file);
    char hex[65] = {};
    for (std::size_t i = 0; i < digest.size(); ++i) {
        std::snprintf(hex + i * 2, 3, "%02x", static_cast<unsigned int>(digest[i]));
    }
    return ok && std::strcmp(hex, expected) == 0;
}

template <typename Function>
static Function Method(void* object, std::size_t slot) {
    return reinterpret_cast<Function>((*reinterpret_cast<void***>(object))[slot]);
}

static bool ValidateSlots(HMODULE module, void* client) {
    // Slots below are from the inspected current binary, not the older public
    // SDK's later-method ordering. No memory or vtable modifications are made.
    constexpr std::size_t slots[] = {26, 27, 52, 74, 107};
    constexpr std::uintptr_t rvas[] = {0x5f1a0, 0x5f1b0, 0x5f1c0, 0x5dda0, 0x5cf20};
    auto table = *reinterpret_cast<void***>(client);
    const auto base = reinterpret_cast<std::uintptr_t>(module);
    for (std::size_t i = 0; i < std::size(slots); ++i) {
        if (reinterpret_cast<std::uintptr_t>(table[slots[i]]) != base + rvas[i]) return false;
    }
    return true;
}

static bool BackgroundMap(const char* level) {
    if (!level) return false;
    const char* base = level;
    for (const char* p = level; *p; ++p) if (*p == '/' || *p == '\\') base = p + 1;
    return std::strncmp(base, "background", 10) == 0 && base[10] >= '0' && base[10] <= '9';
}

static void Poll() {
    if (!engine_client || disabled) return;
    EnsureKeyboardHook();
    const bool escape = escape_requested.exchange(false);
    using Bool = bool(__thiscall*)(void*);
    using Pointer = void*(__thiscall*)(void*);
    using String = const char*(__thiscall*)(void*);
    using Float = float(__thiscall*)(void*);
    using Command = void(__thiscall*)(void*, const char*);
    const bool connected = Method<Bool>(engine_client, 27)(engine_client);
    if (!connected) {
        accept_escape.store(false);
        first_escape.Update(false, false, 0, -1, "", false);
        session.Update(false, false, 0, -1);
        return;
    }
    void* channel = Method<Pointer>(engine_client, 74)(engine_client);
    if (!channel) {
        accept_escape.store(false);
        return;
    }
    const bool active = Method<Bool>(engine_client, 26)(engine_client);
    const char* level = Method<String>(engine_client, 52)(engine_client);
    // INetChannelInfo's first methods match its documented x86 interface.
    const float age = Method<Float>(channel, 3)(channel);
    const bool playback = Method<Bool>(channel, 8)(channel);
    const bool background = BackgroundMap(level);
    accept_escape.store(active && !background && !playback &&
                        std::isfinite(age) && age >= 0);
    if (session.Update(connected, active, reinterpret_cast<std::uintptr_t>(channel), age,
                       background, playback)) {
        // Same path as user console execution; no server/cheat-policy changes.
        Method<Command>(engine_client, 107)(engine_client, "exec l4d2esc_defaults\n");
        Log("NEW_CONNECTION: queued exec l4d2esc_defaults once; ESC and same-channel map loads do not reset");
    }
    if (first_escape.Update(connected, active, reinterpret_cast<std::uintptr_t>(channel), age,
                            level, escape, background, playback)) {
        Method<Command>(engine_client, 107)(engine_client, "r_flashlightfov 150\n");
        Log("FIRST_ESC: queued r_flashlightfov 150 once for this map; manual changes remain untouched afterwards");
    }
}

static void CALLBACK Timer(HWND, UINT, UINT_PTR, DWORD) {
    // A thread timer executes on the L4N launch callback's message-pump thread,
    // never a worker-thread call into the engine. Protect failure by disabling.
    __try {
        if (!timer_observed) {
            timer_observed = true;
            Log("TIMER_ACTIVE: launch thread dispatched its first timer callback");
        }
        Poll();
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        disabled = true;
        accept_escape.store(false);
        if (keyboard_hook) UnhookWindowsHookEx(keyboard_hook);
        keyboard_hook = nullptr;
        KillTimer(nullptr, timer_id);
        timer_id = 0;
        Log("DISABLED: engine/connection query exception; no retry or offset fallback");
    }
}

class Plugin final : public IL4NPluginV1 {
public:
    void OnGameLaunch() override {
        if (timer_id || disabled) return;
        HMODULE engine = GetModuleHandleW(L"engine.dll");
        if (!engine || !EngineIdentityMatches(engine)) {
            disabled = true;
            Log("DISABLED: unreviewed engine.dll; update ABI profile before enabling");
            return;
        }
        using Factory = void*(__cdecl*)(const char*, int*);
        auto factory = reinterpret_cast<Factory>(GetProcAddress(engine, "CreateInterface"));
        engine_client = factory ? factory("VEngineClient013", nullptr) : nullptr;
        if (!engine_client || !ValidateSlots(engine, engine_client)) {
            engine_client = nullptr;
            disabled = true;
            Log("DISABLED: VEngineClient013 interface/slot mismatch");
            return;
        }
        HMODULE pinned = nullptr;
        // Timers must never outlive their DLL; unloading is deferred to exit.
        if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
                               reinterpret_cast<LPCWSTR>(&Timer), &pinned)) {
            disabled = true;
            return;
        }
        timer_id = SetTimer(nullptr, 0, 100, Timer);
        if (!timer_id) {
            disabled = true;
            Log("DISABLED: thread timer creation failed");
            return;
        }
        Log("READY: L4N launch-thread timer installed; awaiting connection; runtime still requires verification");
    }
};

extern "C" __declspec(dllexport) IL4NPluginV1* GetL4NPluginInstance() {
    static Plugin plugin;
    return &plugin;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) self_module = instance;
    return TRUE;
}
