package main

import (
	"bytes"
	"compress/zlib"
	"image"
	"image/color"
	"math"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type ownAPNGFrame struct {
	area           image.Rectangle
	c              color.NRGBA
	dispose, blend byte
}

func ownAPNG(t *testing.T, frames []ownAPNGFrame, hidden bool) []byte {
	t.Helper()
	var out bytes.Buffer
	out.WriteString("\x89PNG\r\n\x1a\n")
	header := make([]byte, 13)
	be.PutUint32(header, 4)
	be.PutUint32(header[4:], 4)
	header[8], header[9] = 8, 6
	pngChunk(&out, "IHDR", header)
	actl := make([]byte, 8)
	be.PutUint32(actl, uint32(len(frames)))
	pngChunk(&out, "acTL", actl)
	encode := func(frame ownAPNGFrame) []byte {
		var data bytes.Buffer
		z := zlib.NewWriter(&data)
		for y := 0; y < frame.area.Dy(); y++ {
			z.Write([]byte{0})
			for x := 0; x < frame.area.Dx(); x++ {
				z.Write([]byte{frame.c.R, frame.c.G, frame.c.B, frame.c.A})
			}
		}
		must(t, z.Close())
		return data.Bytes()
	}
	if hidden {
		pngChunk(&out, "IDAT", encode(ownAPNGFrame{area: image.Rect(0, 0, 4, 4), c: color.NRGBA{B: 255, A: 255}}))
	}
	seq := uint32(0)
	for i, f := range frames {
		control := make([]byte, 26)
		be.PutUint32(control, seq)
		seq++
		for j, v := range []int{f.area.Dx(), f.area.Dy(), f.area.Min.X, f.area.Min.Y} {
			be.PutUint32(control[4+j*4:], uint32(v))
		}
		be.PutUint16(control[20:], 1)
		be.PutUint16(control[22:], 25)
		control[24], control[25] = f.dispose, f.blend
		pngChunk(&out, "fcTL", control)
		if i == 0 && !hidden {
			pngChunk(&out, "IDAT", encode(f))
		} else {
			data := make([]byte, 4)
			be.PutUint32(data, seq)
			seq++
			data = append(data, encode(f)...)
			pngChunk(&out, "fdAT", data)
		}
	}
	pngChunk(&out, "IEND", nil)
	return out.Bytes()
}

func TestAPNGCompositionAndHiddenDefault(t *testing.T) {
	for _, hidden := range []bool{false, true} {
		for _, dispose := range []byte{0, 1, 2} {
			frames := []ownAPNGFrame{
				{area: image.Rect(0, 0, 4, 4), c: color.NRGBA{R: 255, A: 255}},
				{area: image.Rect(0, 0, 2, 2), c: color.NRGBA{G: 255, A: 128}, dispose: dispose, blend: 1},
				{area: image.Rect(2, 2, 4, 4), c: color.NRGBA{B: 255, A: 255}},
			}
			result, err := convertAPNG(ownAPNG(t, frames, hidden))
			must(t, err)
			if result.Info.Frames != 3 || result.FPS != 25 {
				t.Fatal(result.Info, result.FPS)
			}
			first := result.Masters[0]
			if first.NRGBAAt(128, 128) != (color.NRGBA{R: 255, A: 255}) {
				t.Fatal("hidden default used")
			}
			second := result.Masters[1]
			if c := second.NRGBAAt(128, 128); c.R < 126 || c.R > 128 || c.G < 127 || c.G > 129 || c.A != 255 {
				t.Fatal("OVER", c)
			}
			third := result.Masters[2]
			c := third.NRGBAAt(128, 128)
			if dispose == 1 && c.A != 0 || dispose == 2 && c != (color.NRGBA{R: 255, A: 255}) {
				t.Fatal("dispose", dispose, c)
			}
			if third.NRGBAAt(896, 896) != (color.NRGBA{B: 255, A: 255}) {
				t.Fatal("partial frame offset")
			}
			frames[1].blend = 0
			result, err = convertAPNG(ownAPNG(t, frames, hidden))
			must(t, err)
			second = result.Masters[1]
			if second.NRGBAAt(128, 128) != (color.NRGBA{G: 255, A: 128}) {
				t.Fatal("SOURCE blend")
			}
		}
	}
}

func TestAPNGBudgetPrefixAndImportRoutes(t *testing.T) {
	frames := make([]ownAPNGFrame, 40)
	for i := range frames {
		frames[i] = ownAPNGFrame{area: image.Rect(0, 0, 4, 4), c: color.NRGBA{R: uint8(i * 40), A: 255}}
	}
	raw := ownAPNG(t, frames, false)
	for _, route := range []string{"single-png", "folder-apng"} {
		a, _ := fixture(t)
		dir := t.TempDir()
		ext := ".png"
		if route == "folder-apng" {
			ext = ".apng"
		}
		path := filepath.Join(dir, "own"+ext)
		must(t, atomicWrite(path, raw))
		if route == "single-png" {
			must(t, a.Import(path, 1))
		} else {
			r, err := a.ImportFolder(dir)
			must(t, err)
			if len(r.Notices) != 1 || !strings.Contains(r.Notices[0], "3/40") {
				t.Fatal(r.Notices)
			}
		}
		row := a.State.Slots[1]
		if row.Animation == nil || row.Animation.Original != 40 || row.Animation.Kept != 3 || row.Animation.Size != 512 || row.Animation.Bytes >= 512<<10 || len(row.Masters) != 3 {
			t.Fatal(row.Animation)
		}
		clip, err := a.LoadPreview(1)
		must(t, err)
		last, err := decodeVTFFrame(clip.Raw, 2)
		must(t, err)
		if clip.Info.Frames != 3 || math.Abs(float64(last.NRGBAAt(256, 256).R)-80) > 7 {
			t.Fatal("not a continuous prefix")
		}
		folder, err := a.Build()
		must(t, err)
		packed, err := os.ReadFile(filepath.Join(folder, "left4dead2/addons", vpkName))
		must(t, err)
		files, err := readVPK(packed)
		must(t, err)
		if !bytes.Equal(files[slotPath(1, "vtf")], clip.Raw) || !strings.Contains(string(files["materials/vgui/logos/ui/csp_test/test_001.vmt"]), "AnimatedTexture") {
			t.Fatal("build lost animation")
		}
		reopened, err := newApp(a.Home, a.Game)
		must(t, err)
		if reopened.State.Slots[1].Animation.Kept != 3 {
			t.Fatal("notice not persisted")
		}
	}
}

func TestAPNGMalformedRejected(t *testing.T) {
	frames := []ownAPNGFrame{{area: image.Rect(0, 0, 4, 4), c: color.NRGBA{R: 255, A: 255}}, {area: image.Rect(0, 0, 4, 4), c: color.NRGBA{G: 255, A: 255}}}
	raw := ownAPNG(t, frames, false)
	for _, scenario := range []string{"count", "sequence", "dispose", "critical"} {
		var changed bytes.Buffer
		changed.Write(raw[:8])
		did := false
		for at := 8; at < len(raw); {
			n := int(be.Uint32(raw[at:]))
			kind := string(raw[at+4 : at+8])
			data := append([]byte{}, raw[at+8:at+8+n]...)
			if !did {
				switch {
				case scenario == "count" && kind == "acTL":
					be.PutUint32(data, 3)
					did = true
				case scenario == "sequence" && kind == "fdAT":
					be.PutUint32(data, 99)
					did = true
				case scenario == "dispose" && kind == "fcTL":
					data[24] = 3
					did = true
				case scenario == "critical" && kind == "acTL":
					kind = "ABCD"
					did = true
				}
			}
			pngChunk(&changed, kind, data)
			at += n + 12
		}
		if _, err := convertAPNG(changed.Bytes()); err == nil {
			t.Fatal("valid CRC but invalid APNG accepted", scenario)
		}
	}
	for _, bad := range [][]byte{nil, raw[:12], raw[:len(raw)-1], append(append([]byte{}, raw...), 0)} {
		if _, err := convertAPNG(bad); err == nil {
			t.Fatal("truncated accepted")
		}
	}
	for _, kind := range []string{"IHDR", "acTL", "fcTL", "fdAT"} {
		bad := append([]byte{}, raw...)
		at := bytes.Index(bad, []byte(kind))
		bad[at+4] ^= 255
		if _, err := convertAPNG(bad); err == nil {
			t.Fatal("bad CRC", kind)
		}
	}
	frames[1].area = image.Rect(3, 3, 5, 5)
	if _, err := convertAPNG(ownAPNG(t, frames, false)); err == nil {
		t.Fatal("out of canvas accepted")
	}
}
