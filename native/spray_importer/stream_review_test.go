package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"unicode/utf8"
)

type observedAPNGReader struct {
	r          io.Reader
	maxRequest int
}

func (r *observedAPNGReader) Read(p []byte) (int, error) {
	r.maxRequest = max(r.maxRequest, len(p))
	return r.r.Read(p)
}

func TestReviewAPNGForgedLengthReadBound(t *testing.T) {
	// Valid prefix controls, then an IDAT claiming 100 MiB but containing no
	// payload. Reject without allocating/requesting the claimed payload size.
	var source bytes.Buffer
	source.WriteString("\x89PNG\r\n\x1a\n")
	header := make([]byte, 13)
	be.PutUint32(header, 4)
	be.PutUint32(header[4:], 4)
	header[8], header[9] = 8, 6
	pngChunk(&source, "IHDR", header)
	actl := make([]byte, 8)
	be.PutUint32(actl, 1)
	pngChunk(&source, "acTL", actl)
	frame := make([]byte, 26)
	be.PutUint32(frame[4:], 4)
	be.PutUint32(frame[8:], 4)
	pngChunk(&source, "fcTL", frame)
	var h [8]byte
	be.PutUint32(h[:], 100<<20)
	copy(h[4:], "IDAT")
	source.Write(h[:])
	reader := &observedAPNGReader{r: bytes.NewReader(source.Bytes())}
	if _, _, _, err := parseAPNGReader(reader); err == nil {
		t.Fatal("forged length accepted")
	}
	if reader.maxRequest > 32<<10 {
		t.Fatalf("unbounded retained-payload read request: %d bytes", reader.maxRequest)
	}
}

func TestReviewDiagnosticsOversizedErrorBounded(t *testing.T) {
	home := t.TempDir()
	message := strings.Repeat("错", (5<<20)/3)
	must(t, recordFailure(home, errors.New(message)))
	first, err := os.ReadFile(filepath.Join(home, "logs/last-error.json"))
	must(t, err)
	var record map[string]string
	must(t, json.Unmarshal(first, &record))
	if !utf8.ValidString(record["Error"]) || !strings.Contains(record["Error"], "诊断文本已截断") {
		t.Fatal("missing truncation notice or broken UTF-8")
	}
	for _, name := range []string{"last-error.json", "errors.jsonl"} {
		stat, err := os.Stat(filepath.Join(home, "logs", name))
		must(t, err)
		if stat.Size() > 4<<20 {
			t.Fatalf("diagnostic %s exceeds history bound: %d", name, stat.Size())
		}
	}
	// A single unusual message must not permanently block subsequent records.
	must(t, recordFailure(home, errors.New("normal subsequent error")))
	latest, err := os.ReadFile(filepath.Join(home, "logs/last-error.json"))
	must(t, err)
	if !bytes.Contains(latest, []byte("normal subsequent error")) {
		t.Fatal("latest error not updated")
	}
}

func FuzzAPNGStreamStructure(f *testing.F) {
	var seed bytes.Buffer
	seed.WriteString("\x89PNG\r\n\x1a\n")
	header := make([]byte, 13)
	be.PutUint32(header, 4)
	be.PutUint32(header[4:], 4)
	header[8], header[9] = 8, 6
	pngChunk(&seed, "IHDR", header)
	control := make([]byte, 8)
	be.PutUint32(control, 1)
	pngChunk(&seed, "acTL", control)
	frame := make([]byte, 26)
	be.PutUint32(frame[4:], 4)
	be.PutUint32(frame[8:], 4)
	pngChunk(&seed, "fcTL", frame)
	pngChunk(&seed, "IDAT", []byte{0})
	pngChunk(&seed, "IEND", nil)
	f.Add(seed.Bytes())
	f.Add([]byte{})
	f.Add(seed.Bytes()[:len(seed.Bytes())-1])
	f.Fuzz(func(t *testing.T, raw []byte) {
		if len(raw) > 256<<10 {
			return
		}
		_, _, _, _ = parseAPNGReader(bytes.NewReader(raw))
	})
}
