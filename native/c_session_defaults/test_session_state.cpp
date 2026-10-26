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
    FirstEscState first;
    assert(!first.Update(false, false, 0, -1, "", true));
    assert(!first.Update(true, false, 1, 0, "map1", true)); // loading ESC ignored
    assert(!first.Update(true, true, 1, 1, "map1", false)); // entering alone never writes 150
    assert(first.Update(true, true, 1, 2, "map1", true));
    int manual_fov = 80;
    for (int press = 0; press < 100; ++press) {
        if (first.Update(true, true, 1, 3.0f + press, "map1", true)) manual_fov = 150;
    }
    assert(manual_fov == 80); // deliberately below 150: no locking/clamping
    assert(!first.Update(true, true, 1, 103, "map2", false));
    assert(first.Update(true, true, 1, 104, "map2", true)); // next chapter
    assert(!first.Update(true, false, 1, 105, "map2", true));
    assert(!first.Update(true, true, 1, 106, "map2", false));
    assert(first.Update(true, true, 1, 107, "map2", true)); // reload same map
    assert(first.Update(true, true, 2, 0, "map2", true)); // new room, same map
    assert(!first.Update(true, true, 2, 5, "map2", false));
    assert(first.Update(true, true, 2, 0, "map2", true)); // channel address reused
    assert(!first.Update(true, true, 2, 1, "map2", true));
    for (float age : invalid_ages) {
        assert(!first.Update(true, true, 2, age, "map2", true));
    }
    assert(!first.Update(true, true, 2, 2, "map2", true)); // invalid samples did not re-arm
    FirstEscState exclusions;
    assert(!exclusions.Update(true, true, 3, 0, "background01", true, true));
    assert(!exclusions.Update(true, true, 3, 1, "map1", true, false, true));
    assert(!exclusions.Update(true, true, 3, 2, "map1", false));
    assert(exclusions.Update(true, true, 3, 3, "map1", true));
    std::puts("PASS first ESC per map, next chapter/same-map reload/reconnect, 100 repeated ESC preserve manual FOV 80, background/demo/loading exclusions");
    std::puts("PASS initial join, 100 ESC cycles, same-session map load, reconnect, reused channel, background/demo exclusions, non-finite ages");
    return 0;
}
