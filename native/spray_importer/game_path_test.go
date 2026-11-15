package main

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"
)

func ownGameDirectory(t *testing.T) string {
	t.Helper()
	game := filepath.Join(t.TempDir(), "游戏目录 with spaces")
	must(t, atomicWrite(filepath.Join(game, "left4dead2.exe"), []byte("fixture only, never executed")))
	must(t, atomicWrite(filepath.Join(game, "left4dead2/gameinfo.txt"), []byte("fixture metadata")))
	return game
}

func TestGameDirectoryPersistenceAndSettingsMerge(t *testing.T) {
	a, _ := fixture(t)
	game := ownGameDirectory(t)
	must(t, a.SetMinimumFrames(3))
	must(t, a.SetGameDirectory("  \""+game+string(os.PathSeparator)+"\"  "))
	if a.Game != game || a.Settings.GameDirectory != game || a.Settings.MinimumAnimationFrames != 3 {
		t.Fatal("path normalization/settings merge", a.Settings)
	}
	must(t, a.SetMinimumFrames(30))
	reopened, err := newApp(a.Home, defaultGame)
	must(t, err)
	if reopened.Game != game || reopened.Settings.MinimumAnimationFrames != 30 {
		t.Fatal("restart forgot game path or animation setting")
	}
	other := ownGameDirectory(t)
	must(t, reopened.SetGameDirectory(other))
	reopened, err = newApp(a.Home, defaultGame)
	must(t, err)
	if reopened.Game != other {
		t.Fatal("changed path not saved")
	}
}

func TestGameDirectoryInvalidEditAndWriteFailurePreserveConfig(t *testing.T) {
	a, _ := fixture(t)
	game := ownGameDirectory(t)
	must(t, a.SetGameDirectory(game))
	path := filepath.Join(a.Home, "settings.json")
	before, err := os.ReadFile(path)
	must(t, err)
	for _, invalid := range []string{"", "relative/path", "C:partial", filepath.Join(game, "left4dead2"), t.TempDir(), filepath.Join(game, "missing")} {
		if a.SetGameDirectory(invalid) == nil || a.Game != game || a.Settings.GameDirectory != game {
			t.Fatal("invalid edit overwrote last valid path", invalid)
		}
		after, err := os.ReadFile(path)
		must(t, err)
		if !bytes.Equal(before, after) {
			t.Fatal("invalid edit wrote config")
		}
	}
	must(t, os.Remove(path))
	must(t, os.Mkdir(path, 0755))
	if a.SetGameDirectory(ownGameDirectory(t)) == nil || a.Game != game || a.Settings.GameDirectory != game {
		t.Fatal("failed write changed runtime path")
	}
}

func TestGameDirectoryMigrationAndUnavailableDisk(t *testing.T) {
	a, _ := fixture(t)
	must(t, atomicWrite(filepath.Join(a.Home, "settings.json"), []byte("{\"MinimumAnimationFrames\":2}")))
	reopened, err := newApp(a.Home, a.Game)
	must(t, err)
	if reopened.Game != a.Game || reopened.Settings.MinimumAnimationFrames != 2 {
		t.Fatal("legacy settings changed")
	}
	game := ownGameDirectory(t)
	must(t, reopened.SetGameDirectory(game))
	must(t, os.Remove(filepath.Join(game, "left4dead2.exe")))
	reopened, err = newApp(a.Home, defaultGame)
	must(t, err)
	if reopened.Game != game {
		t.Fatal("temporarily missing disk/game erased saved path")
	}
	if reopened.SetGameDirectory(game) == nil {
		t.Fatal("missing executable accepted on new save")
	}
}

func TestGameDirectoryPortableAndFreshConfig(t *testing.T) {
	a, _ := fixture(t)
	game := ownGameDirectory(t)
	must(t, a.SetGameDirectory(game))
	raw, err := os.ReadFile(filepath.Join(a.Home, "settings.json"))
	must(t, err)
	portable := filepath.Join(t.TempDir(), "moved-program", "CSP_Spray_Data")
	must(t, atomicWrite(filepath.Join(portable, "settings.json"), raw))
	reopened, err := newApp(portable, defaultGame)
	must(t, err)
	if reopened.Game != game {
		t.Fatal("moving program and data lost config")
	}
	fresh, err := newApp(filepath.Join(t.TempDir(), "fresh-program", "CSP_Spray_Data"), defaultGame)
	must(t, err)
	if fresh.Game != defaultGame || fresh.Settings.GameDirectory != "" {
		t.Fatal("fresh installation inherited another program's config")
	}
}

func TestGameDirectoryCachedConfigRecoveryAndExternalChange(t *testing.T) {
	a, _ := fixture(t)
	game := ownGameDirectory(t)
	must(t, a.SetGameDirectory(game))
	path := filepath.Join(a.Home, "settings.json")
	must(t, os.Remove(path))
	// Even with the game disk offline, restore the already verified remembered
	// value rather than silently pretending a missing config is still saved.
	must(t, os.Remove(filepath.Join(game, "left4dead2.exe")))
	must(t, a.RememberGameDirectory(game))
	reopened, err := newApp(a.Home, defaultGame)
	must(t, err)
	if reopened.Game != game {
		t.Fatal("deleted configuration not recreated")
	}
	// Do not clobber an external settings edit when either preference changes.
	external := a.Settings
	external.MinimumAnimationFrames = 3
	must(t, saveJSON(path, external))
	before, err := os.ReadFile(path)
	must(t, err)
	if a.RememberGameDirectory(game) == nil || a.SetMinimumFrames(30) == nil {
		t.Fatal("external config edit ignored")
	}
	after, err := os.ReadFile(path)
	must(t, err)
	if !bytes.Equal(before, after) || a.Settings.MinimumAnimationFrames != 2 {
		t.Fatal("external edit overwritten")
	}
	// A cached match must also surface replacement/write failures.
	must(t, os.Remove(path))
	must(t, os.Mkdir(path, 0755))
	if a.RememberGameDirectory(game) == nil {
		t.Fatal("cached path concealed config I/O error")
	}
}
