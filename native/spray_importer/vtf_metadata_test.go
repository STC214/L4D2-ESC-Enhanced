package main

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Entirely synthetic byte fixtures: no image decoder, renderer or picture input.
func metadataFixture(frames, mips int) []byte {
	size := 0
	for level := 0; level < mips; level++ {
		size += vtfLevelBytes(max(1, 256>>level), max(1, 256>>level), 13) * frames
	}
	raw := make([]byte, 64+size)
	copy(raw, "VTF\x00")
	le.PutUint32(raw[4:], 7)
	le.PutUint32(raw[8:], 1)
	le.PutUint32(raw[12:], 64)
	le.PutUint16(raw[16:], 256)
	le.PutUint16(raw[18:], 256)
	le.PutUint16(raw[24:], uint16(frames))
	le.PutUint32(raw[52:], 13)
	raw[56] = byte(mips)
	le.PutUint32(raw[57:], 0xffffffff)
	return raw
}

func TestVTFMetadataNineFramesAndMipLengths(t *testing.T) {
	raw := metadataFixture(9, 4)
	info, err := inspectVTF(raw)
	must(t, err)
	if len(raw) != 391744 || info.Frames != 9 || info.Mips != 4 || info.Width != 256 {
		t.Fatal(info, len(raw))
	}
	for _, bad := range [][]byte{nil, raw[:63], raw[:len(raw)-1]} {
		if _, err = inspectVTF(bad); err == nil {
			t.Fatal("truncated mip/frame payload accepted")
		}
	}
	for _, field := range []string{"frames", "version", "cube", "mips", "format", "first", "header", "limit"} {
		bad := append([]byte{}, raw...)
		switch field {
		case "frames":
			le.PutUint16(bad[24:], 0)
		case "version":
			le.PutUint32(bad[8:], 6)
		case "cube":
			le.PutUint32(bad[20:], 0x4000)
		case "mips":
			bad[56] = 14
		case "format":
			le.PutUint32(bad[52:], 99)
		case "first":
			le.PutUint16(bad[26:], 10)
		case "header":
			le.PutUint32(bad[12:], 0xffffffff)
		case "limit":
			bad = append(bad, make([]byte, (512<<10)-len(bad))...)
		}
		if _, err = inspectVTF(bad); err == nil {
			t.Fatal("bad metadata accepted", field)
		}
	}
}

func TestVTFMetadataResourceTable(t *testing.T) {
	old := metadataFixture(9, 4)
	raw := append(make([]byte, 88), old[64:]...)
	copy(raw[:64], old[:64])
	le.PutUint32(raw[8:], 3)
	le.PutUint32(raw[12:], 88)
	le.PutUint16(raw[63:], 1)
	le.PutUint32(raw[68:], 1)
	raw[80] = 0x30
	le.PutUint32(raw[84:], 88)
	_, err := inspectVTF(raw)
	must(t, err)
	for _, pos := range []int{63, 68, 80, 83, 84} {
		bad := append([]byte{}, raw...)
		bad[pos] = 0xff
		if _, err = inspectVTF(bad); err == nil {
			t.Fatal("bad resource metadata accepted", pos)
		}
	}
}

