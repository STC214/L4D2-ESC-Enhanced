package main

import (
	"bytes"
	"image"
	"image/color"
	"image/png"
	"testing"
)

func TestIconFramesAndDeterminism(t *testing.T) {
	source := image.NewNRGBA(image.Rect(0, 0, 256, 256))
	for y := 0; y < 256; y++ {
		for x := 0; x < 256; x++ {
			source.SetNRGBA(x, y, color.NRGBA{R: 200, G: 40, B: 60, A: 128})
		}
	}
	raw, e := makeIcon(source)
	must(t, e)
	again, e := makeIcon(source)
	must(t, e)
	if !bytes.Equal(raw, again) || le.Uint16(raw) != 0 || le.Uint16(raw[2:]) != 1 || int(le.Uint16(raw[4:])) != len(iconSizes) {
		t.Fatal("ICO header/determinism")
	}
	end := 6 + 16*len(iconSizes)
	for i, size := range iconSizes {
		entry := raw[6+i*16:]
		n, offset := int(le.Uint32(entry[8:])), int(le.Uint32(entry[12:]))
		if offset != end || entry[0] != byte(size%256) || entry[1] != byte(size%256) || le.Uint16(entry[6:]) != 32 {
			t.Fatal("ICO directory")
		}
		img, e := png.Decode(bytes.NewReader(raw[offset : offset+n]))
		must(t, e)
		if img.Bounds().Dx() != size || img.Bounds().Dy() != size {
			t.Fatal("ICO dimensions")
		}
		_, _, _, alpha := img.At(size/2, size/2).RGBA()
		if alpha != 128*257 {
			t.Fatal("alpha lost")
		}
		end += n
	}
	if end != len(raw) {
		t.Fatal("extra ICO bytes")
	}
}
