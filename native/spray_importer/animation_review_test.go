package main

import (
	"bytes"
	"image"
	"image/color"
	"image/gif"
	"testing"
)

func TestGIFInitialOpaqueLogicalBackground(t *testing.T) {
	palette := color.Palette{color.NRGBA{B: 255, A: 255}, color.NRGBA{R: 255, A: 255}}
	frame := image.NewPaletted(image.Rect(1, 1, 2, 2), palette)
	frame.Pix[0] = 1
	g := &gif.GIF{Image: []*image.Paletted{frame}, Delay: []int{10}, BackgroundIndex: 0, Config: image.Config{ColorModel: palette, Width: 4, Height: 4}}
	var out bytes.Buffer
	must(t, gif.EncodeAll(&out, g))
	prepared, err := convertGIF(out.Bytes())
	must(t, err)
	img := prepared.Masters[0]
	center := img.NRGBAAt(384, 384)
	if img.NRGBAAt(0, 0) != (color.NRGBA{B: 255, A: 255}) || center.R < 240 || center.B > 16 || center.A != 255 {
		t.Fatal("logical background or partial first frame lost", img.NRGBAAt(0, 0), img.NRGBAAt(96, 96))
	}
}
