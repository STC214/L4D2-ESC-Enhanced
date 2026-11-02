package main

import (
	"bytes"
	"image"
	"image/color"
	"image/gif"
	"image/jpeg"
	"math/rand"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"testing"
	"unicode/utf16"
	"unsafe"
)

func fixture(t *testing.T) (*App, string) {
	t.Helper()
	root := t.TempDir()
	a, e := newApp(filepath.Join(root, "data"), filepath.Join(root, "game"))
	if e != nil {
		t.Fatal(e)
	}
	img := image.NewNRGBA(image.Rect(0, 0, 128, 64))
	for y := 0; y < 64; y++ {
		for x := 0; x < 128; x++ {
			img.SetNRGBA(x, y, color.NRGBA{R: 240, G: 40, B: 20, A: 128})
		}
	}
	source := filepath.Join(root, "own.png")
	if e = savePNG(source, img); e != nil {
		t.Fatal(e)
	}
	return a, source
}
func must(t *testing.T, e error) {
	t.Helper()
	if e != nil {
		t.Fatal(e)
	}
}
func seedGame(t *testing.T, a *App) map[string]string {
	t.Helper()
	must(t, atomicWrite(filepath.Join(a.Game, "left4dead2/gameinfo.txt"), []byte(`"GameInfo" { "FileSystem" { "SearchPaths" { Game update } } }`)))
	must(t, atomicWrite(filepath.Join(a.Game, "bin/neko/plugins/CSPSelector.dll"), []byte("fixture-only-not-loaded")))
	files, e := readVPK(embeddedVPK)
	must(t, e)
	hashes := map[string]string{}
	for _, p := range expectedPaths() {
		b := embeddedVPK
		if strings.HasPrefix(p, "update/") {
			b = files[strings.TrimPrefix(p, "update/")]
		}
		must(t, atomicWrite(filepath.Join(a.Game, filepath.FromSlash(p)), b))
		hashes[p] = digest(b)
	}
	return hashes
}

