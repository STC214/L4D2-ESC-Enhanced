package main

import (
	"bytes"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

func actionFixture(t *testing.T) *App {
	t.Helper()
	a, _ := fixture(t)
	a.Game = ownGameDirectory(t)
	must(t, atomicWrite(filepath.Join(a.Game, "left4dead2/gameinfo.txt"), []byte(`"GameInfo" { "FileSystem" { "SearchPaths" { Game update } } }`)))
	for p, data := range map[string]string{"bin/neko/source_nekomimi.exe": "fixture loader never run", "bin/engine.dll": "fixture engine", "bin/gameui.dll": "fixture UI", "left4dead2/cfg/config.cfg": "keep user settings", "left4dead2/addons/other.vpk": "keep foreign MOD", "left4dead2/addonlist.txt": "\"AddonList\"\r\n{\r\n\t\"other.vpk\" \"1\" // keep me\r\n}\r\n"} {
		must(t, atomicWrite(filepath.Join(a.Game, filepath.FromSlash(p)), []byte(data)))
	}
	return a
}
func actionTree(t *testing.T, root string) map[string]string {
	t.Helper()
	out := map[string]string{}
	must(t, filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.Mode().IsRegular() {
			rel, err := filepath.Rel(root, path)
			if err != nil {
				return err
			}
			h, err := fileHash(path)
			if err != nil {
				return err
			}
			out[filepath.ToSlash(rel)] = h
		}
		return nil
	}))
	return out
}

func TestProjectAddonBytePreservation(t *testing.T) {
	for _, legacy := range []bool{false, true} {
		name := cProjectVPK
		if legacy {
			var err error
			name, err = legacyAddonName(name)
			must(t, err)
		}
		raw := []byte("\xef\xbb\xbf\"AddonList\"\r\n{\r\n// keep original comment\r\n\"other.vpk\" \"1\"\r\n\"" + vpkName + "\" \"0\"\r\n\"" + name + "\" \"1\"\r\n\"" + diagnosticVPK + "\" \"1\"\r\n}\r\n")
		installed, err := patchProjectAddons(raw, false)
		must(t, err)
		if !bytes.Contains(installed, []byte("\""+vpkName+"\" \"1\"")) || !bytes.Contains(installed, []byte("\""+name+"\" \"1\"")) || !bytes.Contains(installed, []byte("\""+diagnosticVPK+"\" \"0\"")) {
			t.Fatal("install changed wrong addon state")
		}
		clean, err := patchProjectAddons(installed, true)
		must(t, err)
		if bytes.Contains(clean, []byte(vpkName)) || bytes.Contains(clean, []byte(name)) || bytes.Contains(clean, []byte(diagnosticVPK)) || !bytes.Contains(clean, []byte("\"other.vpk\" \"1\"")) || !bytes.HasPrefix(clean, []byte{239, 187, 191}) || !bytes.Contains(clean, []byte("// keep original comment\r\n")) {
			t.Fatal("foreign addon bytes damaged")
		}
		again, err := patchProjectAddons(clean, true)
		must(t, err)
		if !bytes.Equal(again, clean) {
			t.Fatal("cleanup not idempotent")
		}
	}
	raw := append([]byte("AddonList { \""), 0x81, 0x5c)
	raw = append(raw, []byte("\" \"1\" }")...)
	patched, err := patchProjectAddons(raw, false)
	must(t, err)
	if !bytes.Contains(patched, raw[12:19]) || !bytes.Contains(patched, []byte("\""+diagnosticVPK+"\"\t\"0\"")) {
		t.Fatal("DBCS backslash or diagnostic exclusion lost")
	}
}

