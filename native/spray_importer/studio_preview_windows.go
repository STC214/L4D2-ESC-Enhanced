package main

import (
	"fmt"
	"image"
	"image/color"
	"runtime"
	"unsafe"
)

// Render a client-area design preview into our own offscreen DIB. This does
// not capture the desktop or any other application and is not a live screenshot.
func renderStudioPreview(path string) error {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	scale = 1
	const w, h = 964, 661
	font = uiFont(16, 400)
	defer gdi.NewProc("DeleteObject").Call(font)
	closeStudio := initStudio()
	defer closeStudio()
	dc, _, _ := gdi.NewProc("CreateCompatibleDC").Call(0)
	if dc == 0 {
		return fmt.Errorf("preview DC unavailable")
	}
	defer gdi.NewProc("DeleteDC").Call(dc)
	info := bitmapInfo{Size: 40, Width: w, Height: -h, Planes: 1, Bits: 32}
	var pixels uintptr
	bitmap, _, _ := gdi.NewProc("CreateDIBSection").Call(dc, uintptr(unsafe.Pointer(&info)), 0, uintptr(unsafe.Pointer(&pixels)), 0, 0)
	if bitmap == 0 {
		return fmt.Errorf("preview bitmap unavailable")
	}
	defer gdi.NewProc("DeleteObject").Call(bitmap)
	old, _, _ := gdi.NewProc("SelectObject").Call(dc, bitmap)
	p := studioGeometry(w, h)
	previewArea = p.Preview
	studioScene(dc, w, h)
	titles := []string{"SPRAY STUDIO", "游戏安装目录", "槽位 01 · 内置编号测试图", "选图 → 构建 → 部署", "40 SLOTS  /  原生 Windows  /  你的喷漆素材工作台", "素材目录   00 / 40"}
	for i, title := range titles {
		face, ink := font, studioText
		if i == 0 {
			face = titleFont
		}
		if i == 1 || i == 3 || i == 4 {
			face, ink = smallFont, studioMuted
		}
		if i == 2 || i == 5 {
			face = captionFont
		}
		drawText(dc, title, logicalRect(p.Labels[i]), ink, face, false)
	}
	drawText(dc, defaultGame, logicalRect(p.Path), studioText, font, false)
	for i := 0; i < p.List.H/40; i++ {
		r := logicalRect(placement{p.List.X, p.List.Y + i*40, p.List.W, 40})
		if i == 0 {
			fillArea(dc, r, rgb(22, 62, 68))
		}
		nr := r
		nr.Right = nr.Left + int32(px(44))
		drawText(dc, fmt.Sprintf("%02d", i+1), nr, studioAccent, captionFont, true)
		nr.Left = nr.Right + int32(px(6))
		nr.Right = r.Right
		drawText(dc, "编号测试图", nr, studioText, smallFont, false)
	}
	for i, title := range []string{"整目录导入并排序…", "单张导入到当前槽位…", "构建部署包", "部署到游戏", "回退最近部署", "打开数据目录"} {
		studioAction(dc, logicalRect(p.Buttons[i]), []uint32{106, 101, 102, 103, 104, 105}[i], 0, title)
	}
	files, e := readVPK(embeddedVPK)
	if e != nil {
		gdi.NewProc("SelectObject").Call(dc, old)
		return e
	}
	sample, e := decodeVTF(files[slotPath(1, "vtf")])
	if e != nil {
		gdi.NewProc("SelectObject").Call(dc, old)
		return e
	}
	bg := previewBG(sample)
	rgba := make([]byte, 256*256*4)
	for y := 0; y < 256; y++ {
		for x := 0; x < 256; x++ {
			c := bg.RGBAAt(x, y)
			at := (y*256 + x) * 4
			rgba[at], rgba[at+1], rgba[at+2] = c.B, c.G, c.R
		}
	}
	imageInfo := bitmapInfo{Size: 40, Width: 256, Height: -256, Planes: 1, Bits: 32}
	gdi.NewProc("StretchDIBits").Call(dc, uintptr(p.Preview.X), uintptr(p.Preview.Y), uintptr(p.Preview.W), uintptr(p.Preview.H), 0, 0, 256, 256, uintptr(unsafe.Pointer(&rgba[0])), uintptr(unsafe.Pointer(&imageInfo)), 0, 0x00cc0020)
	drawText(dc, "就绪 · 原生离线工作流，不改动原始素材。", logicalRect(p.Status), studioMuted, smallFont, false)
	gdi.NewProc("SelectObject").Call(dc, old)
	raw := make([]byte, w*h*4)
	lines, _, _ := gdi.NewProc("GetDIBits").Call(dc, bitmap, 0, h, uintptr(unsafe.Pointer(&raw[0])), uintptr(unsafe.Pointer(&info)), 0)
	if lines != h {
		return fmt.Errorf("preview readback failed")
	}
	out := image.NewNRGBA(image.Rect(0, 0, w, h))
	for i := 0; i < w*h; i++ {
		out.SetNRGBA(i%w, i/w, color.NRGBA{R: raw[i*4+2], G: raw[i*4+1], B: raw[i*4], A: 255})
	}
	return savePNG(path, out)
}
