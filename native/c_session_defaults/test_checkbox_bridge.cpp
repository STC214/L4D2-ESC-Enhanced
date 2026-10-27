#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include "checkbox_bridge.h"

static int original_calls = 0, writes = 0, resets = 0, active_slot = 0;
static bool reject = false;
static bool change_flags = false;
static ULONGLONG now = 0;
static ULONGLONG WINAPI Clock() { return now; }
static std::string last_log;
static void Log(const char* text) { last_log = text; }
static int __cdecl Slot() { return active_slot; }
static bool __fastcall Selected(void* object, void*) { return (static_cast<unsigned char*>(object)[0x1ac] & 128) != 0; }
static CvarPrefix* Var(void* object) {
    return *reinterpret_cast<CvarPrefix**>(static_cast<unsigned char*>(object) + 0x224 + active_slot * 8);
}
static void __fastcall Original(void*, void*) { ++original_calls; }
static void __fastcall Apply(void* object, void*) {
    ++writes;
    static_cast<unsigned char*>(object)[0x240] = Selected(object, nullptr) ? 1 : 0;
    if (!reject) Var(object)->int_value = Selected(object, nullptr) ? 1 : 0;
    if (change_flags) Var(object)->base.flags ^= 1;
}
static void __fastcall Reset(void* object, void*) {
    ++resets;
    static_cast<unsigned char*>(object)[0x1ac] = Var(object)->int_value ? 128 : 0;
}
static DWORD WINAPI OtherThread(void* object) {
    reinterpret_cast<CheckboxBridge::Handler>(CheckboxBridge::module + CheckboxBridge::EventRva)(object);
    return 0;
}

