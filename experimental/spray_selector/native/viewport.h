#pragma once
#include <windows.h>
#include <algorithm>
#include "apply.h"

namespace CSPViewport {
using Pair = void (__thiscall*)(void*, int*, int*);
using Parent = void* (__thiscall*)(void*);
using Position = void (__thiscall*)(void*, int, int);
using Logger = void (*)(const char*);
struct API { Pair get_position, get_size; Parent get_parent; Position set_position; };

inline bool Name(const char* value) {
    if (!CSP::Readable(value, 12)) return false;
    constexpr char page[] = "FlmCSPPage";
    if (!std::memcmp(value, page, sizeof(page) - 1))
        return value[sizeof(page)] == 0 && value[sizeof(page) - 1] >= '1' && value[sizeof(page) - 1] <= '4';
    constexpr char confirm[] = "FlmCSPConfirm";
    if (!CSP::Readable(value, sizeof(confirm) + 3) || std::memcmp(value, confirm, sizeof(confirm) - 1)) return false;
    const char* number = value + sizeof(confirm) - 1;
    if (number[3] || number[0] != '0' || number[1] < '0' || number[1] > '4' || number[2] < '0' || number[2] > '9') return false;
    const int id = (number[1] - '0') * 10 + number[2] - '0';
    return id >= 1 && id <= 40;
}

// All coordinates here are actual VGUI pixels, not RES design/proportional units.
inline int Place(void* panel, int width, int height, const API& api, Logger logger = nullptr) {
    int x = 0, y = 0, w = 0, h = 0;
    api.get_position(panel, &x, &y);
    api.get_size(panel, &w, &h);
    constexpr int margin = 8;
    if (w <= 0 || h <= 0 || width < w + margin * 2 || height < h + margin * 2) return -1;
    int parent_x = 0, parent_y = 0;
    void* parent = api.get_parent(panel);
    for (int depth = 0; parent; ++depth) {
        if (depth >= 32 || parent == panel || !CSP::Readable(parent, sizeof(void*))) return -1;
        int px = 0, py = 0;
        api.get_position(parent, &px, &py);
        parent_x += px;
        parent_y += py;
        parent = api.get_parent(parent);
    }
    const int wanted_x = (std::max)(margin, (std::min)(x + parent_x, width - w - margin)) - parent_x;
    const int wanted_y = (std::max)(margin, (std::min)(y + parent_y, height - h - margin)) - parent_y;
    if (wanted_x == x && wanted_y == y) return 0;
    api.set_position(panel, wanted_x, wanted_y);
    if (logger) {
        char message[240]{};
        std::snprintf(message, sizeof(message), "POPUP_CLAMPED: viewport=%dx%d size=%dx%d local=(%d,%d)->(%d,%d)",
                      width, height, w, h, x, y, wanted_x, wanted_y);
        logger(message);
    }
    return 1;
}

inline void Poll(unsigned char* module, HWND window, Logger logger) {
    if (!module || !IsWindow(window)) return;
    auto active = reinterpret_cast<void**>(module + 0x201578);
    if (!CSP::Readable(active, sizeof(void*))) return;
    auto panel = static_cast<unsigned char*>(*active);
    if (!CSP::Readable(panel, 0x50) || *reinterpret_cast<void**>(panel) != module + 0x16d4fc ||
        !Name(*reinterpret_cast<const char**>(panel + 0x4c))) return;
    RECT client{};
    if (!GetClientRect(window, &client)) return;
    const API api{reinterpret_cast<Pair>(module + 0xca580), reinterpret_cast<Pair>(module + 0xca5e0),
                  reinterpret_cast<Parent>(module + 0xca700), reinterpret_cast<Position>(module + 0xca530)};
    Place(panel, client.right - client.left, client.bottom - client.top, api, logger);
}
}
