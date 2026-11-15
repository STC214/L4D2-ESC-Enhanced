package main

import (
	"bytes"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

func assertNumberedSlots(t *testing.T, a *App) {
	t.Helper()
	for n, row := range a.State.Slots {
		if row.Title != slotTitle(n) || row.OriginalTitle == "" || filepath.Base(row.Texture) != filepath.Base(slotPath(n, "vtf")) {
			t.Fatal("slot naming mismatch", n, row)
		}
		if row.Preview != "" && !strings.HasPrefix(filepath.Base(row.Preview), "test_"+filepath.Base(slotPath(n, "vtf"))[5:8]+"_") {
			t.Fatal("preview numbering", row)
		}
		data, err := os.ReadFile(filepath.Join(a.Home, filepath.FromSlash(row.Texture)))
		must(t, err)
		if digest(data) != row.SHA256 {
			t.Fatal("renumber changed resource bytes")
		}
	}
}

func TestSlotNamesAcrossImportRoutes(t *testing.T) {
	for _, route := range []string{"single", "folder", "vpk"} {
		a, source := fixture(t)
		before, err := fileHash(source)
		must(t, err)
		switch route {
		case "single":
			must(t, a.Import(source, 17))
		case "folder":
			dir := t.TempDir()
			batchFile(t, source, dir, "x2.png")
			batchFile(t, source, dir, "x10.png")
			_, err = a.ImportFolder(dir)
			must(t, err)
		case "vpk":
			pkg := sprayVPK(t, filepath.Join(t.TempDir(), "own.vpk"), map[string][]byte{"materials/vgui/logos/z.vtf": twoFrameVTF(13)})
			_, err = a.ImportVPKs([]string{pkg})
			must(t, err)
		}
		assertNumberedSlots(t, a)
		after, err := fileHash(source)
		must(t, err)
		if before != after {
			t.Fatal("original source renamed/modified")
		}
		_, err = a.Build()
		must(t, err)
	}
}

func TestSlotResortKeepsNamesSourcesAndHistory(t *testing.T) {
	a, source := fixture(t)
	oldSource := batchFile(t, source, t.TempDir(), "20.png")
	must(t, a.Import(oldSource, 17))
	old := a.State.Slots[17]
	dir := t.TempDir()
	batchFile(t, source, dir, "2.png")
	_, err := a.ImportFolder(dir)
	must(t, err)
	assertNumberedSlots(t, a)
	if a.State.Slots[2].OriginalTitle != "20.png" || a.State.Slots[2].Source != old.Source || a.State.Slots[2].Texture == old.Texture {
		t.Fatal("resort/source identity lost")
	}
	if _, err = os.Stat(filepath.Join(a.Home, filepath.FromSlash(old.Texture))); err != nil {
		t.Fatal("old generation removed", err)
	}
	_, err = a.ImportFolder(dir)
	must(t, err)
	if len(a.State.Slots) != 2 {
		t.Fatal("renaming broke repeated import identity")
	}
	// Simulate an earlier unnumbered catalog; a later manual import upgrades all
	// active names without altering old catalog files or original title sorting.
	legacy := a.State.Slots[2]
	legacy.Title = "20.png"
	legacy.OriginalTitle = ""
	a.State.Slots[2] = legacy
	must(t, saveJSON(filepath.Join(a.Home, "slots.json"), a.State))
	must(t, a.Import(source, 3))
	assertNumberedSlots(t, a)
	if a.State.Slots[2].OriginalTitle != "20.png" {
		t.Fatal("legacy title not retained")
	}
}

func TestResetDefaultsBuildDeployAndReimport(t *testing.T) {
	a, source := fixture(t)
	seedGame(t, a)
	must(t, a.Import(source, 1))
	old := a.State
	_, err := a.Build()
	must(t, err)
	backup, err := a.ResetDefaults()
	must(t, err)
	if len(a.State.Slots) != 0 || !a.State.Defaults || backup == "" {
		t.Fatal("reset state")
	}
	var saved State
	must(t, loadJSON(filepath.Join(backup, "before.json"), &saved))
	if !reflect.DeepEqual(saved, old) {
		t.Fatal("reset backup mismatch")
	}
	if _, err = a.Deploy(true); err == nil {
		t.Fatal("stale pre-reset build deployed")
	}
	folder, err := a.Build()
	must(t, err)
	raw, err := os.ReadFile(filepath.Join(folder, "left4dead2/addons", vpkName))
	must(t, err)
	files, err := readVPK(raw)
	must(t, err)
	base, err := readVPK(embeddedVPK)
	must(t, err)
	if !reflect.DeepEqual(files, base) {
		t.Fatal("reset build not the default resources")
	}
	_, err = a.Deploy(true)
	must(t, err)
	must(t, a.Rollback(true))
	if _, err = os.Stat(filepath.Join(a.Home, filepath.FromSlash(old.Slots[1].Texture))); err != nil {
		t.Fatal("reset removed old material")
	}
	again, err := a.ResetDefaults()
	must(t, err)
	if again != "" {
		t.Fatal("idempotent reset replaced backup")
	}
	must(t, a.Import(source, 4))
	if a.State.Defaults || len(a.State.Slots) != 1 {
		t.Fatal("new import after reset")
	}
	assertNumberedSlots(t, a)
	reopened, err := newApp(a.Home, a.Game)
	must(t, err)
	if !reflect.DeepEqual(reopened.State, a.State) {
		t.Fatal("reopen mismatch")
	}
	// No implicit default build before the user imports or explicitly resets.
	fresh, _ := fixture(t)
	if _, err = fresh.Build(); err == nil {
		t.Fatal("unrequested empty build accepted")
	}
}

func TestResetDefaultsProtectionAndFailures(t *testing.T) {
	for _, scenario := range []string{"external-state", "pending", "write-failure", "deleted-default-state"} {
		a, source := fixture(t)
		must(t, a.Import(source, 1))
		before := a.State
		switch scenario {
		case "external-state":
			must(t, saveJSON(filepath.Join(a.Home, "slots.json"), State{Slots: map[int]Slot{}}))
		case "pending":
			rel := "transactions/pending"
			must(t, saveJSON(filepath.Join(a.Home, "last-deploy.json"), rel))
			must(t, saveJSON(filepath.Join(a.Home, filepath.FromSlash(rel), "transaction.json"), Transaction{Status: "PREPARED"}))
		case "write-failure":
			must(t, atomicWrite(filepath.Join(a.Home, "resets"), []byte("not a directory")))
		case "deleted-default-state":
			_, err := a.ResetDefaults()
			must(t, err)
			before = a.State
			must(t, os.Remove(filepath.Join(a.Home, "slots.json")))
		}
		if _, err := a.ResetDefaults(); err == nil || !reflect.DeepEqual(a.State, before) {
			t.Fatal("failed reset changed memory", scenario, err)
		}
	}
}

func TestSlotRenameCorruptionIsAtomic(t *testing.T) {
	a, source := fixture(t)
	must(t, a.Import(source, 1))
	row := a.State.Slots[1]
	path := filepath.Join(a.Home, filepath.FromSlash(row.Texture))
	must(t, atomicWrite(path, []byte("tampered")))
	before, err := os.ReadFile(filepath.Join(a.Home, "slots.json"))
	must(t, err)
	if err = a.Import(source, 2); err == nil {
		t.Fatal("renumbering accepted a corrupt existing resource")
	}
	after, err := os.ReadFile(filepath.Join(a.Home, "slots.json"))
	must(t, err)
	if !bytes.Equal(before, after) || len(a.State.Slots) != 1 {
		t.Fatal("failed import committed partial naming state")
	}
	if _, err = numberSlots(a.Home, "copy", State{Slots: map[int]Slot{41: row}}); err == nil {
		t.Fatal("invalid slot accepted")
	}
	// Clearing bindings must still work when an old private texture is damaged;
	// the reset preserves it rather than decoding, renaming or deleting it.
	_, err = a.ResetDefaults()
	must(t, err)
	if len(a.State.Slots) != 0 {
		t.Fatal("corrupt binding not cleared")
	}
	must(t, a.Import(source, 1))
	assertNumberedSlots(t, a)
}