// With the two opt-in paths this runs the exact same byte-only checks against
// the user's approved packages; default runs use generated VPK fixtures.
func TestVPKMetadataOnlyAcceptance(t *testing.T) {
	a, _ := fixture(t)
	before := seedGame(t, a)
	paths := []string{os.Getenv("CSP_METADATA_VPK1"), os.Getenv("CSP_METADATA_VPK2")}
	wantTotal := 30
	if paths[0] == "" && paths[1] == "" {
		dir := t.TempDir()
		paths[0] = sprayVPK(t, filepath.Join(dir, "one.vpk"), map[string][]byte{"materials/vgui/logos/1.vtf": metadataFixture(1, 4)})
		paths[1] = sprayVPK(t, filepath.Join(dir, "two.vpk"), map[string][]byte{"materials/vgui/logos/5.vtf": metadataFixture(9, 4)})
		wantTotal = 2
	}
	originals := map[string]string{}
	expected := map[string][]byte{}
	for _, filename := range paths {
		raw, err := os.ReadFile(filename)
		must(t, err)
		originals[filename] = digest(raw)
		files, err := readVPK(raw)
		must(t, err)
		names, err := sprayMembers(files)
		must(t, err)
		for _, name := range names {
			expected[strings.ToLower(filepath.Clean(filename+"::"+name))] = files[name]
		}
	}
	r, err := a.ImportVPKs(paths)
	must(t, err)
	if r.Total != wantTotal || r.Imported != wantTotal {
		t.Fatal(r)
	}
	animated := 0
	for n, row := range a.State.Slots {
		info, err := a.VTFMetadata(n)
		must(t, err)
		if info == nil || row.Preview != "" {
			t.Fatal("picture preview generated or metadata missing")
		}
		if info.Frames > 1 {
			animated++
			if info.Frames != 9 || info.Mips != 4 || info.Width != 256 || info.Height != 256 {
				t.Fatal(info)
			}
		}
		if _, err = a.Preview(n); !errors.Is(err, errMetadataPreview) {
			t.Fatal("picture preview not blocked", err)
		}
		data, err := os.ReadFile(filepath.Join(a.Home, filepath.FromSlash(row.Texture)))
		must(t, err)
		if !bytes.Equal(data, expected[strings.ToLower(filepath.Clean(row.Source))]) {
			t.Fatal("source VTF bytes changed")
		}
	}
	if animated != 1 {
		t.Fatal("expected exactly one preserved animation", animated)
	}
	// Reopening must retain metadata-only behavior via the on-disk schema.
	a, err = newApp(a.Home, a.Game)
	must(t, err)
	folder, err := a.Build()
	must(t, err)
	raw, err := os.ReadFile(filepath.Join(folder, "left4dead2/addons", vpkName))
	must(t, err)
	packed, err := readVPK(raw)
	must(t, err)
	for n, row := range a.State.Slots {
		want := expected[strings.ToLower(filepath.Clean(row.Source))]
		if !bytes.Equal(packed[slotPath(n, "vtf")], want) {
			t.Fatal("VPK build changed frame bytes")
		}
		mod, err := os.ReadFile(filepath.Join(folder, "update", filepath.FromSlash(slotPath(n, "vtf"))))
		must(t, err)
		if !bytes.Equal(mod, want) {
			t.Fatal("MOD build changed frame bytes")
		}
		ref, err := materialTexture(packed[slotPath(n, "vmt")])
		must(t, err)
		if ref != fmt.Sprintf("vgui/logos/csp_test/test_%03d", n) {
			t.Fatal("renumbered reference mismatch", ref)
		}
	}
	_, err = a.Deploy(true)
	must(t, err)
	must(t, a.Rollback(true))
	for name, hash := range before {
		after, err := fileHash(filepath.Join(a.Game, filepath.FromSlash(name)))
		must(t, err)
		if hash != after {
			t.Fatal("fixture rollback mismatch")
		}
	}
	for filename, hash := range originals {
		after, err := fileHash(filename)
		must(t, err)
		if after != hash {
			t.Fatal("source package modified")
		}
	}
	must(t, filepath.WalkDir(a.Home, func(name string, entry os.DirEntry, err error) error {
		if err == nil && !entry.IsDir() && strings.EqualFold(filepath.Ext(name), ".png") {
			t.Error("PNG generated during metadata-only import")
		}
		return err
	}))
	t.Logf("PASS metadata-only: %d textures, 1 nine-frame animation, byte-identical import/build/MOD, renumbered VMT, 81-file fixture deploy/rollback; no picture decoding/PNG/preview", wantTotal)
}

