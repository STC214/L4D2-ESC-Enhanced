package main

import (
	"errors"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"sort"
	"strings"
)

const maxImportVPK = 256 << 20

// Treat package paths only as identifiers, never as extraction destinations.
func packagePath(name string) (string, error) {
	name = strings.ToLower(strings.ReplaceAll(name, `\`, "/"))
	if strings.HasPrefix(name, "/") || strings.ContainsAny(name, ":\x00") {
		return "", errors.New("VPK 含非法资源路径")
	}
	for _, part := range strings.Split(name, "/") {
		if part == ".." {
			return "", errors.New("VPK 含越界资源路径")
		}
	}
	return path.Clean(name), nil
}

func sprayMembers(files map[string][]byte) ([]string, error) {
	textures := map[string]bool{}
	for name, data := range files {
		if !strings.HasPrefix(name, "materials/vgui/logos/") || strings.Contains(name, "/ui/") {
			continue
		}
		switch path.Ext(name) {
		case ".vtf":
			textures[name] = true
		case ".vmt":
			reference, err := materialTexture(data)
			if err != nil {
				return nil, fmt.Errorf("%s：%w", name, err)
			}
			ref, err := packagePath(reference)
			if err != nil {
				return nil, err
			}
			ref = strings.TrimPrefix(ref, "materials/")
			if !strings.HasSuffix(ref, ".vtf") {
				ref += ".vtf"
			}
			ref = "materials/" + ref
			if _, ok := files[ref]; !ok {
				return nil, fmt.Errorf("喷漆材质 %s 缺少贴图 %s", name, ref)
			}
			textures[ref] = true
		}
	}
	if len(textures) == 0 {
		return nil, errors.New("VPK 中未找到 materials/vgui/logos 下的喷漆资源")
	}
	if len(textures) > 40 {
		return nil, errors.New("VPK 内喷漆超过 40 张；本批尚未提交")
	}
	names := make([]string, 0, len(textures))
	for name := range textures {
		names = append(names, name)
	}
	sort.Slice(names, func(i, j int) bool { return naturalLess(names[i], names[j]) })
	return names, nil
}

// ImportVPKs expands one or two self-contained VPKs into a private numbered
// staging directory. Only structurally validated textures enter the selector,
// byte-for-byte, never source scripts or decoded picture previews.
// The source VPKs stay untouched; both packages commit as one batch.
func (a *App) ImportVPKs(packages []string) (BatchResult, error) {
	result := BatchResult{}
	if len(packages) < 1 || len(packages) > 2 {
		return result, errors.New("请选择 1～2 个喷漆 VPK")
	}
	if err := a.checkState(); err != nil {
		return result, err
	}
	var inputs []batchInput
	seen := map[string]bool{}
	staging := filepath.Join(a.Home, "vpk-sources", identifier())
	// Delete only our explicitly generated staging files, never recurse through
	// source paths or remove the retained batch's converted textures/backups.
	var staged []string
	defer func() {
		for _, filename := range staged {
			os.Remove(filename)
		}
		os.Remove(staging)
	}()
	for _, filename := range packages {
		filename, err := filepath.Abs(filename)
		if err != nil {
			return result, err
		}
		if !strings.EqualFold(filepath.Ext(filename), ".vpk") {
			return result, errors.New("请选择 .vpk 文件")
		}
		home, err := filepath.Abs(a.Home)
		if err != nil {
			return result, err
		}
		relative, err := filepath.Rel(home, filename)
		if err == nil && relative != ".." && !strings.HasPrefix(relative, ".."+string(os.PathSeparator)) {
			return result, errors.New("请选原始喷漆 VPK，不要导入工具自己的数据目录")
		}
		if _, err = safePath(filepath.Dir(filename), filepath.Base(filename)); err != nil {
			return result, err
		}
		key := strings.ToLower(filepath.Clean(filename))
		if seen[key] {
			return result, errors.New("重复选择了同一个 VPK")
		}
		seen[key] = true
		f, err := os.Open(filename)
		if err != nil {
			return result, err
		}
		raw, err := io.ReadAll(io.LimitReader(f, maxImportVPK+1))
		f.Close()
		if err != nil || len(raw) > maxImportVPK {
			return result, fmt.Errorf("VPK 读取失败或超过 256 MiB：%s", filename)
		}
		members, err := readVPK(raw)
		if err != nil {
			return result, fmt.Errorf("%s：%w（请使用完整的单文件 VPK）", filepath.Base(filename), err)
		}
		files := make(map[string][]byte, len(members))
		for name, data := range members {
			name, err = packagePath(name)
			if err != nil {
				return result, err
			}
			if _, exists := files[name]; exists {
				return result, errors.New("VPK 存在大小写或分隔符冲突的资源")
			}
			files[name] = data
		}
		names, err := sprayMembers(files)
		if err != nil {
			return result, fmt.Errorf("%s：%w", filepath.Base(filename), err)
		}
		if len(inputs)+len(names) > 40 {
			return result, errors.New("两个 VPK 合计超过 40 张；本批尚未提交")
		}
		for _, name := range names {
			if len(files[name]) > 32<<20 {
				return result, fmt.Errorf("喷漆贴图超过 32 MiB：%s", name)
			}
			if len(files[name]) < 4 || string(files[name][:4]) != "VTF\x00" {
				return result, fmt.Errorf("喷漆贴图不是有效的 VTF：%s", name)
			}
			if _, err = inspectVTF(files[name]); err != nil {
				return result, fmt.Errorf("%s :: %s：%w", filepath.Base(filename), name, err)
			}
			dest := filepath.Join(staging, fmt.Sprintf("%03d.vtf", len(inputs)+1))
			staged = append(staged, dest)
			if err = atomicWrite(dest, files[name]); err != nil {
				return result, err
			}
			inputs = append(inputs, batchInput{dest, filename + "::" + name, path.Base(name), filepath.Base(filename) + "/" + name})
		}
	}
	return a.importBatch(inputs, result, true)
}
