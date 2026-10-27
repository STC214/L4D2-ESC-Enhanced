#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <d3d9.h>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <string>
#include <vector>
#include "session_state.h"
#include "local_cvars.h"
#include "checkbox_bridge.h"

// Deliberately version 1, matching the already installed Evolved core contract.
class IL4NPluginV1 {
public:
    virtual ~IL4NPluginV1() = default;
    virtual unsigned int GetInterfaceVersion() { return 1; }
    virtual const char* GetName() { return "C session defaults"; }
    virtual const char* GetVersion() { return "1.3.1"; }
    virtual void OnModuleLoaded(const char*, std::uintptr_t) {}
    virtual void OnGameLaunch() {}
    virtual void OnD3DCreated(void*) {}
    virtual void OnD3DDeviceCreated(void*, bool) {}
};

static HMODULE self_module = nullptr;
static void* engine_client = nullptr;
static UINT_PTR timer_id = 0;
static SessionState session;
static FirstEscState map_defaults;
static void* cvar_interface = nullptr;
static bool cvar_identity_checked = false;
static bool cvar_disabled = false;
static std::atomic<bool> disabled{false};
static bool timer_observed = false;
static std::atomic<bool> bootstrap_started{false};
static std::atomic<bool> timer_ready{false};
static std::atomic<HHOOK> bootstrap_hook{nullptr};
static bool engine_identity_checked = false;
static bool checkbox_disabled = false;

static void CALLBACK Timer(HWND, UINT, UINT_PTR, DWORD);

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

static bool ModuleIdentityMatches(HMODULE module, const char* expected) {
    // This profile was inspected against this exact local x86 engine binary.
    // A game update must receive a newly reviewed ABI profile, not old slots.
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

static bool EnsureEngine() {
    HMODULE engine = GetModuleHandleW(L"engine.dll");
    // L4N can call OnGameLaunch before engine.dll is loaded. Absence means
    // WAIT, not an unreviewed binary. All engine calls stay on the window thread.
    if (!engine) return false;
    if (!engine_identity_checked) {
        if (!ModuleIdentityMatches(engine, "8a6d468059394bf4cfce32f11dcba12ef45de88da1373084d5a2916d0bf7ba86")) {
            disabled = true;
            Log("DISABLED: loaded engine hash verification failed; no ABI fallback");
            return false;
        }
        engine_identity_checked = true;
        Log("ENGINE_VERIFIED: loaded engine matches pinned SHA256");
    }
    using Factory = void*(__cdecl*)(const char*, int*);
    auto factory = reinterpret_cast<Factory>(GetProcAddress(engine, "CreateInterface"));
    void* client = factory ? factory("VEngineClient013", nullptr) : nullptr;
    if (!client) return false; // Interface registration may not be ready yet.
    if (!ValidateSlots(engine, client)) {
        disabled = true;
        Log("DISABLED: VEngineClient013 slot mismatch; no ABI fallback");
        return false;
    }
    engine_client = client;
    Log("ENGINE_READY: verified interface; connection defaults armed");
    return true;
}

static bool EnsureLocalCvars() {
    if (cvar_disabled) return false;
    if (cvar_interface) return true;
    HMODULE library = GetModuleHandleW(L"vstdlib.dll");
    HMODULE client = GetModuleHandleW(L"client.dll");
    if (!library || !client) return false;
    if (!cvar_identity_checked) {
        if (!ModuleIdentityMatches(library, "37d0c98ddfe7fa199d741dfc24526eb435f71f66d2d0e3d0500c4c1be33cb6c5") ||
            !ModuleIdentityMatches(client, "c0a8e1e88f7312db11bcfd4b0ec574d224a34b2d9a615d6088b28335eeb4af1f")) {
            cvar_disabled = true;
            Log("DEFAULTS_DISABLED: unreviewed client/vstdlib; no local-CVar ABI fallback");
            return false;
        }
        cvar_identity_checked = true;
    }
    using Factory = void*(__cdecl*)(const char*, int*);
    auto factory = reinterpret_cast<Factory>(GetProcAddress(library, "CreateInterface"));
    void* candidate = factory ? factory("VEngineCvar007", nullptr) : nullptr;
    if (!candidate) return false;
    // FindVar is slot 12 in the pinned L4D2 ICvar/IAppSystem contract.
    HMODULE owner = nullptr;
    void* method = (*reinterpret_cast<void***>(candidate))[12];
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           reinterpret_cast<LPCWSTR>(method), &owner) || owner != library) {
        cvar_disabled = true;
        Log("DEFAULTS_DISABLED: ICvar FindVar does not belong to pinned vstdlib");
        return false;
    }
    cvar_interface = candidate;
    Log("CVAR_READY: client/vstdlib hashes and VEngineCvar007 verified");
    return true;
}

