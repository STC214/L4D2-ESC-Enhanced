package main

import (
	"bytes"
	"image"
	"image/color"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestImportMinimumDefaultAndSettings(t *testing.T) {
	a, source := fixture(t)
	a, err := newApp(a.Home, a.Game)
	must(t, err)
	if a.Settings.MinimumAnimationFrames != 30 {
		t.Fatal("production default")
	}
	for _, n := range []int{2, 3, 30, 256} {
		must(t, a.SetMinimumFrames(n))
		b, err := newApp(a.Home, a.Game)
		must(t, err)
		if b.Settings.MinimumAnimationFrames != n {
			t.Fatal("setting not persisted")
		}
	}
	for _, n := range []int{-1, 0, 1, 257} {
		if a.SetMinimumFrames(n) == nil || a.Settings.MinimumAnimationFrames != 256 {
			t.Fatal("invalid setting accepted")
		}
	}
	must(t, a.Import(source, 1))
	if a.State.Slots[1].VTF.Frames != 1 {
		t.Fatal("static source affected")
	}
}

func TestAnimationMinimumFallbackAndProgress(t *testing.T) {
	for _, ext := range []string{"gif", "apng", "png"} {
		for _, threshold := range []int{2, 3, 4, 30} {
			a, _ := fixture(t)
			must(t, a.SetMinimumFrames(threshold))
			frames := make([]ownAPNGFrame, 8)
			for i := range frames {
				frames[i] = ownAPNGFrame{area: image.Rect(0, 0, 4, 4), c: color.NRGBA{R: uint8(i * 20), G: 150, A: 255}}
			}
			raw := ownAPNG(t, frames, true)
			if ext == "gif" {
				raw = ownGIF(t, 1)
			}
			path := filepath.Join(t.TempDir(), "own."+ext)
			must(t, atomicWrite(path, raw))
			last, updates := -1, 0
			a.Progress = func(percent int, stage string) {
				if percent < last || percent > 100 || stage == "" {
					t.Fatal("invalid progress", last, percent, stage)
				}
				last, updates = percent, updates+1
			}
			must(t, a.Import(path, 1))
			row := a.State.Slots[1]
			want := 3
			if threshold > 3 {
				want = 1
			}
			if row.VTF.Frames != want || len(row.Masters) != want || row.Animation.StaticFallback != (want == 1) {
				t.Fatal(ext, threshold, row)
			}
			if want == 1 && (row.VTF.Width != 1020 || !strings.Contains(row.Animation.description(), "第一帧作为静态")) {
				t.Fatal("fallback not high-quality static")
			}
			if last != 100 || updates < 5 {
				t.Fatal("missing real progress", last, updates)
			}
			full, err := prepareTexture(path, false, importOptions{MinimumFrames: 2})
			must(t, err)
			first, err := os.ReadFile(filepath.Join(a.Home, filepath.FromSlash(row.Masters[0])))
			must(t, err)
			masterPath := filepath.Join(t.TempDir(), "first.png")
			must(t, savePNG(masterPath, full.Masters[0]))
			expected, err := os.ReadFile(masterPath)
			must(t, err)
			if !bytes.Equal(first, expected) {
				t.Fatal("not the composited first frame")
			}
		}
	}
}

func TestImportBatchProgressPolicyAndRawPreservation(t *testing.T) {
	a, source := fixture(t)
	must(t, a.SetMinimumFrames(30))
	dir := t.TempDir()
	must(t, atomicWrite(filepath.Join(dir, "a.gif"), ownGIF(t, 1)))
	batchFile(t, source, dir, "b.png")
	last := -1
	a.Progress = func(percent int, stage string) {
		if percent < last {
			t.Fatal("batch progress reversed")
		}
		last = percent
	}
	_, err := a.ImportFolder(dir)
	must(t, err)
	if last != 100 || a.State.Slots[1].VTF.Frames != 1 {
		t.Fatal("batch policy/progress")
	}
	raw := twoFrameVTF(13)
	vpk := sprayVPK(t, filepath.Join(t.TempDir(), "raw.vpk"), map[string][]byte{"materials/vgui/logos/raw.vtf": raw})
	a.Progress = nil
	_, err = a.ImportVPKs([]string{vpk})
	must(t, err)
	for _, row := range a.State.Slots {
		if strings.Contains(row.Source, "::") && (row.VTF.Frames != 2 || row.SHA256 != digest(raw)) {
			t.Fatal("raw VTF altered")
		}
	}
}

func TestCatalogBackupSingleGeneration(t *testing.T) {
	a, source := fixture(t)
	must(t, a.Import(source, 1))
	oldTexture := a.State.Slots[1].Texture
	must(t, a.Import(source, 2))
	_, err := a.ResetDefaults()
	must(t, err)
	must(t, a.Import(source, 3))
	must(t, a.PruneBackups())
	counts := map[string]int{}
	err = filepath.Walk(a.Home, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.Name() == "before.json" || info.Name() == "after.json" {
			counts[info.Name()]++
		}
		return nil
	})
	must(t, err)
	if counts["before.json"] != 1 || counts["after.json"] != 1 {
		t.Fatal(counts)
	}
	if _, err = os.Stat(filepath.Join(a.Home, filepath.FromSlash(oldTexture))); err != nil {
		t.Fatal("old source/master deleted", err)
	}
	if _, err = os.Stat(source); err != nil {
		t.Fatal("input removed")
	}
}

