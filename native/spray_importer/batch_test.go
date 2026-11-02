package main

import (
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"testing"
)

func batchFile(t *testing.T, source, folder, name string) string {
	t.Helper()
	data, e := os.ReadFile(source)
	must(t, e)
	path := filepath.Join(folder, filepath.FromSlash(name))
	must(t, atomicWrite(path, data))
	return path
}

func TestNaturalOrder(t *testing.T) {
	values := []string{"图10.png", "图02.png", "图2.png", "图1.png", "图99999999999999999999999999.png"}
	sort.Slice(values, func(i, j int) bool { return naturalLess(values[i], values[j]) })
	if !reflect.DeepEqual(values, []string{"图1.png", "图2.png", "图02.png", "图10.png", "图99999999999999999999999999.png"}) {
		t.Fatal(values)
	}
}

func TestFolderRecursiveSortAndBackups(t *testing.T) {
	a, source := fixture(t)
	folder := filepath.Join(t.TempDir(), "input")
	for _, name := range []string{"图10.png", "child/图2.PNG", "图1.png"} {
		batchFile(t, source, folder, name)
	}
	must(t, atomicWrite(filepath.Join(folder, "notes.txt"), []byte("ignored")))
	result, e := a.ImportFolder(folder)
	must(t, e)
	if result.Imported != 3 || result.Total != 3 || result.Skipped != 1 {
		t.Fatal(result)
	}
	for i, want := range []string{"图1.png", "图2.PNG", "图10.png"} {
		if a.State.Slots[i+1].Title != want {
			t.Fatal(a.State)
		}
	}
	var before, after State
	must(t, loadJSON(filepath.Join(result.Folder, "before.json"), &before))
	must(t, loadJSON(filepath.Join(result.Folder, "after.json"), &after))
	if len(before.Slots) != 0 || !reflect.DeepEqual(after, a.State) {
		t.Fatal("batch backup mismatch")
	}
	for i := 1; i <= 3; i++ {
		_, e = a.Preview(i)
		must(t, e)
	}
	_, e = a.Build()
	must(t, e)
}

func TestFolderMergeResortAndRepeatUpdates(t *testing.T) {
	a, source := fixture(t)
	manual := batchFile(t, source, t.TempDir(), "20.png")
	must(t, a.Import(manual, 17))
	folder := t.TempDir()
	batchFile(t, source, folder, "10.png")
	batchFile(t, source, folder, "2.png")
	result, e := a.ImportFolder(folder)
	must(t, e)
	if result.Total != 3 || a.State.Slots[1].Title != "2.png" || a.State.Slots[3].Title != "20.png" {
		t.Fatal(result, a.State)
	}
	result, e = a.ImportFolder(folder)
	must(t, e)
	if result.Imported != 0 || result.Updated != 2 || result.Total != 3 {
		t.Fatal(result)
	}
}

func TestFolderOverCapacityDoesNotCommit(t *testing.T) {
	a, source := fixture(t)
	must(t, a.Import(source, 1))
	before, e := fileHash(filepath.Join(a.Home, "slots.json"))
	must(t, e)
	folder := t.TempDir()
	for i := 0; i < 41; i++ {
		batchFile(t, source, folder, fmt.Sprintf("%02d.png", i))
	}
	if _, e = a.ImportFolder(folder); e == nil {
		t.Fatal("41 images accepted")
	}
	after, e := fileHash(filepath.Join(a.Home, "slots.json"))
	must(t, e)
	if before != after || len(a.State.Slots) != 1 {
		t.Fatal("capacity failure changed state")
	}
}

func TestFolderMergedCapacityDoesNotCommit(t *testing.T) {
	a, source := fixture(t)
	must(t, a.Import(source, 1))
	// Legacy duplicated slots are intentional and must not be discarded.
	for i := 2; i <= 40; i++ {
		a.State.Slots[i] = a.State.Slots[1]
	}
	must(t, saveJSON(filepath.Join(a.Home, "slots.json"), a.State))
	folder := t.TempDir()
	batchFile(t, source, folder, "new.png")
	if _, e := a.ImportFolder(folder); e == nil {
		t.Fatal("merged overflow accepted")
	}
	if len(a.State.Slots) != 40 {
		t.Fatal("manual duplicates discarded")
	}
}

func TestFolderBadImageDoesNotCommit(t *testing.T) {
	a, source := fixture(t)
	folder := t.TempDir()
	batchFile(t, source, folder, "1.png")
	must(t, atomicWrite(filepath.Join(folder, "2.png"), []byte("broken")))
	if _, e := a.ImportFolder(folder); e == nil {
		t.Fatal("broken image accepted")
	}
	if len(a.State.Slots) != 0 {
		t.Fatal("partial in-memory commit")
	}
	if _, e := os.Stat(filepath.Join(a.Home, "slots.json")); !os.IsNotExist(e) {
		t.Fatal("partial disk commit")
	}
}

func TestFolderSameNameTieAndToolDataRejection(t *testing.T) {
	a, source := fixture(t)
	folder := t.TempDir()
	batchFile(t, source, folder, "b/1.png")
	batchFile(t, source, folder, "a/1.png")
	_, e := a.ImportFolder(folder)
	must(t, e)
	if a.State.Slots[1].SortKey != "a/1.png" || a.State.Slots[2].SortKey != "b/1.png" {
		t.Fatal(a.State)
	}
	if _, e = a.ImportFolder(a.Home); e == nil {
		t.Fatal("tool output recursively imported")
	}
}

func TestEmptyFolderDoesNotCommit(t *testing.T) {
	a, _ := fixture(t)
	if _, e := a.ImportFolder(t.TempDir()); e == nil {
		t.Fatal("empty folder accepted")
	}
	if len(a.State.Slots) != 0 {
		t.Fatal("empty folder changed state")
	}
}

func TestRepeatedSourceUsesLowestOriginalSlot(t *testing.T) {
	a, source := fixture(t)
	folder := t.TempDir()
	path := batchFile(t, source, folder, "new.png")
	must(t, a.Import(path, 1))
	row := a.State.Slots[1]
	for attempt := 0; attempt < 16; attempt++ {
		first, second := row, row
		first.Title = "first.png"
		second.Title = "second.png"
		a.State.Slots = map[int]Slot{1: first, 2: second}
		must(t, saveJSON(filepath.Join(a.Home, "slots.json"), a.State))
		_, e := a.ImportFolder(folder)
		must(t, e)
		if a.State.Slots[1].Title != "new.png" || a.State.Slots[2].Title != "second.png" {
			t.Fatal("updated a random duplicate", a.State)
		}
	}
}
