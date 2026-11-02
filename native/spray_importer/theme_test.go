package main

import (
	"math"
	"testing"
	"unsafe"
)

func TestStudioGeometryBounds(t *testing.T) {
	for _, size := range [][2]int{{904, 611}, {964, 661}, {1264, 741}, {1904, 1001}} {
		w, h := size[0], size[1]
		p := studioGeometry(w, h)
		all := append([]placement{p.List, p.Path, p.Status, p.Preview}, p.Labels[:]...)
		all = append(all, p.Buttons[:]...)
		for _, r := range all {
			if r.X < 0 || r.Y < 0 || r.W <= 0 || r.H <= 0 || r.X+r.W > w || r.Y+r.H > h {
				t.Fatal(size, r)
			}
		}
		if p.Preview.W != p.Preview.H || p.Preview.X+p.Preview.W >= p.Buttons[0].X {
			t.Fatal("preview/button overlap", size)
		}
		if p.List.Y+p.List.H >= p.Status.Y {
			t.Fatal("list/status overlap", size)
		}
		for i := 1; i < len(p.Buttons); i++ {
			if p.Buttons[i-1].Y+p.Buttons[i-1].H >= p.Buttons[i].Y {
				t.Fatal("buttons overlap")
			}
		}
	}
}

func TestStudioTextContrast(t *testing.T) {
	luminance := func(c uintptr) float64 {
		var channels [3]float64
		for i := range channels {
			v := float64((c>>uint(8*i))&255) / 255
			if v <= .04045 {
				channels[i] = v / 12.92
			} else {
				channels[i] = math.Pow((v+.055)/1.055, 2.4)
			}
		}
		return .2126*channels[0] + .7152*channels[1] + .0722*channels[2]
	}
	for _, pair := range [][2]uintptr{{studioText, studioCard}, {studioMuted, studioCard}, {studioBG, studioAccent}, {studioBG, rgb(31, 181, 157)}, {studioText, rgb(39, 60, 88)}} {
		a, b := luminance(pair[0]), luminance(pair[1])
		if a < b {
			a, b = b, a
		}
		if (a+.05)/(b+.05) < 4.5 {
			t.Fatal("insufficient text contrast", pair)
		}
	}
}

func TestDrawItemNativeABI(t *testing.T) {
	var item drawItem
	if unsafe.Sizeof(item) != 64 || unsafe.Offsetof(item.Window) != 24 || unsafe.Offsetof(item.DC) != 32 || unsafe.Offsetof(item.Area) != 40 || unsafe.Offsetof(item.Data) != 56 {
		t.Fatal("DRAWITEMSTRUCT x64 ABI mismatch")
	}
}
