package main

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"unicode/utf16"
)

func sprayVPK(t *testing.T, filename string, files map[string][]byte) string {
	t.Helper()
	raw, err := writeVPK(files)
	must(t, err)
	must(t, atomicWrite(filename, raw))
	return filename
}

func numberedTexture(t *testing.T, n int) []byte {
	t.Helper()
	files, err := readVPK(embeddedVPK)
	must(t, err)
	return files[slotPath(n, "vtf")]
}

func TestVPKImportTwoPackagesBuildDeployRollback(t *testing.T) {
	a, _ := fixture(t)
	before := seedGame(t, a)
	dir := t.TempDir()
	one := sprayVPK(t, filepath.Join(dir, "包1.vpk"), map[string][]byte{
		"materials/vgui/logos/1.vtf":    numberedTexture(t, 1),
		"materials/vgui/logos/1.vmt":    []byte(`"UnlitGeneric" { "$basetexture" "vgui/logos/1" }`),
		"materials/vgui/logos/ui/1.vtf": numberedTexture(t, 3),
		"scripts/autoexec.cfg":          []byte("never deploy this"),
	})
	two := sprayVPK(t, filepath.Join(dir, "包2.vpk"), map[string][]byte{
		"MATERIALS/VGUI/LOGOS/1.VTF":     numberedTexture(t, 2),
		"materials/vgui/logos/alias.vmt": []byte("UnlitGeneric { // ignored reference\n $basetexture VGUI\\LOGOS\\1 }"),
	})
	h1, _ := fileHash(one)
	h2, _ := fileHash(two)
	r, err := a.ImportVPKs([]string{two, one})
	must(t, err)
	if r.Total != 2 || r.Imported != 2 || a.State.Slots[1].Source == a.State.Slots[2].Source {
		t.Fatal(r, a.State)
	}
	// Identical member names in separate packages must retain distinct pixels.
	if a.State.Slots[1].SHA256 == a.State.Slots[2].SHA256 {
		t.Fatal("same-named resources overwritten")
	}
	for n := 1; n <= 2; n++ {
		info, e := a.VTFMetadata(n)
		must(t, e)
		if info == nil {
			t.Fatal("VPK metadata missing")
		}
		if _, e = a.Preview(n); !errors.Is(e, errMetadataPreview) {
			t.Fatal("VPK picture preview was not blocked", e)
		}
	}
	state := a.State
	r, err = a.ImportVPKs([]string{one, two})
	must(t, err)
	if r.Imported != 0 || r.Updated != 2 || r.Total != 2 {
		t.Fatal("repeat created duplicates", r)
	}
	for n, row := range state.Slots {
		if row.Source != a.State.Slots[n].Source || row.SHA256 != a.State.Slots[n].SHA256 {
			t.Fatal("selection order changed numbering")
		}
	}
	folder, err := a.Build()
	must(t, err)
	raw, err := os.ReadFile(filepath.Join(folder, "left4dead2/addons", vpkName))
	must(t, err)
	packed, err := readVPK(raw)
	must(t, err)
	if _, exists := packed["scripts/autoexec.cfg"]; exists {
		t.Fatal("unrelated source script deployed")
	}
	for n := 1; n <= 2; n++ {
		if digest(packed[slotPath(n, "vtf")]) != a.State.Slots[n].SHA256 {
			t.Fatal("renumbered build mismatch")
		}
	}
	_, err = a.Deploy(true)
	must(t, err)
	must(t, a.Rollback(true))
	for name, hash := range before {
		after, err := fileHash(filepath.Join(a.Game, filepath.FromSlash(name)))
		must(t, err)
		if hash != after {
			t.Fatal("rollback mismatch", name)
		}
	}
	if after, _ := fileHash(one); after != h1 {
		t.Fatal("original package changed")
	}
	if after, _ := fileHash(two); after != h2 {
		t.Fatal("original package changed")
	}
	t.Log("PASS: two VPKs -> distinct numbered textures -> build -> 81-file fixture deploy -> exact rollback; originals unchanged")
}

func TestVPKImportNaturalOrderAndExternalReference(t *testing.T) {
	a, source := fixture(t)
	must(t, a.Import(source, 20))
	tex := numberedTexture(t, 1)
	pkg := sprayVPK(t, filepath.Join(t.TempDir(), "sprays.vpk"), map[string][]byte{
		"materials/vgui/logos/10.vtf": tex,
		"materials/vgui/logos/2.vtf":  tex,
		"materials/vgui/logos/1.vmt":  []byte(`UnlitGeneric { "$basetexture" "custom/1" }`),
		"materials/custom/1.vtf":      tex,
	})
	r, err := a.ImportVPKs([]string{pkg})
	must(t, err)
	if r.Total != 4 {
		t.Fatal(r)
	}
	for i, title := range []string{"1.vtf", "2.vtf", "10.vtf", "own.png"} {
		if a.State.Slots[i+1].Title != title {
			t.Fatal(a.State)
		}
	}
}

