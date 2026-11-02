#include "viewport.h"
#include <cassert>

struct Panel { int x, y, w, h; Panel* parent = nullptr; };
static int sets = 0;
static void __fastcall GetPosition(void* pointer, void*, int* x, int* y) { auto p = static_cast<Panel*>(pointer); *x = p->x; *y = p->y; }
static void __fastcall GetSize(void* pointer, void*, int* w, int* h) { auto p = static_cast<Panel*>(pointer); *w = p->w; *h = p->h; }
static void* __fastcall MockParent(void* pointer, void*) { return static_cast<Panel*>(pointer)->parent; }
static void __fastcall SetPosition(void* pointer, void*, int x, int y) { auto p = static_cast<Panel*>(pointer); p->x = x; p->y = y; ++sets; }

int main() {
    const CSPViewport::API api{reinterpret_cast<CSPViewport::Pair>(&GetPosition), reinterpret_cast<CSPViewport::Pair>(&GetSize),
                              reinterpret_cast<CSPViewport::Parent>(&MockParent), reinterpret_cast<CSPViewport::Position>(&SetPosition)};
    for (const auto size : {std::pair<int,int>{640,480}, {1280,720}, {1920,1080}, {2560,1440}, {3440,1440}}) {
        const int w = size.second * 450 / 480, h = size.second * 330 / 480;
        Panel p{size.first - 10, size.second / 2, w, h};
        assert(CSPViewport::Place(&p, size.first, size.second, api) == 1);
        assert(p.x >= 8 && p.y >= 8 && p.x + p.w <= size.first - 8 && p.y + p.h <= size.second - 8);
        assert(CSPViewport::Place(&p, size.first, size.second, api) == 0);
    }
    Panel parent{50, 20, 1280, 720};
    Panel p{908, 360, 675, 495, &parent};
    assert(CSPViewport::Place(&p, 1280, 720, api) == 1);
    assert(p.x + 50 == 597 && p.y + 20 == 217);
    Panel negative{-200, -300, 200, 100, &parent};
    assert(CSPViewport::Place(&negative, 1280, 720, api) == 1 && negative.x == -42 && negative.y == -12);
    Panel huge{0,0,2000,2000};
    const int before = sets;
    assert(CSPViewport::Place(&huge, 1280, 720, api) == -1 && sets == before);
    p.parent = &p;
    assert(CSPViewport::Place(&p, 1280, 720, api) == -1);
    for (int number = 1; number <= 40; ++number) {
        char name[64]{};
        std::snprintf(name, sizeof(name), "FlmCSPConfirm%03d", number);
        assert(CSPViewport::Name(name));
    }
    for (const char* name : {"FlmCSPPage1", "FlmCSPPage2", "FlmCSPPage3", "FlmCSPPage4"}) assert(CSPViewport::Name(name));
    for (const char* name : {"FlmOptionsFlyout", "FlmSpraypaint", "FlmCSPPage5", "FlmCSPPage1evil", "FlmCSPConfirm041", "FlmCSPConfirm000"}) assert(!CSPViewport::Name(name));
    std::puts("PASS popup bounds at five viewport sizes, parent offsets, negative positions, idempotence, oversized/cycle rejection and exact CSP-only names");
}
