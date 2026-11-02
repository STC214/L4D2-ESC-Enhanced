#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cassert>
#include <cstdio>
#include <cstring>

class Contract {
public:
    virtual ~Contract() = default;
    virtual unsigned int Interface() = 0;
    virtual const char* Name() = 0;
    virtual const char* Version() = 0;
};

int wmain(int count, wchar_t** arguments) {
    assert(count == 2);
    const HMODULE module = LoadLibraryW(arguments[1]);
    assert(module);
    using Factory = Contract* (__cdecl*)();
    auto factory = reinterpret_cast<Factory>(GetProcAddress(module, "GetL4NPluginInstance"));
    assert(factory);
    Contract* plugin = factory();
    assert(plugin && plugin == factory() && plugin->Interface() == 1);
    assert(!std::strcmp(plugin->Name(), "CSP numbered spray selector prototype"));
    assert(!std::strcmp(plugin->Version(), "0.2.3"));
    FreeLibrary(module);
    std::puts("PASS actual x86 CSPSelector DLL loaded; L4N ABI v1 singleton/export/name/version; no launch callback invoked");
}
