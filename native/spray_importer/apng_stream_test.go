package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"hash/crc32"
	"image"
	"image/color"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// A >32 MiB ancillary chunk written using a fixed buffer, not a giant bitmap
// or source payload allocation. Every pixel in the animation is self-authored.
func largeAPNGFixture(t *testing.T, path string, corrupt bool) {
	t.Helper()
	frames := make([]ownAPNGFrame, 40)
	for i := range frames {
		frames[i] = ownAPNGFrame{area: image.Rect(0, 0, 4, 4), c: color.NRGBA{R: uint8(i), A: 255}}
	}
	raw := ownAPNG(t, frames, false)
	f, err := os.Create(path)
	must(t, err)
	defer f.Close()
	_, err = f.Write(raw[:33])
	must(t, err)
	var word [4]byte
	be.PutUint32(word[:], 33<<20)
	_, err = f.Write(word[:])
	must(t, err)
	_, err = f.Write([]byte("tEXt"))
	must(t, err)
	hash := crc32.NewIEEE()
	hash.Write([]byte("tEXt"))
	w := io.MultiWriter(f, hash)
	buffer := bytes.Repeat([]byte{'x'}, 32<<10)
	copy(buffer, []byte("fixture\x00"))
	_, err = w.Write(buffer)
	must(t, err)
	for i := 1; i < (33<<20)/len(buffer); i++ {
		_, err = w.Write(buffer)
		must(t, err)
	}
	checksum := hash.Sum32()
	if corrupt {
		checksum ^= 1
	}
	be.PutUint32(word[:], checksum)
	_, err = f.Write(word[:])
	must(t, err)
	_, err = f.Write(raw[33:])
	must(t, err)
	must(t, f.Close())
}

func TestLargeAPNGStreamingSingleAndFolder(t *testing.T) {
	for _, ext := range []string{".apng", ".png"} {
		dir := t.TempDir()
		path := filepath.Join(dir, "own"+ext)
		largeAPNGFixture(t, path, false)
		stat, err := os.Stat(path)
		must(t, err)
		if stat.Size() <= 32<<20 {
			t.Fatal("fixture not large")
		}
		// Prove the old generic reader still protects GIF/VTF/static inputs.
		if _, err := readTextureInput(path); err == nil {
			t.Fatal("baseline 32 MiB guard changed")
		}
		a, _ := fixture(t)
		if ext == ".png" {
			must(t, a.Import(path, 1))
		} else {
			r, err := a.ImportFolder(dir)
			must(t, err)
			if r.Total != 1 {
				t.Fatal(r)
			}
		}
		row := a.State.Slots[1]
		if row.Animation == nil || row.Animation.Original != 40 || row.Animation.Kept != 31 || row.Animation.Bytes >= 512<<10 {
			t.Fatal(row.Animation)
		}
		clip, err := a.LoadPreview(1)
		must(t, err)
		last, err := decodeVTFFrame(clip.Raw, 30)
		must(t, err)
		if last.NRGBAAt(32, 32).R != 30 {
			t.Fatal("prefix changed")
		}
		_, err = a.Build()
		must(t, err)
	}
}

func TestAPNGStreamDiscardedCRCAndBounds(t *testing.T) {
	frames := make([]ownAPNGFrame, 40)
	for i := range frames {
		frames[i] = ownAPNGFrame{area: image.Rect(0, 0, 4, 4), c: color.NRGBA{R: uint8(i), A: 255}}
	}
	raw := ownAPNG(t, frames, false)
	_, _, parsed, err := parseAPNG(raw)
	must(t, err)
	for _, frame := range parsed[31:] {
		if len(frame.data) != 0 || !frame.hasData {
			t.Fatal("discarded pixels retained")
		}
	}
	// The last fdAT belongs to a discarded frame. Its CRC must still be checked.
	bad := append([]byte{}, raw...)
	at := bytes.LastIndex(bad, []byte("fdAT"))
	bad[at+8] ^= 1
	if _, err := convertAPNG(bad); err == nil {
		t.Fatal("discarded frame CRC ignored")
	}
	path := filepath.Join(t.TempDir(), "bad.apng")
	largeAPNGFixture(t, path, true)
	a, _ := fixture(t)
	if err := a.Import(path, 1); err == nil || len(a.State.Slots) != 0 {
		t.Fatal("bad large APNG committed", err)
	}
	var oversized bytes.Buffer
	oversized.WriteString("\x89PNG\r\n\x1a\n")
	var h [8]byte
	be.PutUint32(h[:], apngInputLimit)
	copy(h[4:], "tEXt")
	oversized.Write(h[:])
	if _, _, _, err := parseAPNGReader(&oversized); err == nil || !strings.Contains(err.Error(), "1 GiB") {
		t.Fatal("unbounded chunk", err)
	}
}

func TestFailureDiagnosticsAndRotation(t *testing.T) {
	home := t.TempDir()
	cause := errors.New("C:\\fixture\\large.apng：APNG CRC 异常")
	must(t, recordFailure(home, cause))
	latest, err := os.ReadFile(filepath.Join(home, "logs/last-error.json"))
	must(t, err)
	var row map[string]string
	must(t, json.Unmarshal(latest, &row))
	if row["Error"] != cause.Error() || row["Version"] != "1.7.1" || row["Time"] == "" {
		t.Fatal(row)
	}
	path := filepath.Join(home, "logs/errors.jsonl")
	full := bytes.Repeat([]byte{' '}, 4<<20)
	must(t, atomicWrite(path, full))
	must(t, recordFailure(home, errors.New("second failure")))
	previous, err := os.ReadFile(filepath.Join(home, "logs/errors.previous.jsonl"))
	must(t, err)
	if !bytes.Equal(full, previous) {
		t.Fatal("rotation lost history")
	}
	current, err := os.ReadFile(path)
	must(t, err)
	if !bytes.Contains(current, []byte("second failure")) || len(current) > 4096 {
		t.Fatal("history not bounded")
	}
	if err := recordFailure(home, nil); err != nil {
		t.Fatal(err)
	}
}