func TestProjectAddonMalformedRejected(t *testing.T) {
	for _, s := range []string{"", `"AddonList" "{" "x" "1" "}"`, `"AddonList" { "x" { "y" "1" } }`, `"AddonList" { "x" "1" "X" "0" }`, `"AddonList" { "unterminated`, `"wrong" { }`, `"AddonList" { } extra`, "AddonList { /* unterminated"} {
		if _, err := patchProjectAddons([]byte(s), true); err == nil {
			t.Fatal("malformed addonlist accepted", s)
		}
	}
	legacy, err := legacyAddonName(cProjectVPK)
	must(t, err)
	if _, err = patchProjectAddons([]byte(`"AddonList" { "`+cProjectVPK+`" "1" "`+legacy+`" "1" }`), true); err == nil {
		t.Fatal("mixed encoding duplicate accepted")
	}
}

func TestOneClickFirstInstallAndExactRollback(t *testing.T) {
	a := actionFixture(t)
	before := actionTree(t, a.Game)
	last := -1
	a.Progress = func(percent int, stage string) {
		if percent < last {
			t.Fatal("one-click progress reversed", last, percent)
		}
		last = percent
	}
	tx, err := a.OneClickDeploy(true)
	must(t, err)
	if last != 100 {
		t.Fatal("one-click progress did not finish")
	}
	a.Progress = nil // Undo is a separate UI operation with a new progress range.
	if tx == "" {
		t.Fatal("no first-install transaction")
	}
	for _, p := range expectedPaths() {
		if _, err = os.Stat(filepath.Join(a.Game, filepath.FromSlash(p))); err != nil {
			t.Fatal("first install missing resource", p, err)
		}
	}
	dll, err := os.ReadFile(filepath.Join(a.Game, selectorDLLPath))
	must(t, err)
	if digest(dll) != selectorDLLHash {
		t.Fatal("DLL differs from embedded bridge")
	}
	addon, err := os.ReadFile(filepath.Join(a.Game, addonListPath))
	must(t, err)
	if !bytes.Contains(addon, []byte(vpkName)) {
		t.Fatal("selector addon not enabled")
	}
	if !a.State.Defaults || len(a.State.Slots) != 0 {
		t.Fatal("fresh install not default selector")
	}
	must(t, a.Rollback(true))
	if !reflect.DeepEqual(before, actionTree(t, a.Game)) {
		t.Fatal("first install rollback not byte-exact")
	}
	must(t, atomicWrite(filepath.Join(a.Game, selectorDLLPath), embeddedSelectorDLL))
	if err = a.Rollback(true); err == nil {
		t.Fatal("rolled-back transaction falsely claimed later reinstalled files were restored")
	}
}

func TestProjectCleanupAllComponentsAndRollback(t *testing.T) {
	a := actionFixture(t)
	for p, data := range map[string]string{"left4dead2/addons/" + cProjectVPK: "C fixture", "bin/neko/plugins/CSessionDefaults.dll": "C helper fixture", "left4dead2/addons/" + diagnosticVPK: "diagnostic fixture"} {
		must(t, atomicWrite(filepath.Join(a.Game, filepath.FromSlash(p)), []byte(data)))
	}
	_, err := a.OneClickDeploy(true)
	must(t, err)
	before := actionTree(t, a.Game)
	catalog := a.State
	plan, err := a.PlanProjectCleanup(true)
	must(t, err)
	if !reflect.DeepEqual(before, actionTree(t, a.Game)) {
		t.Fatal("dry run changed game")
	}
	view, err := a.SaveCleanupPreview(plan)
	must(t, err)
	if _, err = os.Stat(view); err != nil {
		t.Fatal("no absolute target list")
	}
	tx, err := a.ApplyGamePlan(plan, true)
	must(t, err)
	if tx == "" {
		t.Fatal("cleanup no-op")
	}
	for _, p := range projectGamePaths() {
		if p == addonListPath {
			continue
		}
		if _, err = os.Stat(filepath.Join(a.Game, filepath.FromSlash(p))); !os.IsNotExist(err) {
			t.Fatal("project component retained", p, err)
		}
	}
	if !reflect.DeepEqual(a.State, catalog) {
		t.Fatal("cleanup changed local imports")
	}
	for p, h := range before {
		if !allowedGameActionPath(p, "cleanup-all") {
			now, err := fileHash(filepath.Join(a.Game, filepath.FromSlash(p)))
			must(t, err)
			if now != h {
				t.Fatal("foreign/native file changed", p)
			}
		}
	}
	plan, err = a.PlanProjectCleanup(true)
	must(t, err)
	if len(plan.After) != 0 {
		t.Fatal("second cleanup not no-op")
	}
	must(t, a.Rollback(true))
	if !reflect.DeepEqual(before, actionTree(t, a.Game)) {
		t.Fatal("cleanup rollback not exact")
	}
}

