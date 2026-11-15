package main

import (
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
)

// Executable-local user preferences are separate from conversion/retention.
type importSettings struct {
	MinimumAnimationFrames int
	GameDirectory          string `json:",omitempty"`
}

func (a *App) saveSettings(next importSettings) error {
	path, err := safePath(a.Home, "settings.json")
	if err != nil {
		return err
	}
	disk := importSettings{MinimumAnimationFrames: 30}
	err = loadJSON(path, &disk)
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	if err == nil {
		if !reflect.DeepEqual(disk, a.Settings) {
			return errors.New("配置已被外部修改，请重新打开工具后再操作；现有配置已保留")
		}
		if reflect.DeepEqual(disk, next) {
			return nil
		}
	}
	if err = saveJSON(path, next); err != nil {
		return err
	}
	a.Settings = next
	return nil
}

func (a *App) SetMinimumFrames(n int) error {
	if err := validMinimum(n); err != nil {
		return err
	}
	settings := a.Settings
	settings.MinimumAnimationFrames = n
	return a.saveSettings(settings)
}

func normalizedGameDirectory(value string) string {
	return strings.Trim(strings.TrimSpace(value), "\"")
}

// Only an unchanged, already remembered game root may bypass filesystem
// validation (e.g. an offline drive). A deleted settings file is recreated;
// external edits or write errors must not be hidden by a cached-value shortcut.
func (a *App) RememberGameDirectory(value string) error {
	game := normalizedGameDirectory(value)
	if a.Settings.GameDirectory != "" && filepath.IsAbs(game) && filepath.Clean(game) == a.Settings.GameDirectory && a.Game == a.Settings.GameDirectory {
		return a.saveSettings(a.Settings)
	}
	return a.SetGameDirectory(game)
}

// Inspect file metadata only; never execute game files or open spray imagery.
func (a *App) SetGameDirectory(value string) error {
	game := normalizedGameDirectory(value)
	if !filepath.IsAbs(game) {
		return errors.New("请输入包含 left4dead2.exe 的游戏根目录绝对路径")
	}
	game = filepath.Clean(game)
	for _, relative := range []string{"left4dead2.exe", "left4dead2/gameinfo.txt"} {
		info, err := os.Stat(filepath.Join(game, filepath.FromSlash(relative)))
		if err != nil || !info.Mode().IsRegular() {
			return errors.New("游戏目录未找到 left4dead2.exe 或 left4dead2/gameinfo.txt；保留上次保存的目录")
		}
	}
	settings := a.Settings
	settings.GameDirectory = game
	if err := a.saveSettings(settings); err != nil {
		return err
	}
	a.Game = game
	return nil
}