static bool SetLocalInteger(const char* name, int value, bool outline_default = false) {
    if (!EnsureLocalCvars()) return false;
    using Find = CvarPrefix*(__thiscall*)(void*, const char*);
    CvarPrefix* var = Method<Find>(cvar_interface, 12)(cvar_interface, name);
    if (!var) {
        char message[160]{};
        std::snprintf(message, sizeof(message), "DEFAULT_MISSING: %s", name);
        Log(message);
        return false;
    }
    auto iface = reinterpret_cast<char*>(var) + sizeof(CommandPrefix);
    auto table = *reinterpret_cast<void***>(iface);
    for (int slot : {2, 4}) { // IConVar::SetValue(int), GetName.
        HMODULE owner = nullptr;
        if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                               reinterpret_cast<LPCWSTR>(table[slot]), &owner) ||
            (owner != GetModuleHandleW(L"client.dll") && owner != GetModuleHandleW(L"vstdlib.dll") &&
             owner != GetModuleHandleW(L"engine.dll"))) return false;
    }
    const bool ok = SetCheckedLocalInt(var, name, value, outline_default);
    char message[180]{};
    std::snprintf(message, sizeof(message), "%s: %s requested=%d actual=%d; flags unchanged",
                  ok ? "DEFAULT_VERIFIED" : "DEFAULT_FAILED", name, value,
                  var->parent ? var->parent->int_value : -1);
    Log(message);
    return ok;
}

static void EnsureCheckboxBridge() {
    if (checkbox_disabled || CheckboxBridge::trampoline) return;
    HMODULE image = GetModuleHandleW(L"gameui.dll");
    if (!image) return;
    auto base = reinterpret_cast<unsigned char*>(image);
    const unsigned char apply_prefix[] = {0x56, 0x8b, 0xf1, 0x57, 0x8d};
    auto table = reinterpret_cast<void**>(base + 0x15f674);
    if (!ModuleIdentityMatches(image, "321ec9b5865582330af61e81eb347da31cc213cc6c95b80d6d98170b8a5fbb40") ||
        std::memcmp(base + 0x4500, apply_prefix, sizeof(apply_prefix)) ||
        std::memcmp(base + 0x4320, apply_prefix, sizeof(apply_prefix)) ||
        table[0x400 / 4] != base + 0xe5f40 || table[0x3fc / 4] != base + 0x42e0) {
        checkbox_disabled = true;
        Log("CHECKBOX_DISABLED: GameUI identity/native ApplyChanges ABI mismatch; no fallback");
        return;
    }
    HMODULE pinned = nullptr;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
                           reinterpret_cast<LPCWSTR>(base), &pinned) || !CheckboxBridge::Install(image, Log)) {
        checkbox_disabled = true;
        Log("CHECKBOX_DISABLED: scoped UI event bridge installation failed");
        return;
    }
    Log("CHECKBOX_READY: scoped C_ESC_BOOL controls commit through native ApplyChanges with readback; game files unchanged");
}

