package main

import (
	"fmt"
	"strings"
	"syscall"
	"unsafe"
)

type placement struct{ X, Y, W, H int }
type studioLayout struct {
	Labels                      [6]placement
	Buttons                     [6]placement
	List, Path, Status, Preview placement
}

func studioGeometry(w, h int) studioLayout {
	var p studioLayout
	p.Labels = [6]placement{{40, 26, w - 80, 34}, {40, 118, w - 330, 20}, {304, 210, w - 330, 26}, {w - 262, 127, 218, 44}, {40, 66, w - 80, 22}, {36, 210, 218, 24}}
	p.List = placement{32, 246, 221, h - 338}
	p.Path = placement{44, 145, w - 340, 24}
	p.Status = placement{38, h - 57, w - 76, 38}
	size := min(280, h-340, w-572)
	p.Preview = placement{304, 246, size, size}
	for i := range p.Buttons {
		p.Buttons[i] = placement{w - 236, 246 + i*44, 212, 36}
	}
	return p
}

func rgb(r, g, b uint8) uintptr { return uintptr(r) | uintptr(g)<<8 | uintptr(b)<<16 }

var studioBG = rgb(10, 16, 29)
var studioCard = rgb(17, 28, 48)
var studioBorder = rgb(34, 49, 72)
var studioText = rgb(226, 235, 246)
var studioMuted = rgb(143, 161, 185)
var studioAccent = rgb(40, 211, 182)
var studioBrush, editBrush uintptr
var titleFont, captionFont, smallFont uintptr
var previewArea placement
var importedCount int
var studioPaints int
var paintedActions = map[uint32]bool{}
var paintedList bool

func uiFont(size, weight int) uintptr {
	h, _, _ := gdi.NewProc("CreateFontW").Call(uintptr(int64(-px(size))), 0, 0, 0, uintptr(weight), 0, 0, 0, 1, 0, 0, 5, 0, uintptr(unsafe.Pointer(utf("Microsoft YaHei UI"))))
	return h
}

func initStudio() func() {
	studioBrush, _, _ = gdi.NewProc("CreateSolidBrush").Call(studioCard)
	editBrush, _, _ = gdi.NewProc("CreateSolidBrush").Call(rgb(24, 39, 61))
	titleFont, captionFont, smallFont = uiFont(26, 700), uiFont(16, 600), uiFont(13, 400)
	return func() {
		for _, h := range []uintptr{studioBrush, editBrush, titleFont, captionFont, smallFont} {
			if h != 0 {
				gdi.NewProc("DeleteObject").Call(h)
			}
		}
	}
}

func fillArea(dc uintptr, r rect, colour uintptr) {
	brush, _, _ := gdi.NewProc("CreateSolidBrush").Call(colour)
	call("FillRect", dc, uintptr(unsafe.Pointer(&r)), brush)
	gdi.NewProc("DeleteObject").Call(brush)
}

func roundArea(dc uintptr, r rect, colour, border uintptr, radius int) {
	brush, _, _ := gdi.NewProc("CreateSolidBrush").Call(colour)
	pen, _, _ := gdi.NewProc("CreatePen").Call(0, 1, border)
	oldBrush, _, _ := gdi.NewProc("SelectObject").Call(dc, brush)
	oldPen, _, _ := gdi.NewProc("SelectObject").Call(dc, pen)
	gdi.NewProc("RoundRect").Call(dc, uintptr(r.Left), uintptr(r.Top), uintptr(r.Right), uintptr(r.Bottom), uintptr(px(radius)), uintptr(px(radius)))
	gdi.NewProc("SelectObject").Call(dc, oldPen)
	gdi.NewProc("SelectObject").Call(dc, oldBrush)
	gdi.NewProc("DeleteObject").Call(pen)
	gdi.NewProc("DeleteObject").Call(brush)
}

func logicalRect(p placement) rect {
	return rect{int32(px(p.X)), int32(px(p.Y)), int32(px(p.X + p.W)), int32(px(p.Y + p.H))}
}

func studioPaint(dc uintptr) {
	var r rect
	call("GetClientRect", window, uintptr(unsafe.Pointer(&r)))
	w, h := int(float64(r.Right)/scale), int(float64(r.Bottom)/scale)
	studioScene(dc, w, h)
}