func TestProjectCleanupConfirmationRaceAndUnknownPath(t *testing.T) {
	a := actionFixture(t)
	_, err := a.OneClickDeploy(true)
	must(t, err)
	plan, err := a.PlanProjectCleanup(true)
	must(t, err)
	must(t, atomicWrite(filepath.Join(a.Game, selectorDLLPath), []byte("external edit")))
	before := actionTree(t, a.Game)
	if _, err = a.ApplyGamePlan(plan, true); err == nil {
		t.Fatal("confirmation race ignored")
	}
	if !reflect.DeepEqual(before, actionTree(t, a.Game)) {
		t.Fatal("race rejection made partial changes")
	}
	plan, err = a.PlanProjectCleanup(true)
	must(t, err)
	plan.After["../foreign.txt"] = gameFile{}
	plan.Before["../foreign.txt"] = gameFile{}
	if _, err = a.ApplyGamePlan(plan, true); err == nil {
		t.Fatal("non-project cleanup path accepted")
	}
}

func TestGameActionPendingAndDamagedBackupProtection(t *testing.T) {
	a := actionFixture(t)
	tx, err := a.OneClickDeploy(true)
	must(t, err)
	var journal gameJournal
	must(t, loadJSON(filepath.Join(tx, "transaction.json"), &journal))
	journal.Status = "PREPARED"
	must(t, saveJSON(filepath.Join(tx, "transaction.json"), journal))
	if _, err = a.OneClickDeploy(true); err == nil {
		t.Fatal("pending install overwritten")
	}
	if _, err = a.PlanProjectCleanup(true); err == nil {
		t.Fatal("pending cleanup permitted")
	}
	must(t, a.Rollback(true))
	_, err = a.OneClickDeploy(true)
	must(t, err)
	plan, err := a.PlanProjectCleanup(true)
	must(t, err)
	tx, err = a.ApplyGamePlan(plan, true)
	must(t, err)
	must(t, atomicWrite(filepath.Join(tx, "before", selectorDLLPath), []byte("damaged backup")))
	before := actionTree(t, a.Game)
	if err = a.Rollback(true); err == nil {
		t.Fatal("damaged backup accepted")
	}
	if !reflect.DeepEqual(before, actionTree(t, a.Game)) {
		t.Fatal("rollback backup rejection modified game")
	}
}

func TestOneClickPrerequisitesAndForeignFilesPreserved(t *testing.T) {
	a := actionFixture(t)
	must(t, os.Remove(filepath.Join(a.Game, "bin/neko/source_nekomimi.exe")))
	before := actionTree(t, a.Game)
	if _, err := a.OneClickDeploy(true); err == nil {
		t.Fatal("missing L4N accepted")
	}
	if !reflect.DeepEqual(before, actionTree(t, a.Game)) {
		t.Fatal("prerequisite failure changed game")
	}
	// Cleanup itself must remain available after the user removed L4N.
	plan, err := a.PlanProjectCleanup(true)
	must(t, err)
	if len(plan.After) != 0 {
		t.Fatal("foreign-only game scheduled for deletion")
	}
	if _, err = a.ApplyGamePlan(plan, true); err != nil {
		t.Fatal(err)
	}
}

