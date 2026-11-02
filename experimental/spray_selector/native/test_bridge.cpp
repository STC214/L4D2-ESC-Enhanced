#include "bridge.h"
#include <cassert>

static int chosen = 0, forwarded = 0;
static bool apply_success = true;
static const char* passed = nullptr;
static void* passed_object = nullptr;

static bool Apply(int number) { chosen = number; return apply_success; }
static void __fastcall Forward(void* object, void*, const char* command) {
    ++forwarded;
    passed = command;
    passed_object = object;
}
// The production detour copies this complete nine-byte prologue, no relative call.
__declspec(naked) static void Native() {
    __asm {
        push ebp
        mov ebp, esp
        sub esp, 12ch
        mov esp, ebp
        pop ebp
        ret 4
    }
}

int main() {
    CSP::owner = GetCurrentThreadId();
    CSP::original = reinterpret_cast<CSP::Handler>(&Forward);
    CSP::apply = Apply;
    int object = 0;
    for (int number = 1; number <= 40; ++number) {
        char command[64]{};
        std::snprintf(command, sizeof(command), "CSP_TEST_APPLY_%03d", number);
        CSP::Dispatch(&object, command);
        assert(chosen == number && passed_object == &object && !std::strcmp(passed, "Back"));
    }
    const int calls = forwarded;
    for (const char* bad : {"CSP_TEST_APPLY_000", "CSP_TEST_APPLY_041", "CSP_TEST_APPLY_17",
                           "CSP_TEST_APPLY_017;quit", "CSP_TEST_APPLY_017\n", "CSP_TEST_APPLY_x17"}) {
        chosen = 0;
        CSP::Dispatch(&object, bad);
        assert(!chosen && forwarded == calls);
    }
    CSP::Dispatch(&object, "FlmCSPPage2");
    assert(forwarded == calls + 1 && !std::strcmp(passed, "FlmCSPPage2"));
    apply_success = false;
    CSP::Dispatch(&object, "CSP_TEST_APPLY_017");
    assert(forwarded == calls + 1 && chosen == 17); // Failed readback sends no extra Back command.
    chosen = 0;
    CSP::owner = 0;
    CSP::Dispatch(&object, "CSP_TEST_APPLY_017");
    assert(!chosen && forwarded == calls + 2);
    apply_success = true;
    CSP::original = nullptr;
    assert(CSP::Install(reinterpret_cast<unsigned char*>(&Native), GetCurrentThreadId(), Apply));
    auto handler = reinterpret_cast<CSP::Handler>(&Native);
    chosen = 0;
    handler(&object, "CSP_TEST_APPLY_040");
    assert(chosen == 40);
    handler(&object, "Unrelated"); // Real trampoline preserves thiscall and ret 4.
    assert(CSP::RemoveForTest());
    assert(!std::memcmp(reinterpret_cast<void*>(&Native), CSP::Prologue, sizeof(CSP::Prologue)));
    assert(!CSP::Install(nullptr, GetCurrentThreadId(), Apply));
    std::puts("PASS 40 apply IDs; malformed/unknown/thread rejection; failed readback sends no Back; unrelated routing; actual x86 detour/trampoline/restoration");
}
