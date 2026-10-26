#include "local_cvars.h"
#include "session_state.h"
#include <cassert>
#include <cstdio>
#include <initializer_list>

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
    for (const auto name : {"r_flashlightconstant", "r_flashlightfar"}) {
        Fake light;
        light.name = name;
        const int maximum = std::strcmp(name, "r_flashlightfar") == 0 ? 3000 : 1;
        assert(SetCheckedLocalInt(reinterpret_cast<CvarPrefix*>(&light), name, maximum));
        assert(light.int_value == maximum && light.flags == (1 << 14));
    }
    std::puts("PASS flashlight brightness 1 and reach 3000 use named setter with exact readback");
    FirstEscState once_per_map;
    Fake reach;
    reach.name = "r_flashlightfar";
    auto reach_raw = reinterpret_cast<CvarPrefix*>(&reach);
    assert(once_per_map.Update(true, true, 1, 0, "map1", true));
    assert(SetCheckedLocalInt(reach_raw, reach.name, 3000));
    reach.SetValue(1200); // User adjustment after initial defaults.
    for (int tick = 1; tick <= 100; ++tick) {
        if (once_per_map.Update(true, true, 1, static_cast<float>(tick), "map1", true))
            SetCheckedLocalInt(reach_raw, reach.name, 3000);
    }
    assert(reach.int_value == 1200);
    assert(once_per_map.Update(true, true, 1, 101, "map2", true));
    assert(SetCheckedLocalInt(reach_raw, reach.name, 3000));
    assert(reach.int_value == 3000);
    std::puts("PASS map defaults preserve manual reach 1200 for 100 ticks/ESC; next map resets 3000");
    FirstEscState fov_per_map;
    Fake cone;
    cone.name = "r_flashlightfov";
    auto cone_raw = reinterpret_cast<CvarPrefix*>(&cone);
    assert(!fov_per_map.Update(true, false, 1, 0, "map1", true));
    assert(fov_per_map.Update(true, true, 1, 1, "map1", true));
    assert(SetCheckedLocalInt(cone_raw, cone.name, 165));
    assert(cone.int_value == 165); // No ESC event required for map defaults.
    cone.SetValue(80);
    for (int tick = 2; tick <= 101; ++tick) {
        if (fov_per_map.Update(true, true, 1, static_cast<float>(tick), "map1", true))
            SetCheckedLocalInt(cone_raw, cone.name, 165);
    }
    assert(cone.int_value == 80);
    assert(fov_per_map.Update(true, true, 1, 102, "map2", true));
    assert(SetCheckedLocalInt(cone_raw, cone.name, 165));
    assert(cone.int_value == 165);
    std::puts("PASS map entry FOV 165 without ESC; manual 80 preserved for 100 ticks; next map resets 165");
    std::puts("PASS pinned x86 ConVar prefix, named local setter/readback, unchanged flags, replicated/name/null rejection");
    return 0;
}
