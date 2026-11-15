package main

import (
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestReviewMaterialStructure(t *testing.T) {
	for _, text := range []string{
		`UnlitGeneric { "$basetexture" "vgui/logos/1"`,
		`UnlitGeneric { "$note" "$basetexture" "vgui/logos/1" "ignored" }`,
		`UnlitGeneric { Proxies { Example { "$basetexture" "vgui/logos/1" } } }`,
		`UnlitGeneric { "$basetexture" "vgui/logos/1" } trailing`,
		`UnlitGeneric { "$basetexture" "vgui/logos/1" "$basetexture" "vgui/logos/2" }`,
	} {
		files := map[string][]byte{
			"materials/vgui/logos/1.vmt": []byte(text),
			"materials/vgui/logos/1.vtf": []byte("texture"),
			"materials/vgui/logos/2.vtf": []byte("texture"),
		}
		if _, err := sprayMembers(files); err == nil {
			t.Errorf("malformed or ambiguous material accepted: %s", text)
		}
	}
}

func TestReviewMaterialBlockComments(t *testing.T) {
	files := map[string][]byte{
		"materials/vgui/logos/1.vmt": []byte("\xef\xbb\xbfUnlitGeneric { /* $basetexture missing */ \n $basetexture \"vgui/logos/1\" }"),
		"materials/vgui/logos/1.vtf": []byte("texture"),
	}
	names, err := sprayMembers(files)
	must(t, err)
	if len(names) != 1 {
		t.Fatal(names)
	}
}

func TestReviewVPKSectionBoundaries(t *testing.T) {
	raw, err := writeVPK(map[string][]byte{"file.bin": []byte("payload")})
	must(t, err)
	v2 := append(make([]byte, 28), raw[12:]...)
	copy(v2[:12], raw[:12])
	le.PutUint32(v2[4:], 2)
	// Declare zero file-data bytes: the payload is a footer, not file data.
	le.PutUint32(v2[24:], uint32(len(raw)-12)-le.Uint32(raw[8:]))
	if _, err = readVPK(v2); err == nil {
		t.Error("entry read from VPK v2 footer accepted")
	}
	le.PutUint32(v2[12:], 0xffffffff)
	if _, err = readVPK(v2); err == nil {
		t.Error("impossible v2 section sizes accepted")
	}
}

func TestReviewVPKPreloadOnlyOffset(t *testing.T) {
	// A preload-only member has no archive payload; its offset is unused.
	raw, err := writeVPK(map[string][]byte{"file.bin": []byte("x")})
	must(t, err)
	end := 12 + int(le.Uint32(raw[8:]))
	at := bytes.Index(raw[:end], []byte("file\x00")) + 5
	tree := append([]byte{}, raw[12:end]...)
	le.PutUint16(tree[at-12+4:], 1)
	le.PutUint16(tree[at-12+6:], 0xffff)
	le.PutUint32(tree[at-12+8:], 0xffffffff)
	le.PutUint32(tree[at-12+12:], 0)
	tree = append(tree[:at-12+18], append([]byte{'x'}, tree[at-12+18:]...)...)
	preload := append(append([]byte{}, raw[:12]...), tree...)
	le.PutUint32(preload[8:], uint32(len(tree)))
	files, err := readVPK(preload)
	must(t, err)
	if string(files["file.bin"]) != "x" {
		t.Fatal(files)
	}
}

func TestReviewVPKOwnDataSource(t *testing.T) {
	a, _ := fixture(t)
	pkg := sprayVPK(t, filepath.Join(a.Home, "builds", "self.vpk"), map[string][]byte{"materials/vgui/logos/1.vtf": numberedTexture(t, 1)})
	if _, err := a.ImportVPKs([]string{pkg}); err == nil {
		t.Fatal("generated tool data reimported as original VPK")
	}
}

func TestReviewVPKStagingCleanup(t *testing.T) {
	for _, bad := range []bool{false, true} {
		a, _ := fixture(t)
		tex := numberedTexture(t, 1)
		if bad {
			tex = []byte("broken")
		}
		pkg := sprayVPK(t, filepath.Join(t.TempDir(), "test.vpk"), map[string][]byte{"materials/vgui/logos/1.vtf": tex})
		_, err := a.ImportVPKs([]string{pkg})
		if (err != nil) != bad {
			t.Fatal(err)
		}
		must(t, filepath.WalkDir(a.Home, func(name string, entry os.DirEntry, err error) error {
			if os.IsNotExist(err) {
				return nil
			}
			if err != nil {
				return err
			}
			if !entry.IsDir() && strings.Contains(name, "vpk-sources") {
				t.Errorf("raw staging file retained: %s", name)
			}
			return nil
		}))
	}
}

func TestReviewDialogTruncation(t *testing.T) {
	for _, buf := range [][]uint16{{'C', ':', '\\', 'a'}, {'C', ':', '\\', 'a', 0, 'b'}} {
		if _, err := selectedVPKPaths(buf); err == nil {
			t.Errorf("truncated selection accepted: %v", buf)
		}
	}
}

func TestReviewVPKRequiresVTFPayload(t *testing.T) {
	a, source := fixture(t)
	png, err := os.ReadFile(source)
	must(t, err)
	pkg := sprayVPK(t, filepath.Join(t.TempDir(), "fake.vpk"), map[string][]byte{"materials/vgui/logos/fake.vtf": png})
	if _, err = a.ImportVPKs([]string{pkg}); err == nil {
		t.Fatal("PNG mislabeled as VTF accepted from VPK")
	}
}

func TestReviewTwoVPKsAtCapacityAndOverflow(t *testing.T) {
	a, _ := fixture(t)
	dir := t.TempDir()
	tex := numberedTexture(t, 1)
	files := map[string][]byte{}
	for i := 1; i <= 20; i++ {
		files[fmt.Sprintf("materials/vgui/logos/%d.vtf", i)] = tex
	}
	one := sprayVPK(t, filepath.Join(dir, "pack1.vpk"), files)
	two := sprayVPK(t, filepath.Join(dir, "pack2.vpk"), files)
	r, err := a.ImportVPKs([]string{two, one})
	must(t, err)
	if r.Total != 40 || r.Imported != 40 {
		t.Fatal(r)
	}
	for n := 1; n <= 40; n++ {
		if a.State.Slots[n].Title != fmt.Sprintf("%d.vtf", (n+1)/2) {
			t.Fatal("natural numbering wrong", n, a.State.Slots[n])
		}
	}
	r, err = a.ImportVPKs([]string{one, two})
	must(t, err)
	if r.Imported != 0 || r.Updated != 40 || r.Total != 40 {
		t.Fatal("repeat at full capacity failed", r)
	}
	before, err := fileHash(filepath.Join(a.Home, "slots.json"))
	must(t, err)
	files["materials/vgui/logos/21.vtf"] = tex
	sprayVPK(t, two, files)
	if _, err = a.ImportVPKs([]string{one, two}); err == nil {
		t.Fatal("combined 41 images accepted")
	}
	after, err := fileHash(filepath.Join(a.Home, "slots.json"))
	must(t, err)
	if before != after {
		t.Fatal("overflow changed existing catalog")
	}
}

func TestReviewMaterialLimitsAndQuotedValues(t *testing.T) {
	for _, bad := range []string{
		`UnlitGeneric { $basetexture "unterminated }`,
		"UnlitGeneric { /* unterminated",
		"UnlitGeneric { $basetexture \"a\x00b\" }",
		"UnlitGeneric { " + strings.Repeat("nested { ", 40) + "$basetexture a " + strings.Repeat("}", 41),
		"UnlitGeneric { $basetexture a " + strings.Repeat("key value ", 17000) + "}",
		strings.Repeat("x", (1<<20)+1),
	} {
		if _, err := materialTexture([]byte(bad)); err == nil {
			t.Error("invalid/unbounded material accepted")
		}
	}
	got, err := materialTexture([]byte(`UnlitGeneric { "$note" "{ // literal }" "$basetexture" "vgui\logos\1" Proxies { Example { "$basetexture" "not-root" } } }`))
	must(t, err)
	if got != `vgui\logos\1` {
		t.Fatal(got)
	}
}

func TestReviewVPKFileCountLimit(t *testing.T) {
	tree := []byte("bin\x00empty\x00")
	for i := 0; i <= 10000; i++ {
		tree = append(tree, []byte(fmt.Sprintf("%d\x00", i))...)
		entry := make([]byte, 18)
		le.PutUint16(entry[6:], 0x7fff)
		le.PutUint16(entry[16:], 0xffff)
		tree = append(tree, entry...)
	}
	tree = append(tree, 0, 0, 0)
	raw := make([]byte, 12)
	le.PutUint32(raw, 0x55aa1234)
	le.PutUint32(raw[4:], 1)
	le.PutUint32(raw[8:], uint32(len(tree)))
	raw = append(raw, tree...)
	if _, err := readVPK(raw); err == nil {
		t.Fatal("over 10000 members accepted")
	}
}

func FuzzVPKMaterialParsers(f *testing.F) {
	raw, err := writeVPK(map[string][]byte{"file.bin": []byte("payload")})
	if err != nil {
		f.Fatal(err)
	}
	f.Add(raw)
	f.Add([]byte(`UnlitGeneric { $basetexture "vgui/logos/1" }`))
	f.Add([]byte{})
	f.Fuzz(func(t *testing.T, data []byte) {
		if len(data) > 65536 {
			return
		}
		readVPK(data)
		materialTexture(data)
		packagePath(string(data))
	})
}
