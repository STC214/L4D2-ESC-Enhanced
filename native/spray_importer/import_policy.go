package main

import (
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"strings"
)

type importSettings struct {
	MinimumAnimationFrames int
}

func (a *App) SetMinimumFrames(n int) error {
	if err := validMinimum(n); err != nil {
		return err
	}
	settings := importSettings{MinimumAnimationFrames: n}
	path, err := safePath(a.Home, "settings.json")
	if err != nil {
		return err
	}
	if err = saveJSON(path, settings); err != nil {
		return err
	}
	a.Settings = settings
	return nil
}

func (a *App) finishCatalog(rel string) {
	a.MaintenanceWarning = ""
	// Commit a pointer first. Interrupted cleanup may leave extra old copies,
	// but it never discards the new backup before its catalog is durable.
	path, err := safePath(a.Home, "latest-catalog-backup.json")
	if err == nil {
		err = saveJSON(path, filepath.ToSlash(rel))
	}
	if err == nil {
		err = a.checkPending()
	}
	if err == nil {
		err = pruneCatalogBackups(a.Home, rel)
	}
	if err != nil {
		a.MaintenanceWarning = "清单已保存；旧备份清理待重试：" + err.Error()
	}
	if a.Progress != nil {
		a.Progress(100, "导入与清单提交完成")
	}
}

// Metadata-only maintenance for existing installations. Only a backup whose
// after-snapshot matches the current durable catalog is eligible as the keeper.
func (a *App) PruneBackups() error {
	if err := a.checkState(); err != nil {
		return err
	}
	if err := a.checkPending(); err != nil {
		return err
	}
	keep, newest := "", ""
	for _, category := range []string{"imports", "batches", "resets"} {
		root, err := safePath(a.Home, category)
		if err != nil {
			return err
		}
		entries, err := os.ReadDir(root)
		if os.IsNotExist(err) {
			continue
		}
		if err != nil {
			return err
		}
		for _, entry := range entries {
			if !entry.IsDir() {
				continue
			}
			rel := filepath.Join(category, entry.Name())
			var before, after State
			beforePath, err := safePath(a.Home, filepath.Join(rel, "before.json"))
			if err != nil {
				return err
			}
			afterPath, err := safePath(a.Home, filepath.Join(rel, "after.json"))
			if err != nil {
				return err
			}
			if loadJSON(beforePath, &before) != nil || loadJSON(afterPath, &after) != nil {
				continue
			}
			if reflect.DeepEqual(after, a.State) && entry.Name() > newest {
				keep, newest = rel, entry.Name()
			}
		}
	}
	if keep == "" {
		return nil
	} // No verified replacement: retain recovery data.
	if err := a.checkState(); err != nil {
		return err
	}
	return pruneCatalogBackups(a.Home, keep)
}

type importOptions struct {
	MinimumFrames int
	Progress      func(int, string)
}

func validMinimum(n int) error {
	if n < 2 || n > 256 {
		return errors.New("动画最低帧数须为 2～256 的整数")
	}
	return nil
}

// Standalone conversion helpers retain their explicit historical policy;
// application imports always pass the persisted user setting (default 30).
func conversionOptions(options []importOptions) importOptions {
	if len(options) > 0 {
		return options[0]
	}
	return importOptions{MinimumFrames: 2}
}

func (o importOptions) report(percent int, stage string) {
	if o.Progress != nil {
		o.Progress(max(0, min(100, percent)), stage)
	}
}

func (o importOptions) retainedFrames(count int) int {
	// Capacity is derived from 512x512 DXT1 bytes plus the 80-byte header;
	// keep the quality policy rather than reducing image size to hit a threshold.
	capacity := ((512 << 10) - 1 - 80) / vtfLevelBytes(512, 512, 13)
	kept := min(count, capacity)
	if count > 1 && kept < o.MinimumFrames {
		return 1
	}
	return kept
}

func (o importOptions) explain(a *animationImport) {
	if a.Original > 1 && a.Kept == 1 {
		a.MinimumFrames = o.MinimumFrames
		a.StaticFallback = true
	}
}

type progressReader struct {
	reader      io.Reader
	total, read int64
	options     importOptions
	last        int
}

func (r *progressReader) Read(p []byte) (int, error) {
	n, err := r.reader.Read(p)
	r.read += int64(n)
	if r.total > 0 {
		percent := 5 + int(min(r.read, r.total)*25/r.total)
		if percent != r.last {
			r.last = percent
			r.options.report(percent, "读取并校验全部 APNG 数据")
		}
	}
	return n, err
}

// Delete only superseded catalog snapshots, never texture/master/source files
// or game recovery journals. The newest before/after pair is one backup set.
func pruneCatalogBackups(home, keep string) error {
	parts := strings.Split(filepath.ToSlash(keep), "/")
	if len(parts) != 2 || (parts[0] != "imports" && parts[0] != "batches" && parts[0] != "resets") || parts[1] == "" || parts[1] == "." || parts[1] == ".." {
		return errors.New("最新清单备份路径异常，保留旧备份")
	}
	for _, name := range []string{"before.json", "after.json"} {
		path, err := safePath(home, filepath.Join(keep, name))
		if err != nil {
			return err
		}
		var snapshot State
		if err = loadJSON(path, &snapshot); err != nil {
			return err
		}
	}
	for _, category := range []string{"imports", "batches", "resets"} {
		root, err := safePath(home, category)
		if err != nil {
			return err
		}
		entries, err := os.ReadDir(root)
		if os.IsNotExist(err) {
			continue
		}
		if err != nil {
			return err
		}
		for _, entry := range entries {
			if !entry.IsDir() {
				continue
			}
			rel := filepath.Join(category, entry.Name())
			if filepath.Clean(rel) == filepath.Clean(keep) {
				continue
			}
			for _, name := range []string{"before.json", "after.json"} {
				path, err := safePath(home, filepath.Join(rel, name))
				if err != nil {
					return err
				}
				if err = os.Remove(path); err != nil && !os.IsNotExist(err) {
					return fmt.Errorf("旧清单备份清理失败：%w", err)
				}
			}
		}
	}
	return nil
}
