package main

import (
	"bytes"
	"image"
	"image/color"
	"image/png"
	"math"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestQualityDXT1BlockEncoding(t *testing.T) {
	for _, c := range []color.NRGBA{{A: 255}, {255, 255, 255, 255}, {17, 123, 238, 255}, {255, 0, 0, 128}, {255, 0, 0, 127}, {}} {
		src := image.NewNRGBA(image.Rect(0, 0, 7, 5))
		for y := 0; y < 5; y++ {
			for x := 0; x < 7; x++ {
				src.SetNRGBA(x, y, c)
			}
		}
		data := encodeDXT1(src)
		if len(data) != 32 {
			t.Fatal("block padding", len(data))
		}
		decoded := image.NewNRGBA(src.Bounds())
		decodeBlocks(decoded, data, 13)
		for y := 0; y < 5; y++ {
			for x := 0; x < 7; x++ {
				got := decoded.NRGBAAt(x, y)
				if c.A < 128 {
					if got.A != 0 {
						t.Fatal(c, got)
					}
				} else if got.A != 255 || math.Abs(float64(got.R)-float64(c.R)) > 7 || math.Abs(float64(got.G)-float64(c.G)) > 3 || math.Abs(float64(got.B)-float64(c.B)) > 7 {
					t.Fatal(c, got)
				}
			}
		}
	}
	// Mixed transparency and RGB endpoints must coexist in the same block.
	src := image.NewNRGBA(image.Rect(0, 0, 4, 4))
	src.SetNRGBA(0, 0, color.NRGBA{R: 255, A: 255})
	src.SetNRGBA(1, 0, color.NRGBA{G: 255, A: 255})
	decoded := image.NewNRGBA(src.Bounds())
	decodeBlocks(decoded, encodeDXT1(src), 13)
	if decoded.NRGBAAt(0, 0) != (color.NRGBA{R: 255, A: 255}) || decoded.NRGBAAt(1, 0) != (color.NRGBA{G: 255, A: 255}) || decoded.NRGBAAt(2, 0).A != 0 {
		t.Fatal("mixed block")
	}
}

func TestQualityStaticMasterAndGameBudget(t *testing.T) {
	a, path := fixture(t)
	must(t, a.Import(path, 1))
	row := a.State.Slots[1]
	if row.VTF == nil || row.VTF.Width != 1020 || row.VTF.Height != 1024 || row.VTF.Format != 13 || len(row.Masters) != 1 {
		t.Fatal(row)
	}
	master, err := os.ReadFile(filepath.Join(a.Home, filepath.FromSlash(row.Masters[0])))
	must(t, err)
	img, err := png.Decode(bytes.NewReader(master))
	must(t, err)
	if img.Bounds() != image.Rect(0, 0, 1024, 1024) {
		t.Fatal("master not 1024", img.Bounds())
	}
	_, _, _, alpha := img.At(512, 512).RGBA()
	if alpha/257 != 128 {
		t.Fatal("master lost soft alpha")
	}
	clip, err := a.LoadPreview(1)
	must(t, err)
	if len(clip.Raw) != 522320 || len(clip.Raw) >= 512<<10 {
		t.Fatal("static game budget", len(clip.Raw))
	}
	game, err := decodeVTFFrame(clip.Raw, 0)
	must(t, err)
	if game.NRGBAAt(0, 0).A != 0 || game.NRGBAAt(510, 512).A != 255 {
		t.Fatal("DXT1 alpha threshold/padding")
	}
	if !strings.Contains(row.Animation.description(), "1020×1024") || !strings.Contains(row.Animation.description(), "1位透明") {
		t.Fatal("quality tradeoff not disclosed")
	}
	folder, err := a.Build()
	must(t, err)
	packed, err := os.ReadFile(filepath.Join(folder, "left4dead2/addons", vpkName))
	must(t, err)
	files, err := readVPK(packed)
	must(t, err)
	if !bytes.Equal(files[slotPath(1, "vtf")], clip.Raw) || len(files) != 167 {
		t.Fatal("high quality build mismatch")
	}
	for name := range files {
		if strings.Contains(name, "master_") {
			t.Fatal("private masters leaked into VPK")
		}
	}
}

func TestQualityAnimatedPrefixAndMasters(t *testing.T) {
	for _, kind := range []string{"GIF", "APNG"} {
		a, _ := fixture(t)
		dir := t.TempDir()
		path := filepath.Join(dir, "own.gif")
		var raw []byte
		if kind == "GIF" {
			raw = ownGIF(t, 1)
		} else {
			path = filepath.Join(dir, "own.apng")
			frames := make([]ownAPNGFrame, 8)
			colors := []color.NRGBA{{R: 255, A: 255}, {G: 255, A: 255}, {B: 255, A: 255}}
			for i := range frames {
				frames[i] = ownAPNGFrame{area: image.Rect(0, 0, 4, 4), c: colors[i%3]}
			}
			raw = ownAPNG(t, frames, false)
		}
		must(t, atomicWrite(path, raw))
		result, err := a.ImportFolder(dir)
		must(t, err)
		row := a.State.Slots[1]
		if row.VTF.Width != 512 || row.VTF.Height != 512 || row.VTF.Format != 13 || row.VTF.Frames != 3 || len(row.Masters) != 3 || len(result.Notices) != 1 {
			t.Fatal(row, result)
		}
		if kind == "APNG" && (row.Animation.Original != 8 || row.Animation.Kept != 3) {
			t.Fatal("not a prefix")
		}
		for _, path := range row.Masters {
			f, err := os.Open(filepath.Join(a.Home, filepath.FromSlash(path)))
			must(t, err)
			cfg, err := png.DecodeConfig(f)
			f.Close()
			must(t, err)
			if cfg.Width != 1024 || cfg.Height != 1024 {
				t.Fatal("animated master size", cfg)
			}
		}
		clip, err := a.LoadPreview(1)
		must(t, err)
		if len(clip.Raw) != 393296 {
			t.Fatal("animated DXT1 budget", len(clip.Raw))
		}
		first, err := clip.Frame(0)
		must(t, err)
		second, err := clip.Frame(1)
		must(t, err)
		if bytes.Equal(first.Pix, second.Pix) {
			t.Fatal("animation flattened")
		}
		_, err = a.Build()
		must(t, err)
	}
}