func studioScene(dc uintptr, w, h int) {
	studioPaints++
	r := logicalRect(placement{0, 0, w, h})
	fillArea(dc, r, studioBG)
	for _, p := range []placement{{20, 16, w - 40, 82}, {20, 112, w - 40, 68}, {20, 196, 245, h - 276}, {282, 196, w - 302, h - 276}, {20, h - 66, w - 40, 50}} {
		roundArea(dc, logicalRect(p), studioCard, studioBorder, 16)
	}
	roundArea(dc, logicalRect(placement{36, 139, w - 324, 34}), rgb(24, 39, 61), studioBorder, 10)
	roundArea(dc, logicalRect(placement{previewArea.X - 4, previewArea.Y - 4, previewArea.W + 8, previewArea.H + 8}), rgb(9, 17, 31), studioBorder, 12)
	fillArea(dc, logicalRect(placement{22, 32, 3, 44}), studioAccent)
}

func drawText(dc uintptr, value string, r rect, colour, face uintptr, center bool) {
	old, _, _ := gdi.NewProc("SelectObject").Call(dc, face)
	gdi.NewProc("SetTextColor").Call(dc, colour)
	gdi.NewProc("SetBkMode").Call(dc, 1)
	flags := uintptr(4 | 32 | 0x8000)
	if center {
		flags |= 1
	}
	call("DrawTextW", dc, uintptr(unsafe.Pointer(utf(value))), ^uintptr(0), uintptr(unsafe.Pointer(&r)), flags)
	gdi.NewProc("SelectObject").Call(dc, old)
}

// Win32 DRAWITEMSTRUCT is supplied by the owner-draw control notification.
type drawItem struct {
	Kind, ID, Item, Action, State uint32
	Window, DC                    uintptr
	Area                          rect
	Data                          uintptr
}

func studioDraw(item *drawItem) bool {
	if item.Kind == 4 { // ODT_BUTTON
		paintedActions[item.ID] = true
		studioAction(item.DC, item.Area, item.ID, item.State, windowText(item.Window))
		return true
	}
	if item.Kind == 2 { // ODT_LISTBOX
		paintedList = true
		if item.Item == 0xffffffff {
			return true
		}
		base := studioCard
		if item.State&1 != 0 {
			base = rgb(22, 62, 68)
		}
		fillArea(item.DC, item.Area, base)
		r := item.Area
		r.Left += int32(px(8))
		r.Right = r.Left + int32(px(32))
		drawText(item.DC, fmt.Sprintf("%02d", item.Item+1), r, studioAccent, captionFont, true)
		n := send(item.Window, 0x18a, uintptr(item.Item), 0)
		if n > 32768 {
			return true
		}
		buffer := make([]uint16, n+1)
		send(item.Window, 0x189, uintptr(item.Item), uintptr(unsafe.Pointer(&buffer[0])))
		title := syscall.UTF16ToString(buffer)
		if parts := strings.SplitN(title, "    ", 2); len(parts) == 2 {
			title = parts[1]
		}
		r.Left += int32(px(42))
		r.Right = item.Area.Right - int32(px(8))
		drawText(item.DC, title, r, studioText, smallFont, false)
		if item.State&1 != 0 {
			r = item.Area
			r.Right = r.Left + int32(px(3))
			fillArea(item.DC, r, studioAccent)
		}
		return true
	}
	return false
}

func studioAction(dc uintptr, area rect, id, state uint32, title string) {
	base, ink := rgb(29, 45, 68), studioText
	if id == 106 || id == 103 {
		base, ink = studioAccent, studioBG
	}
	if state&1 != 0 {
		base = rgb(39, 60, 88)
		if id == 106 || id == 103 {
			base = rgb(31, 181, 157)
		}
	}
	if state&4 != 0 {
		base, ink = rgb(24, 35, 52), studioMuted
	}
	border := studioBorder
	if state&16 != 0 {
		border = studioAccent
	}
	roundArea(dc, area, base, border, 10)
	drawText(dc, title, area, ink, font, true)
}

func studioControlColour(dc, hwnd uintptr, edit bool) uintptr {
	gdi.NewProc("SetBkMode").Call(dc, 1)
	colour := studioText
	if hwnd == labels[1] || hwnd == labels[3] || hwnd == labels[4] || hwnd == statusLabel {
		colour = studioMuted
	}
	gdi.NewProc("SetTextColor").Call(dc, colour)
	if edit {
		gdi.NewProc("SetBkColor").Call(dc, rgb(24, 39, 61))
		return editBrush
	}
	gdi.NewProc("SetBkColor").Call(dc, studioCard)
	return studioBrush
}

func darkTitlebar() {
	one := uint32(1)
	syscall.NewLazyDLL("dwmapi.dll").NewProc("DwmSetWindowAttribute").Call(window, 20, uintptr(unsafe.Pointer(&one)), 4)
}
