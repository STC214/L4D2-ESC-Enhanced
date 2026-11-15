package main

import (
	"bytes"
	"image"
	"image/color"
	"image/gif"
	"math"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func solidFrame(w, h int, format uint32, c color.NRGBA) []byte {
	out := make([]byte, vtfLevelBytes(w, h, format))
	if format >= 13 {
		step := 8
		if format != 13 {
			step = 16
		}
		for i := 0; i < len(out); i += step {
			block := out[i : i+step]
			if format == 14 {
				for j := 0; j < 8; j++ {
					block[j] = 255
				}
				block = block[8:]
			}
			if format == 15 {
				block[0] = 255
				block = block[8:]
			}
			code := uint16(c.R>>3)<<11 | uint16(c.G>>2)<<5 | uint16(c.B>>3)
			le.PutUint16(block, code)
		}
		return out
	}
	step := 4
	if format == 2 || format == 3 {
		step = 3
	}
	for i := 0; i < len(out); i += step {
		r, b := c.R, c.B
		if format == 3 || format == 12 {
			r, b = b, r
		}
		out[i], out[i+1], out[i+2] = r, c.G, b
		if step == 4 {
			out[i+3] = c.A
		}
	}
	return out
}

func twoFrameVTF(format uint32) []byte {
	raw := make([]byte, 64)
	copy(raw, "VTF\x00")
	le.PutUint32(raw[4:], 7)
	le.PutUint32(raw[8:], 1)
	le.PutUint32(raw[12:], 64)
	le.PutUint16(raw[16:], 4)
	le.PutUint16(raw[18:], 4)
	le.PutUint16(raw[24:], 2)
	le.PutUint32(raw[52:], format)
	raw[56] = 3
	le.PutUint32(raw[57:], 0xffffffff)
	for level := 2; level >= 0; level-- {
		colors := []color.NRGBA{{R: 255, A: 255}, {G: 255, A: 255}}
		if level > 0 {
			colors = []color.NRGBA{{B: 255, A: 255}, {R: 255, G: 255, A: 255}}
		}
		for _, c := range colors {
			raw = append(raw, solidFrame(4>>level, 4>>level, format, c)...)
		}
	}
	return raw
}

func TestAnimatedVTFFrameLayoutAllFormats(t *testing.T) {
	for _, format := range []uint32{0, 2, 3, 12, 13, 14, 15} {
		raw := twoFrameVTF(format)
		for frame, want := range []color.NRGBA{{R: 255, A: 255}, {G: 255, A: 255}} {
			img, err := decodeVTFFrame(raw, frame)
			must(t, err)
			if img.NRGBAAt(0, 0) != want {
				t.Fatal(format, frame, img.NRGBAAt(0, 0), want)
			}
		}
		for _, frame := range []int{-1, 2} {
			if _, err := decodeVTFFrame(raw, frame); err == nil {
				t.Fatal("invalid frame accepted")
			}
		}
	}
}

func TestAnimatedVTFStandalonePreviewAndMaterial(t *testing.T) {
	a, _ := fixture(t)
	raw := twoFrameVTF(13)
	p := filepath.Join(t.TempDir(), "own.vtf")
	must(t, atomicWrite(p, raw))
	must(t, a.Import(p, 3))
	clip, err := a.LoadPreview(3)
	must(t, err)
	img, err := clip.Frame(1)
	must(t, err)
	if clip.Info.Frames != 2 || img.NRGBAAt(128, 128) != (color.NRGBA{G: 255, A: 255}) {
		t.Fatal("animated preview failed")
	}
	row := a.State.Slots[3]
	row.FrameRate = 24
	a.State.Slots[3] = row
	must(t, saveJSON(filepath.Join(a.Home, "slots.json"), a.State))
	folder, err := a.Build()
	must(t, err)
	b, err := os.ReadFile(filepath.Join(folder, "left4dead2/addons", vpkName))
	must(t, err)
	f, err := readVPK(b)
	must(t, err)
	if !bytes.Equal(f[slotPath(3, "vtf")], raw) {
		t.Fatal("animated VTF changed")
	}
	material := string(f[slotPath(3, "vmt")])
	if !strings.Contains(material, "AnimatedTexture") || !strings.Contains(material, `"animatedTextureFrameRate" "24"`) {
		t.Fatal(material)
	}
	ref, err := materialTexture(f[slotPath(3, "vmt")])
	must(t, err)
	if ref != "vgui/logos/csp_test/test_003" {
		t.Fatal(ref)
	}
	if strings.Contains(string(animationMaterial(1, 1, 10)), "AnimatedTexture") {
		t.Fatal("static material animates")
	}
	for _, value := range []float64{math.NaN(), math.Inf(1), -1, 0, 0.1, 200} {
		rate := animationFPS(value)
		if rate < 1 || rate > 100 {
			t.Fatal(rate)
		}
	}
}

func ownGIF(t *testing.T, disposal byte) []byte {
	t.Helper()
	palette := color.Palette{color.NRGBA{}, color.NRGBA{R: 255, A: 255}, color.NRGBA{G: 255, A: 255}, color.NRGBA{B: 255, A: 255}}
	first := image.NewPaletted(image.Rect(0, 0, 4, 4), palette)
	for i := range first.Pix {
		first.Pix[i] = 1
	}
	second := image.NewPaletted(image.Rect(0, 0, 2, 2), palette)
	for i := range second.Pix {
		second.Pix[i] = 2
	}
	third := image.NewPaletted(image.Rect(2, 2, 4, 4), palette)
	for i := range third.Pix {
		third.Pix[i] = 3
	}
	g := &gif.GIF{Image: []*image.Paletted{first, second, third}, Delay: []int{10, 20, 30}, Disposal: []byte{gif.DisposalNone, disposal, gif.DisposalNone}, Config: image.Config{ColorModel: palette, Width: 4, Height: 4}}
	var out bytes.Buffer
	must(t, gif.EncodeAll(&out, g))
	return out.Bytes()
}

func TestAnimatedGIFImportFolderAndTiming(t *testing.T) {
	a, _ := fixture(t)
	dir := t.TempDir()
	p := filepath.Join(dir, "own.gif")
	must(t, atomicWrite(p, ownGIF(t, gif.DisposalPrevious)))
	must(t, atomicWrite(filepath.Join(dir, "own.vtf"), twoFrameVTF(13)))
	r, err := a.ImportFolder(dir)
	must(t, err)
	if r.Total != 2 {
		t.Fatal(r)
	}
	for n, row := range a.State.Slots {
		clip, err := a.LoadPreview(n)
		must(t, err)
		if strings.HasSuffix(row.Title, ".gif") {
			if clip.Info.Frames != 3 || clip.Info.Width != 128 || math.Abs(clip.FPS-5) > 0.001 {
				t.Fatal(clip.Info, clip.FPS)
			}
			if len(clip.Raw) >= 512<<10 {
				t.Fatal("GIF output too large")
			}
		}
	}
	_, err = a.Build()
	must(t, err)
}

func TestAnimatedGIFDisposalComposition(t *testing.T) {
	for _, mode := range []byte{gif.DisposalPrevious, gif.DisposalBackground} {
		prepared, err := convertGIF(ownGIF(t, mode))
		must(t, err)
		img, err := decodeVTFFrame(prepared.Raw, 2)
		must(t, err)
		want := color.NRGBA{R: 255, A: 255}
		if mode == gif.DisposalBackground {
			want = color.NRGBA{}
		}
		if img.NRGBAAt(16, 16) != want || img.NRGBAAt(112, 112) != (color.NRGBA{B: 255, A: 255}) {
			t.Fatal(mode, img.NRGBAAt(16, 16), img.NRGBAAt(112, 112))
		}
	}
}

func TestAnimatedGIFPreflightLimits(t *testing.T) {
	raw := ownGIF(t, gif.DisposalNone)
	for _, bad := range [][]byte{nil, raw[:12], raw[:len(raw)-2]} {
		if _, err := convertGIF(bad); err == nil {
			t.Fatal("broken GIF accepted")
		}
	}
	huge := append([]byte{}, raw...)
	le.PutUint16(huge[6:], 8192)
	le.PutUint16(huge[8:], 8192)
	if _, err := inspectGIF(huge); err == nil {
		t.Fatal("oversize GIF accepted")
	}
	palette := color.Palette{color.Black, color.White}
	frame := image.NewPaletted(image.Rect(0, 0, 1, 1), palette)
	g := &gif.GIF{Config: image.Config{ColorModel: palette, Width: 1, Height: 1}}
	for i := 0; i < 257; i++ {
		g.Image = append(g.Image, frame)
		g.Delay = append(g.Delay, 0)
	}
	var out bytes.Buffer
	must(t, gif.EncodeAll(&out, g))
	if _, err := convertGIF(out.Bytes()); err == nil {
		t.Fatal("257-frame GIF accepted")
	}
	g.Image = g.Image[:256]
	g.Delay = g.Delay[:256]
	out.Reset()
	must(t, gif.EncodeAll(&out, g))
	prepared, err := convertGIF(out.Bytes())
	must(t, err)
	if prepared.Info.Frames != 256 || prepared.Info.Width != 16 || prepared.FPS != 10 {
		t.Fatal(prepared.Info, prepared.FPS)
	}
}

func TestPreviewIntegrityAndStaticFallback(t *testing.T) {
	a, p := fixture(t)
	must(t, a.Import(p, 1))
	img, err := a.Preview(1)
	must(t, err)
	if img == nil {
		t.Fatal("static preview missing")
	}
	row := a.State.Slots[1]
	must(t, atomicWrite(filepath.Join(a.Home, filepath.FromSlash(row.Texture)), []byte("changed")))
	if _, err := a.LoadPreview(1); err == nil {
		t.Fatal("changed preview accepted")
	}
}
