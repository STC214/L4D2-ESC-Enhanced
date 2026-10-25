#pragma once
#include <cstdint>
#include <cmath>

// Independent of rendering and menu visibility. Only a new connection arms reset.
class SessionState {
public:
    bool Update(bool connected, bool active, std::uintptr_t channel, float age,
                bool background = false, bool playback = false) {
        if (!connected) {
            applied_ = false;
            channel_ = 0;
            age_ = -1.0f;
            return false;
        }
        if (background || playback || channel == 0 || !std::isfinite(age) || age < 0.0f) return false;
        if (channel != channel_ || (age_ >= 0.0f && age + 0.1f < age_)) {
            channel_ = channel;
            applied_ = false;
        }
        age_ = age;
        // A same-connection loading screen/map transition does not re-arm.
        if (!active || applied_) return false;
        applied_ = true;
        return true;
    }

private:
    bool applied_ = false;
    std::uintptr_t channel_ = 0;
    float age_ = -1.0f;
};