int main() {
    auto image = static_cast<unsigned char*>(VirtualAlloc(nullptr, 0x230000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    CheckboxBridge::clock = Clock;
    assert(image);
    std::memcpy(image + CheckboxBridge::EventRva, CheckboxBridge::Prefix, 5);
    image[CheckboxBridge::EventRva + 5] = 0x5e; // pop esi after the copied prologue
    CheckboxBridge::Jump(image + CheckboxBridge::EventRva + 6, reinterpret_cast<void*>(&Original));
    CheckboxBridge::Jump(image + 0x4500, reinterpret_cast<void*>(&Apply));
    CheckboxBridge::Jump(image + 0x4320, reinterpret_cast<void*>(&Reset));
    CheckboxBridge::Jump(image + 0x87a30, reinterpret_cast<void*>(&Slot));
    auto table = reinterpret_cast<void**>(image + 0x15f674);
    table[0x400 / 4] = reinterpret_cast<void*>(&Selected);
    DWORD old = 0;
    assert(VirtualProtect(image, 0x230000, PAGE_EXECUTE_READ, &old));
    assert(CheckboxBridge::Install(reinterpret_cast<HMODULE>(image), Log));
    assert(CheckboxBridge::Install(reinterpret_cast<HMODULE>(image), Log));
    for (const char* name : CheckboxBridge::Names) {
        unsigned char object[0x244]{};
        *reinterpret_cast<void***>(object) = table;
        char field[128]{};
        std::snprintf(field, sizeof(field), "C_ESC_BOOL_%s", name);
        *reinterpret_cast<const char**>(object + 0x4c) = field;
        CvarPrefix var{};
        var.base.name = name;
        var.base.flags = 0x2000;
        *reinterpret_cast<CvarPrefix**>(object + 0x224) = &var;
        auto event = reinterpret_cast<CheckboxBridge::Handler>(image + CheckboxBridge::EventRva);
        const int initial_writes = writes;
        event(object); // initial UI refresh, not a user change
        assert(writes == initial_writes);
        object[0x1ac] = 128;
        event(object);
        assert(var.int_value == 1 && writes == initial_writes + 1 && var.base.flags == 0x2000);
        assert(last_log.find("CHECKBOX_COMMIT_VERIFIED") != std::string::npos);
        event(object); // repeated notification must not re-submit
        assert(writes == initial_writes + 1);
        object[0x1ac] = 0;
        event(object);
        assert(var.int_value == 0 && writes == initial_writes + 2);
        reject = true;
        object[0x1ac] = 128;
        event(object);
        assert(var.int_value == 0 && object[0x1ac] == 128 && resets == 0);
        assert(last_log.find("CHECKBOX_COMMIT_PENDING") != std::string::npos);
        event(object);
        assert(writes == initial_writes + 3); // pending notification must not requeue
        now += 1001;
        CheckboxBridge::PollPending();
        assert(last_log.find("CHECKBOX_COMMIT_TIMEOUT") != std::string::npos);
        object[0x1ac] = 0; // native Paint's actual-value synchronization
        reject = false;
        const int before_invalid = writes;
        *reinterpret_cast<const char**>(object + 0x4c) = "OtherOptionsCheckbox";
        object[0x1ac] = 128;
        event(object);
        assert(writes == before_invalid);
        *reinterpret_cast<const char**>(object + 0x4c) = field;
        var.base.name = "unrelated_variable";
        event(object);
        assert(writes == before_invalid);
        var.base.name = name;
        active_slot = -1;
        event(object);
        active_slot = 4;
        event(object);
        assert(writes == before_invalid);
        active_slot = 0;
        HANDLE thread = CreateThread(nullptr, 0, OtherThread, object, 0, nullptr);
        assert(thread && WaitForSingleObject(thread, 3000) == WAIT_OBJECT_0);
        CloseHandle(thread);
        assert(writes == before_invalid); // foreign thread forwards native only
    }
    assert(original_calls == 110 && writes == 30 && resets == 0);
    // The GameUI template has four ConVarRef pairs. Exercise every valid slot
    // with distinct parents: a slot-0-only fake setter would hide routing bugs.
    for (active_slot = 0; active_slot < 4; ++active_slot) {
        unsigned char object[0x244]{};
        *reinterpret_cast<void***>(object) = table;
        *reinterpret_cast<const char**>(object + 0x4c) = "C_ESC_BOOL_mat_fullbright";
        CvarPrefix variables[4]{};
        for (int slot = 0; slot < 4; ++slot) {
            variables[slot].base.name = "mat_fullbright";
            variables[slot].base.flags = 0x2000;
            variables[slot].int_value = slot == active_slot ? 0 : 1;
            *reinterpret_cast<CvarPrefix**>(object + 0x224 + slot * 8) = &variables[slot];
        }
        auto event = reinterpret_cast<CheckboxBridge::Handler>(image + CheckboxBridge::EventRva);
        const int before = writes;
        event(object);
        assert(writes == before);
        object[0x1ac] = 128;
        event(object);
        assert(variables[active_slot].int_value == 1 && writes == before + 1);
        event(object);
        assert(writes == before + 1);
        object[0x1ac] = 0;
        event(object);
        assert(variables[active_slot].int_value == 0 && writes == before + 2);
        for (int slot = 0; slot < 4; ++slot) {
            assert(variables[slot].int_value == (slot == active_slot ? 0 : 1));
            assert(variables[slot].base.flags == 0x2000);
        }
    }
    active_slot = 0;
    assert(original_calls == 126 && writes == 38 && resets == 0);
    // A material-system setter can return before applying the render command.
    // Confirmation must wait, survive panel destruction and never re-submit.
    CvarPrefix delayed{};
    delayed.base.name = "mat_fullbright";
    delayed.base.flags = 0x2000;
    unsigned char object[0x244]{};
    *reinterpret_cast<void***>(object) = table;
    *reinterpret_cast<const char**>(object + 0x4c) = "C_ESC_BOOL_mat_fullbright";
    *reinterpret_cast<CvarPrefix**>(object + 0x224) = &delayed;
    auto event = reinterpret_cast<CheckboxBridge::Handler>(image + CheckboxBridge::EventRva);
    reject = true; // hold the simulated queued command until a later frame
    object[0x1ac] = 128;
    event(object);
    assert(last_log.find("CHECKBOX_COMMIT_PENDING") != std::string::npos && resets == 0);
    const int before_refresh = writes;
    object[0x1ac] = 0;
    object[0x240] = 0; // native Paint synchronizes both from the actual value
    event(object);
    assert(writes == before_refresh && CheckboxBridge::pending[6][0].wanted == 1);
    now += 150;
    delayed.int_value = 1; // render queue accepted it
    CheckboxBridge::PollPending();
    assert(last_log.find("CHECKBOX_COMMIT_VERIFIED") != std::string::npos);
    assert(last_log.find("deferred=1") != std::string::npos);
    object[0x1ac] = 128;
    object[0x240] = 1; // next native Paint reflects the accepted render value
    // Rapid on/off: off must cancel an outstanding on even if current value
    // is still off. Both commands are queued once, final intent is confirmed.
    delayed.int_value = 0;
    event(object);
    const int queued = writes;
    object[0x1ac] = 0;
    event(object);
    assert(writes == queued + 1);
    now += 150;
    CheckboxBridge::PollPending();
    assert(last_log.find("requested=0 actual=0") != std::string::npos);
    // Pending entries retain no object pointer; unreadable/dead CVar fails closed.
    object[0x1ac] = 128;
    event(object);
    auto& dead = CheckboxBridge::pending[6][0];
    assert(dead.var == &delayed);
    dead.var = reinterpret_cast<CvarPrefix*>(1);
    now += 150;
    CheckboxBridge::PollPending();
    assert(last_log.find("actual=-1") != std::string::npos && !dead.var);
    reject = false;
    change_flags = true;
    event(object);
    assert(resets == 1 && last_log.find("CHECKBOX_COMMIT_FAILED") != std::string::npos);
    assert(last_log.find("flags unchanged=0") != std::string::npos);
    change_flags = false;
    assert(CheckboxBridge::Remove());
    assert(std::memcmp(image + CheckboxBridge::EventRva, CheckboxBridge::Prefix, 5) == 0);
    assert(VirtualProtect(image, 0x230000, PAGE_READWRITE, &old));
    image[CheckboxBridge::EventRva] = 0xcc;
    assert(VirtualProtect(image, 0x230000, PAGE_EXECUTE_READ, &old));
    assert(!CheckboxBridge::Install(reinterpret_cast<HMODULE>(image), Log));
    VirtualFree(image, 0, MEM_RELEASE);
    assert(!CheckboxBridge::Readable(nullptr, 1));
    std::puts("PASS actual x86 hook/trampoline/unhook; all 10 checkbox bindings commit both ways, readback/reject/reset, no refresh writes, unrelated controls unchanged; four active slots isolated");
    std::puts("PASS deferred render commit confirmation, no premature Reset, timeout without retries, rapid on/off cancellation, dead CVar pointer rejection");
}