static void Poll() {
    if (disabled || (!engine_client && !EnsureEngine())) return;
    EnsureCheckboxBridge();
    CheckboxBridge::PollPending();
    using Bool = bool(__thiscall*)(void*);
    using Pointer = void*(__thiscall*)(void*);
    using String = const char*(__thiscall*)(void*);
    using Float = float(__thiscall*)(void*);
    using Command = void(__thiscall*)(void*, const char*);
    const bool connected = Method<Bool>(engine_client, 27)(engine_client);
    if (!connected) {
        map_defaults.Update(false, false, 0, -1, "", false);
        session.Update(false, false, 0, -1);
        return;
    }
    const bool active = Method<Bool>(engine_client, 26)(engine_client);
    void* channel = Method<Pointer>(engine_client, 74)(engine_client);
    if (!channel) {
        map_defaults.Update(connected, active, 0, -1, "", true);
        return;
    }
    const char* level = Method<String>(engine_client, 52)(engine_client);
    // INetChannelInfo's first methods match its documented x86 interface.
    const float age = Method<Float>(channel, 3)(channel);
    const bool playback = Method<Bool>(channel, 8)(channel);
    const bool background = BackgroundMap(level);
    if (session.Update(connected, active, reinterpret_cast<std::uintptr_t>(channel), age,
                       background, playback)) {
        // Same path as user console execution; no server/cheat-policy changes.
        Method<Command>(engine_client, 107)(engine_client, "exec l4d2esc_defaults\n");
        Log("NEW_CONNECTION: queued exec l4d2esc_defaults once; ESC and same-channel map loads do not reset");
    }
    if (EnsureLocalCvars() && map_defaults.Update(connected, active,
            reinterpret_cast<std::uintptr_t>(channel), age, level, true, background, playback)) {
        // Named client-render/physics defaults only. Do not remove flags or
        // touch replicated server variables. Apply once per map, not a lock.
        for (const char* name : {"r_RainParticleDensity", "r_SnowParticles", "fog_override",
                                 "fog_enable", "cl_ragdoll_maxcount"}) SetLocalInteger(name, 0);
        SetLocalInteger("r_flashlightconstant", 1);
        SetLocalInteger("r_flashlightfar", 3000);
        SetLocalInteger("r_flashlightfov", 165);
        SetLocalInteger("sv_disable_glow_survivors", 0, true);
        SetLocalInteger("sv_disable_glow_faritems", 0, true);
        Log("OUTLINE_DEFAULTS: attempted zero once; server replication may override, no flag changes");
        Log("MAP_DEFAULTS: local weather/corpse/light defaults attempted once; see per-value readback");
    }
}

