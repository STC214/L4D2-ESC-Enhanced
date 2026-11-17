package main

import (
	"bytes"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

func portablePayload(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	packed, err := readVPK(embeddedVPK)
	must(t, err)
	for _, p := range expectedPaths() {
		data := embeddedVPK
		if strings.HasPrefix(p, "update/") {
			data = packed[strings.TrimPrefix(p, "update/")]
		}
		must(t, atomicWrite(filepath.Join(root, filepath.FromSlash(p)), data))
	}
	must(t, atomicWrite(filepath.Join(root, filepath.FromSlash(selectorDLLPath)), embeddedSelectorDLL))
	for p, source := range map[string]string{
		"left4dead2/addons/" + cProjectVPK:      "../../dist/" + cProjectVPK,
		"bin/neko/plugins/CSessionDefaults.dll": "../../dist/c_session_helper/CSessionDefaults.dll",
	} {
		data, err := os.ReadFile(source)
		must(t, err)
		must(t, atomicWrite(filepath.Join(root, filepath.FromSlash(p)), data))
	}
	return root
}

func TestPortableInstallAndExactRollback(t *testing.T) {
	a := actionFixture(t)
	_, err := a.ResetDefaults()
	must(t, err)
	slots, err := os.ReadFile(filepath.Join(a.Home, "slots.json"))
	must(t, err)
	// Existing custom game VPK is a backup target, never the payload source.
	must(t, atomicWrite(filepath.Join(a.Game, "left4dead2/addons", vpkName), []byte("custom game spray")))
	must(t, atomicWrite(filepath.Join(a.Game, "left4dead2/addons", cProjectVPK), []byte("old C")))
	before := actionTree(t, a.Game)
	payload := portablePayload(t)
	plan, err := a.PlanPortableInstall(payload, true)
	must(t, err)
	if plan.Kind != "install-bundle" || len(plan.After) != 85 {
		t.Fatal("incomplete portable payload", len(plan.After))
	}
	_, err = a.ApplyGamePlan(plan, true)
	must(t, err)
	for p, expected := range plan.After {
		actual, err := readGameFile(a.Game, p)
		must(t, err)
		if actual.gameFileState != expected.gameFileState {
			t.Fatal("installed bytes differ", p)
		}
	}
	again, err := a.PlanPortableInstall(payload, true)
	must(t, err)
	if len(again.After) != 0 {
		t.Fatal("portable install not idempotent")
	}
	must(t, a.RollbackGameAction(true))
	if !reflect.DeepEqual(actionTree(t, a.Game), before) {
		t.Fatal("portable rollback differs")
	}
	current, err := os.ReadFile(filepath.Join(a.Home, "slots.json"))
	must(t, err)
	if !bytes.Equal(slots, current) {
		t.Fatal("portable install changed user's catalog")
	}
}

func TestPortableRejectsCorruptAndChangedPayload(t *testing.T) {
	a := actionFixture(t)
	before := actionTree(t, a.Game)
	payload := portablePayload(t)
	for _, p := range []string{"left4dead2/addons/" + vpkName, expectedPaths()[1], selectorDLLPath, "left4dead2/addons/" + cProjectVPK, "bin/neko/plugins/CSessionDefaults.dll"} {
		path := filepath.Join(payload, filepath.FromSlash(p))
		original, err := os.ReadFile(path)
		must(t, err)
		must(t, atomicWrite(path, []byte("not original published bytes")))
		if _, err := a.PlanPortableInstall(payload, true); err == nil {
			t.Fatal("corrupt payload accepted", p)
		}
		must(t, atomicWrite(path, original))
	}
	plan, err := a.PlanPortableInstall(payload, true)
	must(t, err)
	path := "left4dead2/addons/" + cProjectVPK
	must(t, atomicWrite(filepath.Join(a.Game, filepath.FromSlash(path)), []byte("external edit after confirmation")))
	if _, err = a.ApplyGamePlan(plan, true); err == nil {
		t.Fatal("confirmation race accepted")
	}
	before[path] = digest([]byte("external edit after confirmation"))
	if !reflect.DeepEqual(actionTree(t, a.Game), before) {
		t.Fatal("failed portable preflight changed game")
	}
}

func TestPortableAddonEnableCPreservation(t *testing.T) {
	for _, legacy := range []bool{false, true} {
		name := cProjectVPK
		if legacy {
			var err error
			name, err = legacyAddonName(name)
			must(t, err)
		}
		for _, present := range []bool{false, true} {
			raw := []byte("AddonList {\r\n\"other.vpk\" \"1\" // keep\r\n")
			if legacy {
				raw = append(raw, []byte("// "+name+"\r\n")...)
			}
			if present {
				raw = append(raw, []byte("\""+name+"\" \"0\"\r\n")...)
			}
			raw = append(raw, '}')
			after, err := patchProjectAddons(raw, false, true)
			must(t, err)
			if !bytes.Contains(after, []byte("\""+name+"\"")) || !bytes.Contains(after, []byte("\"other.vpk\" \"1\" // keep\r\n")) {
				t.Fatal("C encoding/foreign bytes changed")
			}
			again, err := patchProjectAddons(after, false, true)
			must(t, err)
			if !bytes.Equal(after, again) {
				t.Fatal("C enable not idempotent")
			}
		}
	}
}
