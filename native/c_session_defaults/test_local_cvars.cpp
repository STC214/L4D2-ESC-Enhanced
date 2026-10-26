#include "local_cvars.h"
#include <cassert>
#include <cstdio>

class FakeBase {
public:
    virtual ~FakeBase() = default;
    void* next = nullptr;
    bool registered = true;
    const char* name = "fog_enable";
    const char* help = "fixture";
    int flags = 1 << 14;
};
static_assert(sizeof(FakeBase) == sizeof(CommandPrefix));

class Fake final : public FakeBase, public LocalIConVar {
public:
    Fake* parent = this;
    const char* default_value = "1";
    char* string_value = nullptr;
    int string_length = 0;
    float float_value = 1;
    int int_value = 1;
    void SetValue(const char*) override {}
    void SetValue(float) override {}
    void SetValue(int value) override { int_value = value; }
    void SetColor(unsigned int) override {}
    const char* GetName() const override { return name; }
    const char* GetBaseName() const override { return name; }
    bool IsFlagSet(int flag) const override { return (flags & flag) != 0; }
    int GetSplitScreenPlayerSlot() const override { return 0; }
};

int main() {
    Fake fog;
    auto raw = reinterpret_cast<CvarPrefix*>(&fog);
    assert(raw->int_value == 1 && raw->parent == raw);
    assert(SetCheckedLocalInt(raw, "fog_enable", 0));
    assert(fog.int_value == 0 && fog.flags == (1 << 14));
    assert(!SetCheckedLocalInt(raw, "different_name", 1));
    assert(fog.int_value == 0);
    fog.flags |= 1 << 13;
    assert(!SetCheckedLocalInt(raw, "fog_enable", 1));
    assert(fog.int_value == 0);
    assert(!SetCheckedLocalInt(nullptr, "fog_enable", 0));
    std::puts("PASS pinned x86 ConVar prefix, named local setter/readback, unchanged flags, replicated/name/null rejection");
    return 0;
}
