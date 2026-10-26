#pragma once
#include <cstdint>
#include <cmath>
#include <string>

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

// Separate from connection defaults: each playable map arms exactly one ESC.
// No slider bound/cvar enforcement runs after that one event.
class FirstEscState {
public:
    bool Update(bool connected, bool active, std::uintptr_t channel, float age,
                const char* level, bool escape, bool background = false,
                bool playback = false) {
        if (!connected) {
            channel_ = 0;
            age_ = -1.0f;
            active_ = false;
            applied_ = false;
            level_.clear();
            return false;
        }
        // Loading must be observed even while channel/level data is absent.
        // An active frame with missing metadata must NOT re-arm user defaults.
        if (!active) {
            active_ = false;
            return false;
        }
        if (!channel || !std::isfinite(age) || age < 0 || !level || !*level) return false;
        if (channel != channel_ || (age_ >= 0.0f && age + 0.1f < age_)) {
            active_ = false;
            applied_ = false;
        }
        channel_ = channel;
        age_ = age;
        if (background || playback) {
            active_ = false;
            return false;
        }
        if (!active_ || level_ != level) applied_ = false;
        active_ = true;
        level_ = level;
        if (!escape || applied_) return false;
        applied_ = true;
        return true;
    }

private:
    std::uintptr_t channel_ = 0;
    float age_ = -1.0f;
    bool active_ = false;
    bool applied_ = false;
    std::string level_;
};
