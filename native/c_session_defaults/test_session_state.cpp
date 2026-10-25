#include "session_state.h"
#include <cassert>
#include <cstdio>
#include <limits>

int main() {
    SessionState state;
    assert(!state.Update(false, false, 0, -1));
    assert(!state.Update(true, false, 1, 0));
    assert(state.Update(true, true, 1, 1));
    int user_value = 123;
    for (int esc = 0; esc < 100; ++esc) {
        if (state.Update(true, true, 1, 2.0f + esc)) user_value = 620;
    }
    assert(user_value == 123);
    assert(!state.Update(true, false, 1, 102));
    assert(!state.Update(true, true, 1, 103));
    assert(!state.Update(false, false, 0, -1));
    assert(state.Update(true, true, 1, 1)); // same address reused after disconnect
    assert(!state.Update(true, true, 1, 10));
    assert(state.Update(true, true, 1, 0)); // reconnect detected by connection age
    assert(state.Update(true, true, 2, 0)); // different connection
    SessionState excluded;
    assert(!excluded.Update(true, true, 3, 0, true));
    assert(!excluded.Update(true, true, 3, 0, false, true));
    assert(!excluded.Update(true, true, 0, 0));
    assert(excluded.Update(true, true, 3, 1));
    SessionState invalid;
    const float invalid_ages[] = {std::numeric_limits<float>::quiet_NaN(),
                                 std::numeric_limits<float>::infinity(), -1.0f};
    for (float age : invalid_ages) {
        if (invalid.Update(true, true, 4, age)) {
            std::puts("FAIL invalid connection age consumed first-join initialization");
            return 1;
        }
    }
    assert(invalid.Update(true, true, 4, 1));
    assert(!invalid.Update(true, true, 4, std::numeric_limits<float>::infinity()));
    assert(!invalid.Update(true, true, 4, 2));
    std::puts("PASS initial join, 100 ESC cycles, same-session map load, reconnect, reused channel, background/demo exclusions, non-finite ages");
    return 0;
}
