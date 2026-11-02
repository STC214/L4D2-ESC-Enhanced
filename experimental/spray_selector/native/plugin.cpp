#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <d3d9.h>
#include <array>
#include <atomic>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <vector>
#include "bridge.h"
#include "apply.h"
#include "viewport.h"

class IL4NPluginV1 {
public:
    virtual ~IL4NPluginV1() = default;
    virtual unsigned int GetInterfaceVersion() { return 1; }
    virtual const char* GetName() { return "CSP numbered spray selector prototype"; }
    virtual const char* GetVersion() { return "0.2.3"; }
    virtual void OnModuleLoaded(const char*, std::uintptr_t) {}
    virtual void OnGameLaunch() {}
    virtual void OnD3DCreated(void*) {}
    virtual void OnD3DDeviceCreated(void*, bool) {}
};

static HMODULE self = nullptr;
static std::atomic<bool> started{false}, timer_ready{false};
static std::atomic<HHOOK> startup_hook{nullptr};
static std::atomic<HWND> viewport_window{nullptr};
static bool identity_checked = false;
static UINT_PTR timer = 0;

static std::filesystem::path Root() {
    wchar_t path[32768]{};
    if (!GetModuleFileNameW(self, path, 32768)) return {};
    return std::filesystem::path(path).parent_path().parent_path().parent_path().parent_path();
}

static void Log(const char* message) {
    const auto root = Root();
    if (root.empty()) return;
    FILE* file = nullptr;
    if (!_wfopen_s(&file, (root / L"CSPSelector.log").c_str(), L"ab") && file) {
        std::fprintf(file, "[%llu] %s\r\n", static_cast<unsigned long long>(GetTickCount64()), message);
        std::fclose(file);
    }
}

static bool Identity(HMODULE module, const char* expected) {
    wchar_t path[32768]{};
    if (!module || !GetModuleFileNameW(module, path, 32768)) return false;
    std::ifstream stream(std::filesystem::path(path), std::ios::binary);
    if (!stream) return false;
    std::vector<unsigned char> data((std::istreambuf_iterator<char>(stream)), {});
    if (stream.bad() || data.empty() || data.size() > UINT32_MAX) return false;
    BCRYPT_ALG_HANDLE algorithm = nullptr;
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) < 0) return false;
    std::array<UCHAR, 32> digest{};
    const bool ok = BCryptHash(algorithm, nullptr, 0, data.data(), static_cast<ULONG>(data.size()),
                               digest.data(), static_cast<ULONG>(digest.size())) >= 0;
    BCryptCloseAlgorithmProvider(algorithm, 0);
    char hex[65]{};
    for (std::size_t i = 0; i < digest.size(); ++i) std::snprintf(hex + 2 * i, 3, "%02x", digest[i]);
    return ok && !std::strcmp(hex, expected);
}

static bool Owned(void* address, HMODULE module) {
    HMODULE owner = nullptr;
    return address && module && GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
        GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, reinterpret_cast<LPCWSTR>(address), &owner) && owner == module;
}

static bool ApplySelection(int identifier) {
    const HMODULE engine = GetModuleHandleW(L"engine.dll"), library = GetModuleHandleW(L"vstdlib.dll");
    if (!identity_checked) {
        if (!Identity(engine, "8a6d468059394bf4cfce32f11dcba12ef45de88da1373084d5a2916d0bf7ba86") ||
            !Identity(library, "37d0c98ddfe7fa199d741dfc24526eb435f71f66d2d0e3d0500c4c1be33cb6c5")) {
            Log("APPLY_BLOCKED: engine/vstdlib identity mismatch; dialog stays open");
            return false;
        }
        identity_checked = true;
    }
    using Factory = void* (__cdecl*)(const char*, int*);
    auto factory = reinterpret_cast<Factory>(GetProcAddress(library, "CreateInterface"));
    void* cvar = factory ? factory("VEngineCvar007", nullptr) : nullptr;
    if (!CSP::Readable(cvar, sizeof(void*))) return false;
    auto table = *reinterpret_cast<void***>(cvar);
    if (!CSP::Readable(table, 13 * sizeof(void*)) || !Owned(table[12], library)) return false;
    using Find = CvarPrefix* (__thiscall*)(void*, const char*);
    auto value = reinterpret_cast<Find>(table[12])(cvar, "cl_logofile");
    if (!CSP::Readable(value, sizeof(CvarPrefix)) || !CSP::Readable(value->interface_table, 7 * sizeof(void*))) return false;
    auto methods = reinterpret_cast<void**>(value->interface_table);
    if (!Owned(methods[CSP::StringSetterSlot], engine) && !Owned(methods[CSP::StringSetterSlot], library)) {
        Log("APPLY_BLOCKED: unreviewed IConVar string setter");
        return false;
    }
    const int before_flags = value->base.flags;
    const int before_parent_flags = CSP::Readable(value->parent, sizeof(CvarPrefix)) ? value->parent->base.flags : -1;
    const bool ok = CSP::ApplyValue(value, identifier);
    char actual[128] = "unavailable";
    bool flags_same = false;
    if (CSP::Readable(value->parent, sizeof(CvarPrefix))) {
        flags_same = before_flags == value->base.flags && before_parent_flags == value->parent->base.flags;
        const char* text = value->parent->string_value;
        if (value->parent->string_length > 0 && CSP::Readable(text, 1)) {
            for (std::size_t i = 0; i < sizeof(actual) - 1; ++i) {
                if (!CSP::Readable(text + i, 1)) { actual[i] = 0; break; }
                actual[i] = text[i];
                if (!text[i]) break;
            }
            actual[sizeof(actual) - 1] = 0;
        }
    }
    char message[384]{};
    std::snprintf(message, sizeof(message), "%s: id=%03d setter_slot=3 requested=materials/vgui/logos/csp_test/test_%03d.vtf actual=%s flags_unchanged=%d",
                  ok ? "APPLY_VERIFIED" : "APPLY_READBACK_FAILED", identifier, identifier, actual, flags_same ? 1 : 0);
    Log(message);
    return ok;
}