func TestVPKAnimatedTruncationAndMetadataTamper(t *testing.T) {
	a, source := fixture(t)
	must(t, a.Import(source, 1)) // self-authored fixture only
	before, err := fileHash(filepath.Join(a.Home, "slots.json"))
	must(t, err)
	raw := metadataFixture(9, 4)
	pkg := sprayVPK(t, filepath.Join(t.TempDir(), "anim.vpk"), map[string][]byte{"materials/vgui/logos/5.vtf": raw[:len(raw)-1]})
	if _, err = a.ImportVPKs([]string{pkg}); err == nil {
		t.Fatal("truncated animation imported")
	}
	after, err := fileHash(filepath.Join(a.Home, "slots.json"))
	must(t, err)
	if before != after {
		t.Fatal("invalid animation changed catalog")
	}
	sprayVPK(t, pkg, map[string][]byte{"materials/vgui/logos/5.vtf": raw})
	_, err = a.ImportVPKs([]string{pkg})
	must(t, err)
	for n, row := range a.State.Slots {
		if row.VTF != nil {
			row.VTF.Frames++
			if _, err = a.VTFMetadata(n); err == nil {
				t.Fatal("tampered metadata accepted")
			}
		}
	}
	must(t, saveJSON(filepath.Join(a.Home, "slots.json"), a.State))
	if _, err = a.Build(); err == nil {
		t.Fatal("tampered metadata built")
	}
}

func TestLegacyVPKMetadataOnlyWithoutMigration(t *testing.T) {
	a, source := fixture(t)
	must(t, a.Import(source, 1)) // generated test picture, not user content
	row := a.State.Slots[1]
	row.Source = filepath.Join(t.TempDir(), "legacy.vpk") + "::materials/vgui/logos/1.vtf"
	row.VTF = nil
	a.State.Slots[1] = row
	must(t, saveJSON(filepath.Join(a.Home, "slots.json"), a.State))
	info, err := a.VTFMetadata(1)
	must(t, err)
	if info == nil || info.Frames != 1 {
		t.Fatal(info)
	}
	if _, err = a.Preview(1); !errors.Is(err, errMetadataPreview) {
		t.Fatal("legacy VPK preview not blocked", err)
	}
	_, err = a.Build()
	must(t, err)
}

func FuzzVTFMetadata(f *testing.F) {
	f.Add(metadataFixture(9, 4))
	f.Add(metadataFixture(1, 1))
	f.Add([]byte{})
	f.Fuzz(func(t *testing.T, data []byte) {
		if len(data) <= 512<<10 {
			inspectVTF(data)
		}
	})
}

func TestVTFMetadataRejectsInconsistentClassicLength(t *testing.T) {
	raw := metadataFixture(9, 4)
	le.PutUint16(raw[24:], 1)
	if _, err := inspectVTF(raw); err == nil {
		t.Fatal("frame count smaller than classic payload accepted")
	}
}

func TestVTFMetadataThumbnailResourceBounds(t *testing.T) {
	old := metadataFixture(1, 4)
	raw := append(make([]byte, 96), old[64:]...)
	raw = append(raw, make([]byte, 8)...)
	copy(raw[:64], old[:64])
	le.PutUint32(raw[8:], 3)
	le.PutUint32(raw[12:], 96)
	le.PutUint16(raw[63:], 1)
	le.PutUint32(raw[57:], 13)
	raw[61], raw[62] = 4, 4
	le.PutUint32(raw[68:], 2)
	raw[80], raw[88] = 0x30, 0x01
	le.PutUint32(raw[84:], 96)
	le.PutUint32(raw[92:], uint32(len(raw)-8))
	_, err := inspectVTF(raw)
	must(t, err)
	for _, mode := range []string{"outside", "overlap", "flags", "duplicate"} {
		t.Run(mode, func(t *testing.T) {
			bad := append([]byte{}, raw...)
			switch mode {
			case "outside":
				le.PutUint32(bad[92:], 0xffffffff)
			case "overlap":
				le.PutUint32(bad[92:], 96)
			case "flags":
				bad[91] = 0xff
			case "duplicate":
				bad[88] = 0x30
			}
			if _, err := inspectVTF(bad); err == nil {
				t.Fatal("invalid thumbnail/resource layout accepted", mode)
			}
		})
	}
}
