#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <d3d9.h>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <string>

class PluginContract {
public:
    virtual ~PluginContract() = default;
    virtual unsigned int GetInterfaceVersion() = 0;
    virtual const char* GetName() = 0;
    virtual const char* GetVersion() = 0;
    virtual void OnModuleLoaded(const char*, std::uintptr_t) = 0;
    virtual void OnGameLaunch() = 0;
    virtual void OnD3DCreated(void*) = 0;
    virtual void OnD3DDeviceCreated(void*, bool) = 0;
};

struct DeviceFixture { void** table; HWND window; };
static HRESULT WINAPI CreationParameters(void* object, D3DDEVICE_CREATION_PARAMETERS* parameters) {
    parameters->hFocusWindow = static_cast<DeviceFixture*>(object)->window;
    return S_OK;
}

int wmain(int argc, wchar_t** argv) {
    if (argc != 3) return 2;
    const auto root = std::filesystem::path(argv[2]) / ("run_" + std::to_string(GetCurrentProcessId()));
    const auto target = root / "bin/neko/plugins/CSessionDefaults.dll";
    std::filesystem::create_directories(target.parent_path());
    std::filesystem::copy_file(argv[1], target, std::filesystem::copy_options::overwrite_existing);
    HMODULE dll = LoadLibraryW(target.c_str());
    if (!dll) return 3;
    using Factory = PluginContract*(*)();
    auto factory = reinterpret_cast<Factory>(GetProcAddress(dll, "GetL4NPluginInstance"));
    if (!factory) return 4;
    HWND owner = CreateWindowExW(WS_EX_TOOLWINDOW, L"STATIC", L"C fixture owner", WS_POPUP,
                                 -30000, -30000, 1, 1, nullptr, nullptr, nullptr, nullptr);
    HWND window = CreateWindowExW(WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE, L"STATIC", L"C fixture game",
                                  WS_POPUP, -30000, -30000, 640, 480, owner, nullptr, nullptr, nullptr);
    if (!window || !owner) return 5;
    ShowWindow(window, SW_SHOWNOACTIVATE);
    factory()->OnGameLaunch();
    void* table[10]{};
    table[9] = reinterpret_cast<void*>(&CreationParameters);
    DeviceFixture device{table, window};
    factory()->OnD3DDeviceCreated(&device, false);
    const auto deadline = GetTickCount64() + 3000;
    std::string log;
    while (GetTickCount64() < deadline) {
        MSG message{};
        while (PeekMessageW(&message, nullptr, 0, 0, PM_REMOVE)) {
            TranslateMessage(&message);
            DispatchMessageW(&message);
        }
        std::ifstream input(root / "CSessionDefaults.log", std::ios::binary);
        if (input) log.assign(std::istreambuf_iterator<char>(input), {});
        if (log.find("TIMER_ACTIVE") != std::string::npos) break;
        Sleep(5);
    }
    DestroyWindow(window);
    DestroyWindow(owner);
    std::printf("FIXTURE LOG\n%s\n", log.c_str());
    if (log.find("TIMER_ACTIVE") == std::string::npos) {
        std::puts("FAIL owned visible game window never received bootstrap timer");
        return 1;
    }
    if (log.find("DISABLED") != std::string::npos) return 6;
    std::puts("PASS real DLL D3D focus-window callback + owned-window timer dispatch; absent engine waits without disabling");
    return 0;
}