static void CALLBACK Timer(HWND, UINT, UINT_PTR, DWORD) {
    HMODULE image = GetModuleHandleW(L"gameui.dll");
    if (!image) return;
    if (CSP::patched) {
        if (CSP::patched != reinterpret_cast<unsigned char*>(image) + 0x6a620) {
            KillTimer(nullptr, timer);
            Log("DISABLED: GameUI module changed after bridge installation");
            return;
        }
        if (GetCurrentThreadId() == CSP::owner)
            CSPViewport::Poll(reinterpret_cast<unsigned char*>(image), viewport_window.load(), Log);
        return;
    }
    if (!Identity(image, "321ec9b5865582330af61e81eb347da31cc213cc6c95b80d6d98170b8a5fbb40")) {
        KillTimer(nullptr, timer);
        Log("DISABLED: GameUI identity mismatch; no runtime hook installed");
        return;
    }
    const bool ok = CSP::Install(reinterpret_cast<unsigned char*>(image) + 0x6a620,
                                 GetCurrentThreadId(), ApplySelection);
    if (!ok) KillTimer(nullptr, timer);
    Log(ok ? "READY: scoped Multiplayer bridge + CSP-only viewport clamp; numbered IDs 001..040" :
             "DISABLED: hook prologue mismatch or allocation failure");
}

static void StartTimer() {
    if (timer_ready.exchange(true)) return;
    timer = SetTimer(nullptr, 0, 50, Timer);
    Log(timer ? "TIMER_READY: game-window thread" : "DISABLED: SetTimer failed");
}

static LRESULT CALLBACK OnMessage(int code, WPARAM wp, LPARAM lp) {
    if (code >= 0) {
        StartTimer();
        const HHOOK hook = startup_hook.exchange(nullptr);
        if (hook) UnhookWindowsHookEx(hook);
    }
    return CallNextHookEx(nullptr, code, wp, lp);
}

static BOOL CALLBACK FindWindow(HWND window, LPARAM result) {
    DWORD process = 0;
    GetWindowThreadProcessId(window, &process);
    wchar_t name[128]{};
    GetClassNameW(window, name, 128);
    if (process == GetCurrentProcessId() && IsWindowVisible(window) && !std::wcscmp(name, L"Valve001")) {
        *reinterpret_cast<HWND*>(result) = window;
        return FALSE;
    }
    return TRUE;
}

static DWORD WINAPI Bootstrap(void*) {
    for (int attempt = 0; attempt < 1200 && !timer_ready.load(); ++attempt) {
        HWND window = nullptr;
        EnumWindows(FindWindow, reinterpret_cast<LPARAM>(&window));
        if (window) {
            viewport_window.store(window);
            const DWORD thread = GetWindowThreadProcessId(window, nullptr);
            const HHOOK hook = SetWindowsHookExW(WH_GETMESSAGE, OnMessage, self, thread);
            if (hook) {
                startup_hook.store(hook);
                PostMessageW(window, WM_NULL, 0, 0);
                return 0;
            }
        }
        Sleep(100);
    }
    return 0;
}

class Plugin final : public IL4NPluginV1 {
public:
    void OnGameLaunch() override {
        if (started.exchange(true)) return;
        HMODULE pinned = nullptr;
        if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
                               reinterpret_cast<LPCWSTR>(&Timer), &pinned)) return;
        const HANDLE worker = CreateThread(nullptr, 0, Bootstrap, nullptr, 0, nullptr);
        if (worker) CloseHandle(worker);
        Log("WAIT_WINDOW: no engine calls on worker thread");
    }
    void OnD3DDeviceCreated(void* object, bool) override {
        if (!object) return;
        OnGameLaunch();
        D3DDEVICE_CREATION_PARAMETERS parameters{};
        auto device = static_cast<IDirect3DDevice9*>(object);
        if (FAILED(device->GetCreationParameters(&parameters))) return;
        DWORD process = 0;
        const DWORD thread = GetWindowThreadProcessId(parameters.hFocusWindow, &process);
        if (process == GetCurrentProcessId()) {
            viewport_window.store(parameters.hFocusWindow);
            if (thread == GetCurrentThreadId()) StartTimer();
        }
    }
};

extern "C" __declspec(dllexport) IL4NPluginV1* GetL4NPluginInstance() {
    static Plugin plugin;
    return &plugin;
}

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) self = module;
    return TRUE;
}