static void CALLBACK Timer(HWND, UINT, UINT_PTR, DWORD) {
    // Installed by a message hook on the actual game-window thread. The worker
    // below only locates that thread; it never calls the engine.
    __try {
        if (!timer_observed) {
            timer_observed = true;
            HHOOK hook = bootstrap_hook.exchange(nullptr);
            if (hook) UnhookWindowsHookEx(hook);
            Log("TIMER_ACTIVE: game-window thread dispatched its first timer callback");
        }
        Poll();
        if (disabled && timer_id) {
            KillTimer(nullptr, timer_id);
            timer_id = 0;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        disabled = true;
        KillTimer(nullptr, timer_id);
        timer_id = 0;
        Log("DISABLED: engine/connection query exception; no retry or offset fallback");
    }
}

static void StartTimerOnWindowThread() {
    if (!timer_ready.load() && !disabled) {
        timer_id = SetTimer(nullptr, 0, 100, Timer);
        if (!timer_id) {
            disabled = true;
            Log("DISABLED: game-window timer creation failed");
        } else {
            timer_ready.store(true);
            Log("READY: timer installed on game-window thread; waiting for engine/interface");
        }
    }
}

static LRESULT CALLBACK StartOnWindowThread(int code, WPARAM key, LPARAM data) {
    if (code >= 0) StartTimerOnWindowThread();
    return CallNextHookEx(nullptr, code, key, data);
}

static BOOL CALLBACK FindGameWindow(HWND window, LPARAM result) {
    DWORD process = 0;
    GetWindowThreadProcessId(window, &process);
    RECT rect{};
    if (process == GetCurrentProcessId() && IsWindowVisible(window) &&
        GetClientRect(window, &rect) &&
        rect.right - rect.left >= 320 && rect.bottom - rect.top >= 200) {
        *reinterpret_cast<HWND*>(result) = window;
        return FALSE;
    }
    return TRUE;
}

static DWORD WINAPI Bootstrap(void*) {
    Log("BOOTSTRAP_STARTED: locating game window, including owned windows");
    for (int attempt = 0; attempt < 1200; ++attempt) {
        if (timer_ready.load() || disabled.load()) return 0;
        HWND window = nullptr;
        EnumWindows(FindGameWindow, reinterpret_cast<LPARAM>(&window));
        if (window) {
            DWORD thread = GetWindowThreadProcessId(window, nullptr);
            char message[180]{};
            std::snprintf(message, sizeof(message), "WINDOW_FOUND: thread=%lu owned=%d", thread,
                          GetWindow(window, GW_OWNER) ? 1 : 0);
            Log(message);
            if (timer_ready.load()) return 0;
            HHOOK hook = SetWindowsHookExW(WH_GETMESSAGE, StartOnWindowThread, self_module, thread);
            if (hook) {
                bootstrap_hook.store(hook);
                Log("HOOK_READY: game-window message hook installed");
                PostMessageW(window, WM_NULL, 0, 0);
                return 0;
            }
            std::snprintf(message, sizeof(message), "HOOK_FAILED: Win32 error=%lu", GetLastError());
            Log(message);
        }
        Sleep(100);
    }
    Log("BOOTSTRAP_TIMEOUT: no usable game-window message hook after 120 seconds");
    return 0;
}

class Plugin final : public IL4NPluginV1 {
public:
    void OnD3DDeviceCreated(void* object, bool) override {
        if (!object || disabled.load()) return;
        OnGameLaunch(); // Idempotent pin/bootstrap, even if callback order differs.
        D3DDEVICE_CREATION_PARAMETERS parameters{};
        auto device = static_cast<IDirect3DDevice9*>(object);
        if (FAILED(device->GetCreationParameters(&parameters)) || !IsWindow(parameters.hFocusWindow)) {
            Log("D3D_WINDOW_FAILED: no valid device focus window");
            return;
        }
        DWORD process = 0;
        DWORD thread = GetWindowThreadProcessId(parameters.hFocusWindow, &process);
        if (process != GetCurrentProcessId()) return;
        if (thread == GetCurrentThreadId()) {
            Log("D3D_WINDOW_READY: creation callback is on the game-window thread");
            StartTimerOnWindowThread();
        } else if (!timer_ready.load() && !bootstrap_hook.load()) {
            HHOOK hook = SetWindowsHookExW(WH_GETMESSAGE, StartOnWindowThread, self_module, thread);
            if (hook) {
                bootstrap_hook.store(hook);
                PostMessageW(parameters.hFocusWindow, WM_NULL, 0, 0);
                Log("D3D_HOOK_READY: device focus-window thread selected directly");
            }
        }
    }

    void OnGameLaunch() override {
        if (bootstrap_started.exchange(true) || disabled) return;
        HMODULE pinned = nullptr;
        // Timers must never outlive their DLL; unloading is deferred to exit.
        if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
                               reinterpret_cast<LPCWSTR>(&Timer), &pinned)) {
            disabled = true;
            return;
        }
        HANDLE worker = CreateThread(nullptr, 0, Bootstrap, nullptr, 0, nullptr);
        if (!worker) {
            disabled = true;
            Log("DISABLED: window-bootstrap worker creation failed");
            return;
        }
        CloseHandle(worker);
        Log("WAIT_WINDOW: bootstrap armed; no engine calls on worker thread");
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
