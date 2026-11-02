package main

import (
	"bytes"
	"debug/pe"
	"os"
	"testing"
)

// Link the committed resource section into a minimal x64 PE fixture. No dist
// executable, SDK, resource compiler or real application process is required.
func iconPEFixture(t *testing.T) ([]byte, []byte) {
	t.Helper()
	object, e := pe.Open("icon_windows_amd64.syso")
	must(t, e)
	defer object.Close()
	section := object.Section(".rsrc")
	if section == nil {
		t.Fatal("missing COFF resource section")
	}
	data, e := section.Data()
	must(t, e)
	data = bytes.Clone(data)
	for _, r := range section.Relocs {
		if r.Type != 3 || uint64(r.VirtualAddress)+4 > uint64(len(data)) {
			t.Fatal("unexpected resource relocation")
		}
		le.PutUint32(data[r.VirtualAddress:], le.Uint32(data[r.VirtualAddress:])+0x1000)
	}
	raw := make([]byte, 512+(len(data)+511)/512*512)
	copy(raw, "MZ")
	le.PutUint32(raw[60:], 128)
	copy(raw[128:], "PE\x00\x00")
	le.PutUint16(raw[132:], 0x8664)
	le.PutUint16(raw[134:], 1)
	le.PutUint16(raw[148:], 240)
	le.PutUint16(raw[150:], 0x22)
	optional := 152
	le.PutUint16(raw[optional:], 0x20b)
	le.PutUint32(raw[optional+32:], 4096)
	le.PutUint32(raw[optional+36:], 512)
	le.PutUint32(raw[optional+56:], uint32(4096+(len(data)+4095)/4096*4096))
	le.PutUint32(raw[optional+60:], 512)
	le.PutUint32(raw[optional+108:], 16)
	le.PutUint32(raw[optional+128:], 4096)
	le.PutUint32(raw[optional+132:], uint32(len(data)))
	at := 392
	copy(raw[at:], ".rsrc")
	le.PutUint32(raw[at+8:], uint32(len(data)))
	le.PutUint32(raw[at+12:], 4096)
	le.PutUint32(raw[at+16:], uint32(len(raw)-512))
	le.PutUint32(raw[at+20:], 512)
	le.PutUint32(raw[at+36:], 0x40000040)
	copy(raw[512:], data)
	ico, e := os.ReadFile("assets/app.ico")
	must(t, e)
	return raw, ico
}

func TestLinkedIconMatchesSource(t *testing.T) {
	exe, ico := iconPEFixture(t)
	must(t, verifyEmbeddedIcon(exe, ico))
}

func TestStaleLinkedIconRejected(t *testing.T) {
	exe, ico := iconPEFixture(t)
	ico = bytes.Clone(ico)
	ico[len(ico)-1] ^= 1
	if verifyEmbeddedIcon(exe, ico) == nil {
		t.Fatal("stale resource accepted")
	}
}

func TestBrokenIconPERejected(t *testing.T) {
	exe, ico := iconPEFixture(t)
	for _, bad := range [][]byte{nil, exe[:150], exe[:600]} {
		if verifyEmbeddedIcon(bad, ico) == nil {
			t.Fatal("truncated executable accepted")
		}
	}
	if verifyEmbeddedIcon(exe, ico[:32]) == nil {
		t.Fatal("truncated ICO accepted")
	}
}