func TestCatalogBackupCleanupGuards(t *testing.T) {
	a, source := fixture(t)
	must(t, a.Import(source, 1))
	var latest string
	must(t, loadJSON(filepath.Join(a.Home, "latest-catalog-backup.json"), &latest))
	for _, keep := range []string{"../outside", "resets/missing", "imports/../x", ""} {
		if pruneCatalogBackups(a.Home, keep) == nil {
			t.Fatal("bad keeper accepted")
		}
	}
	if _, err := os.Stat(filepath.Join(a.Home, filepath.FromSlash(latest), "before.json")); err != nil {
		t.Fatal("backup removed")
	}
	must(t, saveJSON(filepath.Join(a.Home, "slots.json"), State{Slots: map[int]Slot{}}))
	if a.PruneBackups() == nil {
		t.Fatal("external catalog change ignored")
	}
	// A pending game transaction also prevents cleanup following an otherwise
	// successful new catalog commit; keep both old and newly saved snapshots.
	must(t, saveJSON(filepath.Join(a.Home, "slots.json"), a.State))
	rel := "transactions/pending"
	must(t, saveJSON(filepath.Join(a.Home, "last-deploy.json"), rel))
	must(t, saveJSON(filepath.Join(a.Home, filepath.FromSlash(rel), "transaction.json"), Transaction{Status: "PREPARED"}))
	must(t, a.Import(source, 2))
	if a.MaintenanceWarning == "" {
		t.Fatal("pending cleanup not reported")
	}
	if _, err := os.Stat(filepath.Join(a.Home, filepath.FromSlash(latest), "before.json")); err != nil {
		t.Fatal("pending transaction lost old snapshot")
	}
}

func TestImportSettingsMalformedAndWriteFailure(t *testing.T) {
	a, _ := fixture(t)
	must(t, saveJSON(filepath.Join(a.Home, "settings.json"), importSettings{MinimumAnimationFrames: 1}))
	if _, err := newApp(a.Home, a.Game); err == nil {
		t.Fatal("invalid settings loaded")
	}
	must(t, os.Remove(filepath.Join(a.Home, "settings.json")))
	must(t, os.Mkdir(filepath.Join(a.Home, "settings.json"), 0755))
	if a.SetMinimumFrames(30) == nil || a.Settings.MinimumAnimationFrames != 2 {
		t.Fatal("failed settings write changed memory")
	}
	bad := filepath.Join(t.TempDir(), "bad.gif")
	must(t, atomicWrite(bad, []byte("GIF89a broken")))
	last := 0
	a.Progress = func(percent int, stage string) { last = percent }
	if a.Import(bad, 1) == nil || last == 100 || len(a.State.Slots) != 0 {
		t.Fatal("failed import reported completion")
	}
}
