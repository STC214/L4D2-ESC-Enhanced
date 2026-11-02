package main

import (
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"syscall"
)

// Compare digit runs as integers without integer conversion/overflow.
func naturalLess(a, b string) bool {
	x, y := strings.ToLower(a), strings.ToLower(b)
	for len(x) > 0 && len(y) > 0 {
		if x[0] >= '0' && x[0] <= '9' && y[0] >= '0' && y[0] <= '9' {
			i, j := 0, 0
			for i < len(x) && x[i] >= '0' && x[i] <= '9' {
				i++
			}
			for j < len(y) && y[j] >= '0' && y[j] <= '9' {
				j++
			}
			xv, yv := strings.TrimLeft(x[:i], "0"), strings.TrimLeft(y[:j], "0")
			if len(xv) != len(yv) {
				return len(xv) < len(yv)
			}
			if xv != yv {
				return xv < yv
			}
			if i != j {
				return i < j
			}
			x, y = x[i:], y[j:]
			continue
		}
		if x[0] != y[0] {
			return x[0] < y[0]
		}
		x, y = x[1:], y[1:]
	}
	if len(x) != len(y) {
		return len(x) < len(y)
	}
	return a < b
}

type BatchResult struct {
	Imported, Updated, Total, Skipped int
	Folder                            string
}

func scanFolder(root string) ([]string, int, error) {
	root, e := filepath.Abs(root)
	if e != nil {
		return nil, 0, e
	}
	if _, e = safePath(root, "."); e != nil {
		return nil, 0, e
	}
	info, e := os.Stat(root)
	if e != nil {
		return nil, 0, e
	}
	if !info.IsDir() {
		return nil, 0, errors.New("请选择目录")
	}
	var files []string
	skipped := 0
	e = filepath.WalkDir(root, func(path string, entry fs.DirEntry, walkError error) error {
		if walkError != nil {
			return walkError
		}
		info, e := entry.Info()
		if e != nil {
			return e
		}
		attributes, ok := info.Sys().(*syscall.Win32FileAttributeData)
		if info.Mode()&os.ModeSymlink != 0 || (ok && attributes.FileAttributes&syscall.FILE_ATTRIBUTE_REPARSE_POINT != 0) {
			skipped++
			if entry.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}
		if entry.IsDir() {
			return nil
		}
		switch strings.ToLower(filepath.Ext(path)) {
		case ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".vtf":
			if !info.Mode().IsRegular() {
				skipped++
				return nil
			}
			files = append(files, path)
			if len(files) > 40 {
				return errors.New("目录中支持的图片超过 40 张，请拆分目录；本批尚未提交")
			}
		default:
			skipped++
		}
		return nil
	})
	if e != nil {
		return nil, skipped, e
	}
	if len(files) == 0 {
		return nil, skipped, errors.New("目录中没有支持的图片（PNG/JPEG/GIF/BMP/VTF）")
	}
	sort.Slice(files, func(i, j int) bool {
		a, b := filepath.Base(files[i]), filepath.Base(files[j])
		if a != b {
			return naturalLess(a, b)
		}
		return naturalLess(files[i], files[j])
	})
	return files, skipped, nil
}

func (a *App) ImportFolder(root string) (BatchResult, error) {
	result := BatchResult{}
	if e := a.checkState(); e != nil {
		return result, e
	}
	root, e := filepath.Abs(root)
	if e != nil {
		return result, e
	}
	files, skipped, e := scanFolder(root)
	result.Skipped = skipped
	if e != nil {
		return result, e
	}
	// Reject importing our own generated images recursively into the catalog.
	home, e := filepath.Abs(a.Home)
	if e != nil {
		return result, e
	}
	for _, path := range files {
		relative, e := filepath.Rel(home, path)
		if e == nil && relative != ".." && !strings.HasPrefix(relative, ".."+string(os.PathSeparator)) {
			return result, errors.New("请选原始图片目录，不要导入工具自己的数据目录")
		}
	}
	merged := map[string]Slot{}
	// Select the lowest original slot as the update target when the user has
	// intentionally imported the same source into multiple manual slots.
	// Iterating a Go map here made that choice nondeterministic.
	for n := 1; n <= 40; n++ {
		row, exists := a.State.Slots[n]
		if !exists {
			continue
		}
		key := fmt.Sprintf("legacy:%03d", n)
		if row.Source != "" {
			key = strings.ToLower(filepath.Clean(row.Source))
		}
		// Preserve two intentionally duplicated manual slots as separate rows.
		if _, exists := merged[key]; exists {
			key = fmt.Sprintf("legacy:%03d", n)
		}
		merged[key] = row
	}
	for _, path := range files {
		key := strings.ToLower(filepath.Clean(path))
		if _, ok := merged[key]; !ok {
			merged[key] = Slot{}
			result.Imported++
		} else {
			result.Updated++
		}
	}
	if len(merged) > 40 {
		return result, fmt.Errorf("合并已有图片后为 %d 张，超过 40 槽位；本批尚未提交", len(merged))
	}
	rel := "batches/" + identifier()
	folder, e := safePath(a.Home, rel)
	if e != nil {
		return result, e
	}
	result.Folder = folder
	for i, path := range files {
		if _, e = safePath(root, strings.TrimPrefix(path, root+string(os.PathSeparator))); e != nil {
			return result, e
		}
		img, e := loadImage(path)
		if e != nil {
			return result, imageError(path, e)
		}
		item := fmt.Sprintf("%s/items/%03d", rel, i+1)
		if e = savePNG(filepath.Join(a.Home, filepath.FromSlash(item), "preview.png"), img); e != nil {
			return result, e
		}
		raw := encodeVTF(img)
		if e = atomicWrite(filepath.Join(a.Home, filepath.FromSlash(item), "texture.vtf"), raw); e != nil {
			return result, e
		}
		key, _ := filepath.Rel(root, path)
		merged[strings.ToLower(filepath.Clean(path))] = Slot{Title: filepath.Base(path), Texture: item + "/texture.vtf", Preview: item + "/preview.png", SHA256: digest(raw), Source: path, SortKey: filepath.ToSlash(key)}
	}
	type entry struct {
		Key string
		Row Slot
	}
	rows := make([]entry, 0, len(merged))
	for key, row := range merged {
		rows = append(rows, entry{key, row})
	}
	sort.Slice(rows, func(i, j int) bool {
		x, y := rows[i], rows[j]
		if x.Row.Title != y.Row.Title {
			return naturalLess(x.Row.Title, y.Row.Title)
		}
		if x.Row.SortKey != y.Row.SortKey {
			return naturalLess(x.Row.SortKey, y.Row.SortKey)
		}
		return x.Key < y.Key
	})
	next := State{Slots: map[int]Slot{}}
	for i, row := range rows {
		next.Slots[i+1] = row.Row
	}
	if e = a.checkState(); e != nil {
		return result, e
	}
	if e = saveJSON(filepath.Join(folder, "before.json"), a.State); e != nil {
		return result, e
	}
	if e = saveJSON(filepath.Join(folder, "after.json"), next); e != nil {
		return result, e
	}
	result.Total = len(rows)
	if e = saveJSON(filepath.Join(folder, "summary.json"), result); e != nil {
		return result, e
	}
	if e = saveJSON(filepath.Join(a.Home, "slots.json"), next); e != nil {
		return result, e
	}
	a.State = next
	return result, nil
}