func TestEmbeddedVPK(t *testing.T) {
	files, e := readVPK(embeddedVPK)
	must(t, e)
	if len(files) != 167 {
		t.Fatal(len(files))
	}
	out, e := writeVPK(files)
	must(t, e)
	out2, e := writeVPK(files)
	must(t, e)
	if !bytes.Equal(out, out2) {
		t.Fatal("non-deterministic VPK")
	}
}
func TestVPKRejectsCorruption(t *testing.T) {
	b := append([]byte{}, embeddedVPK...)
	b[len(b)-1] ^= 255
	if _, e := readVPK(b); e == nil {
		t.Fatal("CRC not checked")
	}
	for _, raw := range [][]byte{nil, b[:8], b[:50]} {
		if _, e := readVPK(raw); e == nil {
			t.Fatal("truncation accepted")
		}
	}
}
func TestSlotsAndPaths(t *testing.T) {
	for _, n := range []int{0, -1, 41} {
		if validSlot(n) == nil {
			t.Fatal(n)
		}
	}
	for _, s := range []string{"../outside", "C:/outside", "../../evil"} {
		if _, e := safePath(t.TempDir(), s); e == nil {
			t.Fatal(s)
		}
	}
}
func TestPNGScaleAlphaAndVTF(t *testing.T) {
	_, path := fixture(t)
	img, e := loadImage(path)
	must(t, e)
	if img.Bounds().Dx() != 256 || img.NRGBAAt(0, 0).A != 0 || img.NRGBAAt(128, 128).A != 128 {
		t.Fatal("aspect/alpha")
	}
	b := encodeVTF(img)
	if len(b) != 262224 {
		t.Fatal(len(b))
	}
	decoded, e := decodeVTF(b)
	must(t, e)
	if !bytes.Equal(img.Pix, decoded.Pix) {
		t.Fatal("RGBA roundtrip")
	}
}
func TestJPEGAndStaticGIF(t *testing.T) {
	a, path := fixture(t)
	img, e := loadImage(path)
	must(t, e)
	for _, ext := range []string{"jpg", "gif"} {
		p := filepath.Join(a.Home, "input."+ext)
		must(t, os.MkdirAll(a.Home, 0755))
		f, e := os.Create(p)
		must(t, e)
		if ext == "jpg" {
			e = jpeg.Encode(f, img, nil)
		} else {
			e = gif.Encode(f, img, nil)
		}
		f.Close()
		must(t, e)
		_, e = loadImage(p)
		must(t, e)
	}
}
func TestDXT(t *testing.T) {
	for _, format := range []uint32{13, 14, 15} {
		header := encodeVTF(image.NewNRGBA(image.Rect(0, 0, 256, 256)))[:80]
		le.PutUint16(header[16:], 4)
		le.PutUint16(header[18:], 4)
		le.PutUint32(header[52:], format)
		block := make([]byte, 8)
		le.PutUint16(block, 0xf800)
		if format == 14 {
			block = append(bytes.Repeat([]byte{255}, 8), block...)
		}
		if format == 15 {
			alpha := make([]byte, 8)
			alpha[0] = 255
			block = append(alpha, block...)
		}
		img, e := decodeVTF(append(header, block...))
		must(t, e)
		if img.NRGBAAt(0, 0) != (color.NRGBA{R: 255, A: 255}) {
			t.Fatal(format, img.NRGBAAt(0, 0))
		}
	}
}
func TestVTFResourcesAndBadInputs(t *testing.T) {
	img := image.NewNRGBA(image.Rect(0, 0, 256, 256))
	raw := encodeVTF(img)
	header := make([]byte, 88)
	copy(header, raw[:80])
	le.PutUint32(header[8:], 3)
	le.PutUint32(header[12:], 88)
	le.PutUint32(header[68:], 1)
	header[80] = 0x30
	le.PutUint32(header[84:], 88)
	_, e := decodeVTF(append(header, raw[80:]...))
	must(t, e)
	bad := append([]byte{}, raw...)
	le.PutUint16(bad[24:], 2)
	for _, b := range [][]byte{nil, raw[:79], bad} {
		if _, e := decodeVTF(b); e == nil {
			t.Fatal("bad VTF accepted")
		}
	}
}
func TestBMP24(t *testing.T) {
	raw := make([]byte, 58)
	copy(raw, "BM")
	le.PutUint32(raw[10:], 54)
	le.PutUint32(raw[14:], 40)
	le.PutUint32(raw[18:], 1)
	le.PutUint32(raw[22:], 1)
	le.PutUint16(raw[26:], 1)
	le.PutUint16(raw[28:], 24)
	raw[56] = 255
	img, e := decodeBMP(raw)
	must(t, e)
	if img.NRGBAAt(0, 0).R != 255 {
		t.Fatal("BMP channels")
	}
}
func TestImportRetainsGeneration(t *testing.T) {
	a, path := fixture(t)
	must(t, a.Import(path, 17))
	old := a.State.Slots[17]
	must(t, a.Import(path, 17))
	if old.Texture == a.State.Slots[17].Texture {
		t.Fatal("generation overwritten")
	}
	p, e := safePath(a.Home, old.Texture)
	must(t, e)
	_, e = os.Stat(p)
	must(t, e)
	_, e = a.Preview(17)
	must(t, e)
}
func TestBuildOnlyOneTexture(t *testing.T) {
	a, path := fixture(t)
	must(t, a.Import(path, 17))
	folder, e := a.Build()
	must(t, e)
	b, e := os.ReadFile(filepath.Join(folder, "left4dead2/addons/"+vpkName))
	must(t, e)
	before, e := readVPK(embeddedVPK)
	must(t, e)
	after, e := readVPK(b)
	must(t, e)
	count := 0
	for name, data := range before {
		if !bytes.Equal(data, after[name]) {
			count++
			if name != slotPath(17, "vtf") {
				t.Fatal(name)
			}
		}
	}
	if count != 1 {
		t.Fatal(count)
	}
}
func TestIncrementalAndStaleBuild(t *testing.T) {
	a, path := fixture(t)
	seedGame(t, a)
	must(t, a.Import(path, 1))
	_, e := a.Build()
	must(t, e)
	must(t, a.Import(path, 40))
	if _, e = a.Deploy(true); e == nil {
		t.Fatal("stale build accepted")
	}
	_, e = a.Build()
	must(t, e)
	_, e = a.Deploy(true)
	must(t, e)
}
func TestDeployRollbackAndGuards(t *testing.T) {
	a, path := fixture(t)
	before := seedGame(t, a)
	must(t, a.Import(path, 17))
	_, e := a.Build()
	must(t, e)
	_, e = a.Deploy(true)
	must(t, e)
	p := filepath.Join(a.Game, "update", filepath.FromSlash(slotPath(17, "vtf")))
	h, e := fileHash(p)
	must(t, e)
	if h == before["update/"+slotPath(17, "vtf")] {
		t.Fatal("no deployment")
	}
	must(t, a.Rollback(true))
	for p, h := range before {
		actual, e := fileHash(filepath.Join(a.Game, filepath.FromSlash(p)))
		must(t, e)
		if actual != h {
			t.Fatal(p)
		}
	}
}
func TestExternalChangeBlocksWholeRollback(t *testing.T) {
	a, path := fixture(t)
	seedGame(t, a)
	must(t, a.Import(path, 17))
	_, e := a.Build()
	must(t, e)
	_, e = a.Deploy(true)
	must(t, e)
	vpkPath := filepath.Join(a.Game, "left4dead2/addons/"+vpkName)
	before, e := fileHash(vpkPath)
	must(t, e)
	must(t, atomicWrite(filepath.Join(a.Game, "update", filepath.FromSlash(slotPath(40, "vtf"))), []byte("external")))
	if e = a.Rollback(true); e == nil {
		t.Fatal("external change overwritten")
	}
	after, e := fileHash(vpkPath)
	must(t, e)
	if before != after {
		t.Fatal("partial rollback")
	}
}
func TestTamperedSourceAndBuild(t *testing.T) {
	a, path := fixture(t)
	before := seedGame(t, a)
	must(t, a.Import(path, 17))
	folder, e := a.Build()
	must(t, e)
	must(t, atomicWrite(filepath.Join(folder, "update", filepath.FromSlash(slotPath(17, "vtf"))), []byte("corrupt")))
	if _, e = a.Deploy(true); e == nil {
		t.Fatal("corruption accepted")
	}
	for p, h := range before {
		actual, e := fileHash(filepath.Join(a.Game, filepath.FromSlash(p)))
		must(t, e)
		if actual != h {
			t.Fatal("wrote despite preflight error")
		}
	}
	source, _ := safePath(a.Home, a.State.Slots[17].Texture)
	must(t, atomicWrite(source, []byte("changed")))
	if _, e = a.Build(); e == nil {
		t.Fatal("bad source accepted")
	}
}
func TestWrongMODMapping(t *testing.T) {
	a, _ := fixture(t)
	seedGame(t, a)
	must(t, atomicWrite(filepath.Join(a.Game, "left4dead2/gameinfo.txt"), []byte(`SearchPaths { Game another }`)))
	if a.validateGame() == nil {
		t.Fatal("wrong MOD accepted")
	}
}

