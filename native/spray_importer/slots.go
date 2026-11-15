package main

import (
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

func slotTitle(n int) string { return fmt.Sprintf("喷漆 %02d", n) }

func originalTitle(row Slot) string {
	if row.OriginalTitle != "" {
		return row.OriginalTitle
	}
	return row.Title
}

// Renumber copies, never source files or immutable earlier generations.
// Reuse an already canonical copy when its slot number has not changed.
func numberSlots(home, rel string, state State) (State, error) {
	next := State{Slots: map[int]Slot{}, Defaults: state.Defaults}
	for n, row := range state.Slots {
		if err := validSlot(n); err != nil {
			return State{}, err
		}
		if len(row.SHA256) != 64 {
			return State{}, fmt.Errorf("槽位 %02d 缺少有效素材哈希", n)
		}
		copied := map[string]string{}
		copyFile := func(source, name, hash string, limit int64) (string, error) {
			key := strings.ToLower(filepath.FromSlash(source))
			if result, ok := copied[key]; ok {
				return result, nil
			}
			path, err := safePath(home, source)
			if err != nil {
				return "", err
			}
			f, err := os.Open(path)
			if err != nil {
				return "", err
			}
			stat, err := f.Stat()
			if err != nil {
				f.Close()
				return "", err
			}
			if !stat.Mode().IsRegular() || stat.Size() > limit {
				f.Close()
				return "", errors.New("槽位素材不是普通文件或超过复制预算")
			}
			data, err := io.ReadAll(io.LimitReader(f, limit+1))
			f.Close()
			if err != nil {
				return "", err
			}
			if int64(len(data)) > limit {
				return "", errors.New("槽位素材超过复制预算")
			}
			if hash != "" && digest(data) != hash {
				return "", fmt.Errorf("槽位 %02d 素材哈希不符", n)
			}
			result := source
			if filepath.Base(path) != name {
				result = rel + "/" + name
				target, err := safePath(home, result)
				if err != nil {
					return "", err
				}
				if err = atomicWrite(target, data); err != nil {
					return "", err
				}
			}
			copied[key] = result
			return result, nil
		}
		var err error
		row.OriginalTitle = originalTitle(row)
		row.Title = slotTitle(n)
		row.Texture, err = copyFile(row.Texture, fmt.Sprintf("test_%03d.vtf", n), row.SHA256, 512<<10)
		if err != nil {
			return State{}, err
		}
		if row.Preview != "" {
			row.Preview, err = copyFile(row.Preview, fmt.Sprintf("test_%03d_preview.png", n), "", 16<<20)
			if err != nil {
				return State{}, err
			}
		}
		if len(row.Masters) > 0 {
			masters := make([]string, len(row.Masters))
			for i, path := range row.Masters {
				masters[i], err = copyFile(path, fmt.Sprintf("test_%03d_master_%03d.png", n, i+1), "", 16<<20)
				if err != nil {
					return State{}, err
				}
			}
			row.Masters = masters
		}
		next.Slots[n] = row
	}
	return next, nil
}

// Reset only catalog bindings. Preserve all source/history bytes and the game
// rollback journal. An explicit marker permits building the untouched baseline.
func (a *App) ResetDefaults() (string, error) {
	if err := a.checkState(); err != nil {
		return "", err
	}
	if err := a.checkPending(); err != nil {
		return "", err
	}
	if len(a.State.Slots) == 0 && a.State.Defaults {
		return "", nil
	}
	rel := "resets/" + identifier()
	folder, err := safePath(a.Home, rel)
	if err != nil {
		return "", err
	}
	next := State{Slots: map[int]Slot{}, Defaults: true}
	if err = saveJSON(filepath.Join(folder, "before.json"), a.State); err != nil {
		return "", err
	}
	if err = saveJSON(filepath.Join(folder, "after.json"), next); err != nil {
		return "", err
	}
	if err = a.checkState(); err != nil {
		return "", err
	}
	if err = saveJSON(filepath.Join(a.Home, "slots.json"), next); err != nil {
		return "", err
	}
	a.State = next
	a.finishCatalog(rel)
	return folder, nil
}
