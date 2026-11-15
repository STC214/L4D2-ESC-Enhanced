package main

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"hash/crc32"
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestPreviewAspectAndTransparentBackground(t *testing.T) {
	for _, dims := range [][2]int{{8, 4}, {4, 8}, {4, 4}, {8192, 1}, {1, 8192}, {1020, 1024}} {
		for _, size := range []int{58, 160, 256} {
			x, y, w, h := previewRect(dims[0], dims[1], 7, 11, size)
			if x < 7 || y < 11 || x+w > 7+size || y+h > 11+size || max(w, h) != size || min(w, h) < 1 {
				t.Fatal(dims, size, x, y, w, h)
			}
			if dims[0] >= dims[1] && h != max(1, (dims[1]*size+dims[0]/2)/dims[0]) {
				t.Fatal("aspect rounding", dims, w, h)
			}
		}
	}
	for _, dims := range [][2]int{{8, 4}, {4, 8}} {
		img := image.NewNRGBA(image.Rect(0, 0, dims[0], dims[1]))
		for i := 0; i < len(img.Pix); i += 4 {
			copy(img.Pix[i:], []byte{255, 0, 0, 128})
		}
		fitted := fitImage(img)
		if fitted.NRGBAAt(0, 0).A != 0 {
			t.Fatal("padding not transparent")
		}
		bg := previewBG(fitted)
		if bg.RGBAAt(0, 0) != (color.RGBA{9, 17, 31, 255}) || bg.RGBAAt(16, 16) != bg.RGBAAt(0, 0) {
			t.Fatal("padding must match preview surface, no checkerboard")
		}
		if c := bg.RGBAAt(128, 128); c.R < 130 || c.G > 9 || c.B > 16 || c.A != 255 {
			t.Fatal("alpha composition", c)
		}
	}
}

func rectangularAnimation(w, h int) []byte {
	raw := append([]byte{}, twoFrameVTF(0)[:64]...)
	le.PutUint16(raw[16:], uint16(w))
	le.PutUint16(raw[18:], uint16(h))
	raw[56] = 1
	raw = append(raw, solidFrame(w, h, 0, color.NRGBA{R: 255, A: 255})...)
	return append(raw, solidFrame(w, h, 0, color.NRGBA{G: 255, A: 255})...)
}

func TestPreviewBuildAnimationAllImportRoutes(t *testing.T) {
	for _, route := range []string{"file", "folder", "vpk", "gif"} {
		t.Run(route, func(t *testing.T) {
			a, _ := fixture(t)
			raw := rectangularAnimation(8, 4)
			dir := t.TempDir()
			path := filepath.Join(dir, "own.vtf")
			must(t, atomicWrite(path, raw))
			switch route {
			case "file":
				must(t, a.Import(path, 1))
			case "folder":
				_, err := a.ImportFolder(dir)
				must(t, err)
			case "vpk":
				pkg := sprayVPK(t, filepath.Join(t.TempDir(), "own.vpk"), map[string][]byte{"materials/vgui/logos/own.vtf": raw})
				_, err := a.ImportVPKs([]string{pkg})
				must(t, err)
			case "gif":
				path = filepath.Join(t.TempDir(), "own.gif")
				must(t, atomicWrite(path, ownGIF(t, 1)))
				must(t, a.Import(path, 1))
			}
			clip, err := a.LoadPreview(1)
			must(t, err)
			first, err := clip.Frame(0)
			must(t, err)
			second, err := clip.Frame(1)
			must(t, err)
			if bytes.Equal(first.Pix, second.Pix) || clip.Info.Frames < 2 {
				t.Fatal("preview flattened")
			}
			folder, err := a.Build()
			must(t, err)
			packed, err := os.ReadFile(filepath.Join(folder, "left4dead2/addons", vpkName))
			must(t, err)
			files, err := readVPK(packed)
			must(t, err)
			if !bytes.Equal(files[slotPath(1, "vtf")], clip.Raw) {
				t.Fatal("frames/mips changed during build")
			}
			for _, path := range []string{slotPath(1, "vmt"), "materials/vgui/logos/ui/csp_test/test_001.vmt"} {
				mat := string(files[path])
				if !strings.Contains(mat, `"AnimatedTexture"`) || !strings.Contains(mat, `"$frame" "0"`) {
					t.Fatal(path, mat)
				}
				ref, err := materialTexture(files[path])
				must(t, err)
				if ref != "vgui/logos/csp_test/test_001" {
					t.Fatal(ref)
				}
			}
			ui := string(files["materials/vgui/logos/ui/csp_test/test_001.vmt"])
			for _, key := range []string{"UnlitGeneric", "$vertexcolor", "$vertexalpha", "$ignorez"} {
				if !strings.Contains(ui, key) {
					t.Fatal(ui)
				}
			}
			if route != "gif" {
				page := string(files["resource/ui/csp_test/page_1.res"])
				if !strings.Contains(page, `"tall" "29"`) || !strings.Contains(page, `"ypos" "46"`) {
					t.Fatal("non-square thumbnail not fitted", page)
				}
				confirm := string(files["resource/ui/csp_test/confirm_001.res"])
				if !strings.Contains(confirm, `"tall" "80"`) || !strings.Contains(confirm, `"ypos" "75"`) {
					t.Fatal("non-square confirmation not fitted", confirm)
				}
			}
		})
	}
}

func TestPreviewControlValidationAndStaticMaterial(t *testing.T) {
	t.Run("APNGMustNotSilentlyFlatten", func(t *testing.T) {
		var out bytes.Buffer
		must(t, png.Encode(&out, image.NewNRGBA(image.Rect(0, 0, 4, 2))))
		raw := out.Bytes()
		chunk := make([]byte, 20)
		binary.BigEndian.PutUint32(chunk, 8)
		copy(chunk[4:], "acTL")
		binary.BigEndian.PutUint32(chunk[8:], 2)
		binary.BigEndian.PutUint32(chunk[16:], crc32.ChecksumIEEE(chunk[4:16]))
		apng := append(append(append([]byte{}, raw[:33]...), chunk...), raw[33:]...)
		path := filepath.Join(t.TempDir(), "animated.png")
		must(t, atomicWrite(path, apng))
		a, _ := fixture(t)
		if err := a.Import(path, 1); err == nil || !strings.Contains(err.Error(), "APNG") {
			t.Fatal("APNG silently flattened", err)
		}
		if _, err := a.ImportFolder(filepath.Dir(path)); err == nil || len(a.State.Slots) != 0 {
			t.Fatal("APNG folder import committed", err)
		}
		must(t, validateStaticPNG(raw))
		for _, bad := range [][]byte{raw[:12], raw[:len(raw)-12]} {
			if validateStaticPNG(bad) == nil {
				t.Fatal("truncated PNG accepted")
			}
		}
	})
	for _, raw := range []string{"", `"X" {"xpos" "0"}`, `"X" {} "X" {}`} {
		if _, err := fitPreviewControl([]byte(raw), "X", 4, 2, 0, 0, 58); err == nil {
			t.Fatal("invalid resource accepted")
		}
	}
	if strings.Contains(string(previewMaterial(1, 1, 10)), "AnimatedTexture") {
		t.Fatal("static animates")
	}
	files, err := readVPK(embeddedVPK)
	must(t, err)
	for n := 1; n <= 40; n++ {
		must(t, configureSlotPreview(files, n, &VTFInfo{Width: 4, Height: 8, Frames: 2}, 12))
		path := fmt.Sprintf("resource/ui/csp_test/confirm_%03d.res", n)
		if !strings.Contains(string(files[path]), `"wide" "80"`) {
			t.Fatal(path)
		}
	}
}