func TestExternalStateChangeBlocksBuildAndImport(t *testing.T) {
	a, path := fixture(t)
	must(t, a.Import(path, 1))
	other, e := newApp(a.Home, a.Game)
	must(t, e)
	must(t, other.Import(path, 40))
	before, e := fileHash(filepath.Join(a.Home, "slots.json"))
	must(t, e)
	if _, e = a.Build(); e == nil {
		t.Fatal("stale in-memory state built against newer disk manifest")
	}
	if e = a.Import(path, 2); e == nil {
		t.Fatal("external state overwritten")
	}
	after, e := fileHash(filepath.Join(a.Home, "slots.json"))
	must(t, e)
	if before != after {
		t.Fatal("external state changed")
	}
}

func TestPendingTransactionBlocksNewDeployment(t *testing.T) {
	a, path := fixture(t)
	seedGame(t, a)
	must(t, a.Import(path, 17))
	_, e := a.Build()
	must(t, e)
	tx, e := a.Deploy(true)
	must(t, e)
	var journal Transaction
	must(t, loadJSON(filepath.Join(tx, "transaction.json"), &journal))
	journal.Status = "PREPARED"
	must(t, saveJSON(filepath.Join(tx, "transaction.json"), journal))
	before, e := fileHash(filepath.Join(a.Home, "last-deploy.json"))
	must(t, e)
	if _, e = a.Deploy(true); e == nil {
		t.Fatal("pending recovery pointer overwritten")
	}
	after, e := fileHash(filepath.Join(a.Home, "last-deploy.json"))
	must(t, e)
	if before != after {
		t.Fatal("recovery pointer changed")
	}
	must(t, a.Rollback(true))
}