func TestManagedAndLegacyRollbackOrdering(t *testing.T) {
	a, source := fixture(t)
	seedGame(t, a)
	must(t, atomicWrite(filepath.Join(a.Game, "left4dead2.exe"), []byte("fixture")))
	must(t, atomicWrite(filepath.Join(a.Game, "bin/neko/source_nekomimi.exe"), []byte("fixture")))
	_, err := a.OneClickDeploy(true)
	must(t, err)
	before := actionTree(t, a.Game)
	must(t, a.Import(source, 7))
	_, err = a.Build()
	must(t, err)
	_, err = a.Deploy(true)
	must(t, err)
	must(t, a.Rollback(true))
	if !reflect.DeepEqual(before, actionTree(t, a.Game)) {
		t.Fatal("latest legacy rollback not selected")
	}
	plan, err := a.PlanProjectCleanup(true)
	must(t, err)
	_, err = a.ApplyGamePlan(plan, true)
	must(t, err)
	must(t, a.Rollback(true))
	if !reflect.DeepEqual(before, actionTree(t, a.Game)) {
		t.Fatal("latest managed cleanup rollback not selected")
	}
	if !strings.Contains(a.State.Slots[7].Title, "07") {
		t.Fatal("cleanup lost imported slot")
	}
}

func TestLegacyActionReferenceSurvivesCompatibilityPointerFailure(t *testing.T) {
	a, source := fixture(t)
	seedGame(t, a)
	must(t, a.Import(source, 1))
	_, err := a.Build()
	must(t, err)
	before := actionTree(t, a.Game)
	_, err = a.Deploy(true)
	must(t, err)
	var ref gameActionRef
	must(t, loadJSON(filepath.Join(a.Home, "last-action.json"), &ref))
	if ref.Kind != "legacy" {
		t.Fatal("unified legacy action reference missing")
	}
	// Simulate a failed/stale compatibility-pointer update after the durable
	// unified reference was committed, before any game mutation could proceed.
	must(t, saveJSON(filepath.Join(a.Home, "last-deploy.json"), "transactions/missing-old-pointer"))
	path := filepath.Join(a.Home, ref.Reference, "transaction.json")
	var journal Transaction
	must(t, loadJSON(path, &journal))
	journal.Status = "PREPARED"
	must(t, saveJSON(path, journal))
	if a.checkPending() == nil {
		t.Fatal("unified reference did not protect pending legacy operation")
	}
	must(t, a.Rollback(true))
	must(t, a.checkPending())
	if !reflect.DeepEqual(before, actionTree(t, a.Game)) {
		t.Fatal("recovery used stale compatibility pointer")
	}
}

func TestGameActionRollbackConcurrentEditPreserved(t *testing.T) {
	a := actionFixture(t)
	before := actionTree(t, a.Game)
	tx, err := a.OneClickDeploy(true)
	must(t, err)
	// The game uses the loose update/ copy, not the VPK member path.
	target := filepath.Join(a.Game, "update", filepath.FromSlash(slotPath(40, "vtf")))
	original, err := os.ReadFile(target)
	must(t, err)
	injected := false
	a.Progress = func(percent int, stage string) {
		if !injected {
			injected = true
			must(t, atomicWrite(target, []byte("external edit during rollback")))
		}
	}
	if err = a.Rollback(true); err == nil {
		t.Fatal("concurrent edit overwritten")
	}
	if !injected {
		t.Fatal("rollback progress not exercised")
	}
	raw, err := os.ReadFile(target)
	must(t, err)
	if string(raw) != "external edit during rollback" {
		t.Fatal("external bytes lost")
	}
	var journal gameJournal
	must(t, loadJSON(filepath.Join(tx, "transaction.json"), &journal))
	if journal.Status != "ROLLBACK_PREPARED" {
		t.Fatal("recovery checkpoint lost")
	}
	a.Progress = nil
	must(t, atomicWrite(target, original))
	must(t, a.Rollback(true))
	if !reflect.DeepEqual(before, actionTree(t, a.Game)) {
		t.Fatal("retry did not complete exact rollback")
	}
}