func TestVPKImportFailuresDoNotCommit(t *testing.T) {
	tex := numberedTexture(t, 1)
	for _, scenario := range []string{"corrupt-second", "bad-texture", "missing-reference", "traversal", "case-collision", "empty", "animated", "over40", "merged-over40", "external-volume", "truncated", "vmt-comment"} {
		t.Run(scenario, func(t *testing.T) {
			a, source := fixture(t)
			must(t, a.Import(source, 1))
			if scenario == "merged-over40" {
				for i := 2; i <= 40; i++ {
					a.State.Slots[i] = a.State.Slots[1]
				}
				must(t, saveJSON(filepath.Join(a.Home, "slots.json"), a.State))
			}
			before, err := os.ReadFile(filepath.Join(a.Home, "slots.json"))
			must(t, err)
			state := a.State
			files := map[string][]byte{"materials/vgui/logos/1.vtf": tex}
			switch scenario {
			case "bad-texture":
				files["materials/vgui/logos/2.vtf"] = []byte("broken")
			case "missing-reference":
				files["materials/vgui/logos/1.vmt"] = []byte(`UnlitGeneric { $basetexture missing }`)
			case "traversal":
				files["../outside.txt"] = []byte("outside")
			case "case-collision":
				files["MATERIALS/VGUI/LOGOS/1.VTF"] = tex
			case "empty":
				files = map[string][]byte{"addoninfo.txt": []byte("not a spray")}
			case "animated":
				anim := append([]byte{}, tex...)
				le.PutUint16(anim[24:], 2)
				files["materials/vgui/logos/1.vtf"] = anim
			case "over40":
				for i := 2; i <= 41; i++ {
					files[fmt.Sprintf("materials/vgui/logos/%d.vtf", i)] = tex
				}
			case "vmt-comment":
				files["materials/vgui/logos/1.vmt"] = []byte("UnlitGeneric { // $basetexture fake\n }")
			}
			pkg := sprayVPK(t, filepath.Join(t.TempDir(), "test.vpk"), files)
			paths := []string{pkg}
			if scenario == "corrupt-second" {
				bad := filepath.Join(t.TempDir(), "bad.vpk")
				must(t, atomicWrite(bad, []byte("broken")))
				paths = append(paths, bad)
			}
			if scenario == "external-volume" || scenario == "truncated" {
				raw, err := os.ReadFile(pkg)
				must(t, err)
				if scenario == "external-volume" {
					at := bytes.Index(raw, []byte("1\x00")) + 2
					le.PutUint16(raw[at+6:], 0)
				} else {
					raw = raw[:len(raw)-10]
				}
				must(t, atomicWrite(pkg, raw))
			}
			if _, err = a.ImportVPKs(paths); err == nil {
				t.Fatal("invalid import accepted")
			}
			after, err := os.ReadFile(filepath.Join(a.Home, "slots.json"))
			must(t, err)
			if !bytes.Equal(before, after) || !reflect.DeepEqual(state, a.State) {
				t.Fatal("failed batch changed catalog")
			}
		})
	}
}

func TestVPKImportSelectionLimits(t *testing.T) {
	a, _ := fixture(t)
	for _, paths := range [][]string{nil, {"1.vpk", "2.vpk", "3.vpk"}, {"bad.png"}} {
		if _, err := a.ImportVPKs(paths); err == nil {
			t.Fatal(paths)
		}
	}
	pkg := sprayVPK(t, filepath.Join(t.TempDir(), "test.vpk"), map[string][]byte{"materials/vgui/logos/1.vtf": numberedTexture(t, 1)})
	if _, err := a.ImportVPKs([]string{pkg, strings.ToUpper(pkg)}); err == nil {
		t.Fatal("duplicate package accepted")
	}
}

func TestVPKImportVersion2AndCRC(t *testing.T) {
	a, _ := fixture(t)
	raw, err := writeVPK(map[string][]byte{"materials/vgui/logos/1.vtf": numberedTexture(t, 1)})
	must(t, err)
	v2 := append(make([]byte, 28), raw[12:]...)
	copy(v2[:12], raw[:12])
	le.PutUint32(v2[4:], 2)
	le.PutUint32(v2[12:], uint32(len(raw)-12)-le.Uint32(raw[8:]))
	filename := filepath.Join(t.TempDir(), "v2.vpk")
	must(t, atomicWrite(filename, v2))
	_, err = a.ImportVPKs([]string{filename})
	must(t, err)
	v2[len(v2)-1] ^= 1
	must(t, atomicWrite(filename, v2))
	if _, err = a.ImportVPKs([]string{filename}); err == nil {
		t.Fatal("CRC failure accepted")
	}
}

func TestVPKDialogSelection(t *testing.T) {
	for _, c := range []struct {
		Input string
		Want  []string
		Bad   bool
	}{
		{"\x00", nil, false},
		{"C:\\素材\\1.vpk\x00\x00", []string{`C:\素材\1.vpk`}, false},
		{"C:\\素材\x001.vpk\x002.vpk\x00\x00", []string{`C:\素材\1.vpk`, `C:\素材\2.vpk`}, false},
		{"C:\\素材\x001.vpk\x002.vpk\x003.vpk\x00\x00", nil, true},
		{"C:\\素材\x00..\\evil.vpk\x00\x00", nil, true},
	} {
		got, err := selectedVPKPaths(utf16.Encode([]rune(c.Input)))
		if (err != nil) != c.Bad || !reflect.DeepEqual(got, c.Want) {
			t.Fatal(c, got, err)
		}
	}
}