func TestGIFPreflightRejectsAnimationAndTruncation(t *testing.T) {
	frame := image.NewPaletted(image.Rect(0, 0, 2, 2), color.Palette{color.Black, color.White})
	var single bytes.Buffer
	must(t, gif.Encode(&single, frame, nil))
	must(t, validateStaticGIF(single.Bytes()))
	var animation bytes.Buffer
	must(t, gif.EncodeAll(&animation, &gif.GIF{Image: []*image.Paletted{frame, frame}, Delay: []int{1, 1}}))
	if validateStaticGIF(animation.Bytes()) == nil {
		t.Fatal("animation accepted")
	}
	for n := 0; n < len(single.Bytes()); n++ {
		if validateStaticGIF(single.Bytes()[:n]) == nil {
			t.Fatalf("truncated GIF accepted at %d", n)
		}
	}
}

func TestMalformedParsersDoNotPanic(t *testing.T) {
	rng := rand.New(rand.NewSource(42))
	for n := 0; n < 300; n++ {
		raw := make([]byte, rng.Intn(2048))
		_, _ = rng.Read(raw)
		if len(raw) >= 80 {
			copy(raw, "VTF\x00")
			le.PutUint32(raw[4:], 7)
			le.PutUint32(raw[8:], uint32(rng.Intn(6)))
			le.PutUint32(raw[12:], 80)
			le.PutUint16(raw[16:], uint16(1+rng.Intn(64)))
			le.PutUint16(raw[18:], uint16(1+rng.Intn(64)))
			le.PutUint32(raw[20:], 0)
			le.PutUint16(raw[24:], 1)
			le.PutUint16(raw[63:], 1)
		}
		_, _ = decodeVTF(raw)
		_, _ = decodeBMP(raw)
		_, _ = readVPK(raw)
	}
}

func TestBaseLinkBlocksAllWrites(t *testing.T) {
	root := t.TempDir()
	real := filepath.Join(root, "real")
	link := filepath.Join(root, "linked")
	must(t, os.Mkdir(real, 0755))
	// NTFS junctions do not require the symbolic-link privilege. Keep both
	// the reparse point and its destination inside this disposable fixture.
	must(t, os.Mkdir(link, 0755))
	name, e := syscall.UTF16PtrFromString(link)
	must(t, e)
	handle, e := syscall.CreateFile(name, syscall.GENERIC_WRITE, syscall.FILE_SHARE_READ|syscall.FILE_SHARE_WRITE|syscall.FILE_SHARE_DELETE, nil, syscall.OPEN_EXISTING, 0x02200000, 0)
	must(t, e)
	substitute := utf16.Encode([]rune(`\??\` + real))
	printName := utf16.Encode([]rune(real))
	buffer := make([]byte, 16+(len(substitute)+len(printName)+2)*2)
	le.PutUint32(buffer, 0xa0000003)
	le.PutUint16(buffer[4:], uint16(len(buffer)-8))
	le.PutUint16(buffer[10:], uint16(len(substitute)*2))
	le.PutUint16(buffer[12:], uint16((len(substitute)+1)*2))
	le.PutUint16(buffer[14:], uint16(len(printName)*2))
	for i, v := range append(append(append(substitute, 0), printName...), 0) {
		le.PutUint16(buffer[16+i*2:], v)
	}
	var returned uint32
	e = syscall.DeviceIoControl(handle, 0x900a4, (*byte)(unsafe.Pointer(&buffer[0])), uint32(len(buffer)), nil, 0, &returned, nil)
	syscall.CloseHandle(handle)
	must(t, e)
	if _, e := safePath(link, "image.vtf"); e == nil {
		t.Fatal("linked root accepted")
	}
	if atomicWrite(filepath.Join(link, "image.vtf"), []byte("outside")) == nil {
		t.Fatal("write through linked root accepted")
	}
	if _, e := os.Stat(filepath.Join(real, "image.vtf")); !os.IsNotExist(e) {
		t.Fatal("linked destination written")
	}
}
