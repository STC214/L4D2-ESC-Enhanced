#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cassert>
#include <cstdio>
#include <cstring>

// Only test the public L4N ABI/export. Do not invoke launch or engine methods.
class IL4NPluginV1 {
public:
    virtual ~IL4NPluginV1() = default;
    virtual unsigned int GetInterfaceVersion() = 0;
    virtual const char* GetName() = 0;
    virtual const char* GetVersion() = 0;
};

int wmain(int argc, wchar_t** argv) {
    assert(argc == 2);
    HMODULE module = LoadLibraryW(argv[1]);
    assert(module);
    using Factory = IL4NPluginV1*(*)();
    auto factory = reinterpret_cast<Factory>(GetProcAddress(module, "GetL4NPluginInstance"));
    assert(factory);
    IL4NPluginV1* plugin = factory();
    assert(plugin && plugin == factory());
    assert(plugin->GetInterfaceVersion() == 1);
    assert(std::strcmp(plugin->GetName(), "C session defaults") == 0);
    assert(std::strcmp(plugin->GetVersion(), "1.3.0") == 0);
    FreeLibrary(module);
    std::puts("PASS real x86 DLL loaded; L4N v1 export/singleton/version 1.3.0; no game launch side effects");
    return 0;
}
