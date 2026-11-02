#include "apply.h"
#include <cassert>

class Base {
public:
    virtual ~Base() = default;
    void* next = nullptr;
    bool registered = true;
    const char* name = "cl_logofile";
    const char* help = "fixture";
    int flags = 128;
};

struct Color32 { unsigned int value; };
// Match all four native overloads, not the older three-overload C helper shim.
class EngineIConVar {
public:
    virtual void SetValue(const char*) = 0;
    virtual void SetValue(float) = 0;
    virtual void SetValue(int) = 0;
    virtual void SetValue(Color32) = 0;
    virtual const char* GetName() const = 0;
    virtual const char* GetBaseName() const = 0;
    virtual bool IsFlagSet(int) const = 0;
    virtual int GetSplitScreenPlayerSlot() const = 0;
};

class Variable final : public Base, public EngineIConVar {
public:
    Variable* parent = this;
    const char* default_value = "";
    char* string_value = storage;
    int string_length = 256;
    float float_value = 0;
    int int_value = 0;
    char storage[256]{};
    bool accept_write = true;
    int writes = 0;
    int float_writes = 0;
    void SetValue(const char* value) override { ++writes; if (accept_write) strcpy_s(storage, value); }
    void SetValue(float) override { ++float_writes; }
    void SetValue(int) override { assert(false); }
    void SetValue(Color32) override { assert(false); }
    const char* GetName() const override { return name; }
    const char* GetBaseName() const override { return name; }
    bool IsFlagSet(int value) const override { return (flags & value) != 0; }
    int GetSplitScreenPlayerSlot() const override { return 0; }
};

int main() {
    Variable variable;
    auto value = reinterpret_cast<CvarPrefix*>(&variable);
    auto legacy = reinterpret_cast<LocalIConVar*>(reinterpret_cast<char*>(value) + sizeof(CommandPrefix));
    legacy->SetValue("materials/vgui/logos/csp_test/test_017.vtf");
    assert(variable.float_writes == 1 && variable.writes == 0); // Reproduce the old ABI error without a game write.
    for (int number = 1; number <= 40; ++number) {
        assert(CSP::ApplyValue(value, number));
        char expected[128]{};
        std::snprintf(expected, sizeof(expected), "materials/vgui/logos/csp_test/test_%03d.vtf", number);
        assert(!std::strcmp(variable.storage, expected) && variable.flags == 128);
        assert(variable.float_writes == 1);
    }
    const int before = variable.writes;
    assert(!CSP::ApplyValue(nullptr, 17));
    assert(!CSP::ApplyValue(value, 0) && !CSP::ApplyValue(value, 41));
    variable.name = "other";
    assert(!CSP::ApplyValue(value, 17));
    variable.name = "cl_logofile";
    variable.flags |= 1 << 13;
    assert(!CSP::ApplyValue(value, 17));
    variable.flags = 128 | (1 << 14);
    assert(!CSP::ApplyValue(value, 17));
    variable.flags = 128;
    assert(variable.writes == before);
    variable.accept_write = false;
    assert(!CSP::ApplyValue(value, 17));
    assert(variable.writes == before + 1 && variable.flags == 128);
    variable.parent = nullptr;
    assert(!CSP::ApplyValue(value, 17));
    std::puts("PASS legacy shim reproduces wrong float slot; native four-overload ABI uses string slot 3 for all 40 IDs; bounds/name/null/replicated/cheat rejection and readback failures");
}
