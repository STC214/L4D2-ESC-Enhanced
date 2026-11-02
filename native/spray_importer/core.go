package main

import (
	"bytes"
	"crypto/rand"
	"crypto/sha256"
	_ "embed"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"hash/crc32"
	"image"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"sort"
	"strings"
	"syscall"
	"time"
)

//go:embed assets/selector.vpk
var embeddedVPK []byte

const vpkName = "CSP_Numbered_Selector_TEST.vpk"
const prefix = "materials/vgui/logos/csp_test/"
const defaultGame = `E:\SteamLibrary\steamapps\common\Left 4 Dead 2`

type Slot struct{ Title, Texture, Preview, SHA256, Source, SortKey string }
type State struct{ Slots map[int]Slot }
type Build struct {
	StateHash string
	Files     map[string]string
	Changed   []string
	BaseHash  string
}
type Change struct{ Before, After string }
type Transaction struct {
	Game, Status string
	Files        map[string]Change
	Guards       map[string]string
}
type App struct {
	Home, Game string
	State      State
}

func digest(b []byte) string { h := sha256.Sum256(b); return hex.EncodeToString(h[:]) }
func fileHash(path string) (string, error) {
	b, e := os.ReadFile(path)
	if e != nil {
		return "", e
	}
	return digest(b), nil
}
func identifier() string {
	var b [8]byte
	if _, e := rand.Read(b[:]); e != nil {
		panic(e)
	}
	return time.Now().Format("20060102-150405") + "-" + hex.EncodeToString(b[:])
}
func saveJSON(path string, v any) error {
	b, e := json.MarshalIndent(v, "", "  ")
	if e != nil {
		return e
	}
	return atomicWrite(path, append(b, '\n'))
}
func loadJSON(path string, v any) error {
	b, e := os.ReadFile(path)
	if e != nil {
		return e
	}
	return json.Unmarshal(b, v)
}
func validSlot(n int) error {
	if n < 1 || n > 40 {
		return errors.New("槽位须为 1～40")
	}
	return nil
}
func slotPath(n int, ext string) string { return fmt.Sprintf("%stest_%03d.%s", prefix, n, ext) }

func safePath(base, relative string) (string, error) {
	if filepath.IsAbs(relative) || strings.Contains(relative, ":") {
		return "", errors.New("非法绝对路径")
	}
	base, e := filepath.Abs(base)
	if e != nil {
		return "", e
	}
	path := filepath.Join(base, filepath.FromSlash(relative))
	rel, e := filepath.Rel(base, path)
	if e != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(os.PathSeparator)) {
		return "", errors.New("路径越界")
	}
	for at := path; ; at = filepath.Dir(at) {
		info, e := os.Lstat(at)
		if e == nil {
			attributes, ok := info.Sys().(*syscall.Win32FileAttributeData)
			if info.Mode()&os.ModeSymlink != 0 || (ok && attributes.FileAttributes&syscall.FILE_ATTRIBUTE_REPARSE_POINT != 0) {
				return "", errors.New("不写入链接或重解析路径")
			}
		}
		if e != nil && !os.IsNotExist(e) {
			return "", e
		}
		if filepath.Dir(at) == at {
			break
		}
	}
	return path, nil
}

func newApp(home, game string) (*App, error) {
	a := &App{Home: home, Game: game, State: State{Slots: map[int]Slot{}}}
	e := loadJSON(filepath.Join(home, "slots.json"), &a.State)
	if e != nil && !os.IsNotExist(e) {
		return nil, e
	}
	if a.State.Slots == nil {
		a.State.Slots = map[int]Slot{}
	}
	for n := range a.State.Slots {
		if e := validSlot(n); e != nil {
			return nil, e
		}
	}
	return a, nil
}

func (a *App) checkState() error {
	var disk State
	err := loadJSON(filepath.Join(a.Home, "slots.json"), &disk)
	if os.IsNotExist(err) && len(a.State.Slots) == 0 {
		return nil
	}
	if err != nil {
		return err
	}
	if disk.Slots == nil {
		disk.Slots = map[int]Slot{}
	}
	if !reflect.DeepEqual(disk, a.State) {
		return errors.New("导入清单已被外部修改，请重新打开工具再操作")
	}
	return nil
}

func (a *App) checkPending() error {
	var rel string
	err := loadJSON(filepath.Join(a.Home, "last-deploy.json"), &rel)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return err
	}
	tx, err := safePath(a.Home, rel)
	if err != nil {
		return err
	}
	var journal Transaction
	if err = loadJSON(filepath.Join(tx, "transaction.json"), &journal); err != nil {
		return err
	}
	if journal.Status != "INSTALLED_RUNTIME_PENDING" && journal.Status != "ROLLED_BACK" {
		return errors.New("有未完成的部署或回退，请先在原游戏目录完成回退；保留现有恢复记录")
	}
	return nil
}

func (a *App) Import(path string, n int) error {
	if e := validSlot(n); e != nil {
		return e
	}
	if e := a.checkState(); e != nil {
		return e
	}
	img, e := loadImage(path)
	if e != nil {
		return imageError(path, e)
	}
	rel := "imports/" + identifier()
	folder, e := safePath(a.Home, rel)
	if e != nil {
		return e
	}
	if e = savePNG(filepath.Join(folder, "preview.png"), img); e != nil {
		return e
	}
	raw := encodeVTF(img)
	if e = atomicWrite(filepath.Join(folder, "texture.vtf"), raw); e != nil {
		return e
	}
	// Conversion can be slow; recheck before committing the new slot record.
	if e = a.checkState(); e != nil {
		return e
	}
	source, e := filepath.Abs(path)
	if e != nil {
		return e
	}
	row := Slot{Title: filepath.Base(path), Texture: rel + "/texture.vtf", Preview: rel + "/preview.png", SHA256: digest(raw), Source: filepath.Clean(source), SortKey: filepath.ToSlash(source)}
	previous, exists := a.State.Slots[n]
	a.State.Slots[n] = row
	if e = saveJSON(filepath.Join(a.Home, "slots.json"), a.State); e != nil {
		if exists {
			a.State.Slots[n] = previous
		} else {
			delete(a.State.Slots, n)
		}
		return e
	}
	return nil
}

func (a *App) Preview(n int) (image.Image, error) {
	if e := validSlot(n); e != nil {
		return nil, e
	}
	if s, ok := a.State.Slots[n]; ok {
		p, e := safePath(a.Home, s.Texture)
		if e != nil {
			return nil, e
		}
		raw, e := os.ReadFile(p)
		if e != nil {
			return nil, e
		}
		if digest(raw) != s.SHA256 {
			return nil, errors.New("导入素材哈希不符")
		}
		return decodeVTF(raw)
	}
	files, e := readVPK(embeddedVPK)
	if e != nil {
		return nil, e
	}
	return decodeVTF(files[slotPath(n, "vtf")])
}

func (a *App) Build() (string, error) {
	if e := a.checkState(); e != nil {
		return "", e
	}
	if len(a.State.Slots) == 0 {
		return "", errors.New("请先导入图片")
	}
	files, e := readVPK(embeddedVPK)
	if e != nil {
		return "", e
	}
	stateBytes, e := os.ReadFile(filepath.Join(a.Home, "slots.json"))
	if e != nil {
		return "", e
	}
	// Bind the hash to exactly the state snapshot used by this build, not to
	// a second, possibly newer file read after the initial consistency check.
	var snapshot State
	if e = json.Unmarshal(stateBytes, &snapshot); e != nil {
		return "", e
	}
	if snapshot.Slots == nil {
		snapshot.Slots = map[int]Slot{}
	}
	if !reflect.DeepEqual(snapshot, a.State) {
		return "", errors.New("导入清单在构建开始时发生变化，请重新打开工具")
	}
	meta := Build{StateHash: digest(stateBytes), Files: map[string]string{}, BaseHash: digest(embeddedVPK)}
	for n, s := range a.State.Slots {
		if e := validSlot(n); e != nil {
			return "", e
		}
		p, e := safePath(a.Home, s.Texture)
		if e != nil {
			return "", e
		}
		b, e := os.ReadFile(p)
		if e != nil {
			return "", e
		}
		if digest(b) != s.SHA256 {
			return "", errors.New("导入图片已被外部修改")
		}
		if _, e = decodeVTF(b); e != nil {
			return "", e
		}
		name := slotPath(n, "vtf")
		files[name] = b
		meta.Changed = append(meta.Changed, name)
	}
	sort.Strings(meta.Changed)
	out, e := writeVPK(files)
	if e != nil {
		return "", e
	}
	folder := filepath.Join(a.Home, "builds", identifier())
	vpkRel := "left4dead2/addons/" + vpkName
	if e = atomicWrite(filepath.Join(folder, filepath.FromSlash(vpkRel)), out); e != nil {
		return "", e
	}
	meta.Files[vpkRel] = digest(out)
	for n := 1; n <= 40; n++ {
		for _, ext := range []string{"vtf", "vmt"} {
			name := slotPath(n, ext)
			data, ok := files[name]
			if !ok {
				return "", errors.New("基础素材缺失")
			}
			rel := "update/" + name
			if e = atomicWrite(filepath.Join(folder, filepath.FromSlash(rel)), data); e != nil {
				return "", e
			}
			meta.Files[rel] = digest(data)
		}
	}
	if e = saveJSON(filepath.Join(folder, "manifest.json"), meta); e != nil {
		return "", e
	}
	rel, e := filepath.Rel(a.Home, folder)
	if e != nil {
		return "", e
	}
	if e = saveJSON(filepath.Join(a.Home, "latest.json"), rel); e != nil {
		return "", e
	}
	return folder, nil
}

func expectedPaths() []string {
	paths := []string{"left4dead2/addons/" + vpkName}
	for n := 1; n <= 40; n++ {
		for _, ext := range []string{"vtf", "vmt"} {
			paths = append(paths, "update/"+slotPath(n, ext))
		}
	}
	return paths
}
func exactFiles(files map[string]string) bool {
	if len(files) != 81 {
		return false
	}
	for _, p := range expectedPaths() {
		if len(files[p]) != 64 {
			return false
		}
	}
	return true
}

func (a *App) validateGame() error {
	b, e := os.ReadFile(filepath.Join(a.Game, "left4dead2", "gameinfo.txt"))
	if e != nil {
		return errors.New("游戏目录未找到 left4dead2/gameinfo.txt")
	}
	clean := regexp.MustCompile(`(?m)//[^\r\n]*`).ReplaceAllString(string(b), "")
	m := regexp.MustCompile(`(?is)"?SearchPaths"?\s*\{\s*"?Game"?\s+"?([^"\s}]+)`).FindStringSubmatch(clean)
	if len(m) != 2 || m[1] != "update" {
		return errors.New("MOD 路径不是 update，需要先适配")
	}
	if _, e = os.Stat(filepath.Join(a.Game, "bin/neko/plugins/CSPSelector.dll")); e != nil {
		return errors.New("请先安装已验证的 CSPSelector.dll 和 L4N")
	}
	return nil
}

func (a *App) guards() map[string]string {
	m := map[string]string{}
	for _, rel := range []string{"bin/gameui.dll", "bin/engine.dll", "bin/neko/plugins/CSPSelector.dll", "bin/neko/plugins/CSessionDefaults.dll", "left4dead2/cfg/config.cfg", "left4dead2/addons/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk"} {
		if h, e := fileHash(filepath.Join(a.Game, filepath.FromSlash(rel))); e == nil {
			m[rel] = h
		}
	}
	return m
}

func (a *App) Deploy(skipProcessCheck bool) (string, error) {
	if e := a.checkPending(); e != nil {
		return "", e
	}
	if !skipProcessCheck {
		if e := gameStopped(); e != nil {
			return "", e
		}
	}
	if e := a.validateGame(); e != nil {
		return "", e
	}
	var rel string
	if e := loadJSON(filepath.Join(a.Home, "latest.json"), &rel); e != nil {
		return "", errors.New("请先构建部署包")
	}
	folder, e := safePath(a.Home, rel)
	if e != nil {
		return "", e
	}
	var meta Build
	if e = loadJSON(filepath.Join(folder, "manifest.json"), &meta); e != nil {
		return "", e
	}
	if !exactFiles(meta.Files) || meta.BaseHash != digest(embeddedVPK) {
		return "", errors.New("部署清单与内置基线不符")
	}
	stateHash, e := fileHash(filepath.Join(a.Home, "slots.json"))
	if e != nil || stateHash != meta.StateHash {
		return "", errors.New("导入记录已更新，请重新构建")
	}
	sources := map[string][]byte{}
	before := map[string][]byte{}
	for _, p := range expectedPaths() {
		source, e := safePath(folder, p)
		if e != nil {
			return "", e
		}
		b, e := os.ReadFile(source)
		if e != nil {
			return "", e
		}
		if digest(b) != meta.Files[p] {
			return "", fmt.Errorf("构建文件校验失败：%s", p)
		}
		sources[p] = b
		target, e := safePath(a.Game, p)
		if e != nil {
			return "", e
		}
		before[p], e = os.ReadFile(target)
		if e != nil {
			return "", fmt.Errorf("请先安装基础选择器及 MOD 路径素材：%s", p)
		}
	}
	packed, e := readVPK(sources["left4dead2/addons/"+vpkName])
	if e != nil {
		return "", e
	}
	for _, p := range expectedPaths()[1:] {
		if !bytes.Equal(packed[strings.TrimPrefix(p, "update/")], sources[p]) {
			return "", errors.New("预览包与 MOD 素材不一致")
		}
	}
	tx := filepath.Join(a.Home, "transactions", identifier())
	journal := Transaction{Game: a.Game, Status: "PREPARED", Files: map[string]Change{}, Guards: a.guards()}
	for _, p := range expectedPaths() {
		if e = atomicWrite(filepath.Join(tx, "before", filepath.FromSlash(p)), before[p]); e != nil {
			return "", e
		}
		journal.Files[p] = Change{digest(before[p]), digest(sources[p])}
	}
	if e = saveJSON(filepath.Join(tx, "transaction.json"), journal); e != nil {
		return "", e
	}
	txrel, _ := filepath.Rel(a.Home, tx)
	if e = saveJSON(filepath.Join(a.Home, "last-deploy.json"), txrel); e != nil {
		return "", e
	}
	for _, p := range expectedPaths() {
		target, e := safePath(a.Game, p)
		if e != nil {
			return tx, e
		}
		h, e := fileHash(target)
		if e != nil || h != journal.Files[p].Before {
			return tx, errors.New("目标在备份后发生变化；已保留回退事务")
		}
		if e = atomicWrite(target, sources[p]); e != nil {
			return tx, e
		}
	}
	for p, h := range journal.Guards {
		actual, e := fileHash(filepath.Join(a.Game, filepath.FromSlash(p)))
		if e != nil || actual != h {
			return tx, errors.New("受保护文件变化，请检查日志与备份")
		}
	}
	journal.Status = "INSTALLED_RUNTIME_PENDING"
	return tx, saveJSON(filepath.Join(tx, "transaction.json"), journal)
}

func (a *App) Rollback(skipProcessCheck bool) error {
	if !skipProcessCheck {
		if e := gameStopped(); e != nil {
			return e
		}
	}
	var rel string
	if e := loadJSON(filepath.Join(a.Home, "last-deploy.json"), &rel); e != nil {
		return errors.New("没有部署回退记录")
	}
	tx, e := safePath(a.Home, rel)
	if e != nil {
		return e
	}
	var journal Transaction
	if e = loadJSON(filepath.Join(tx, "transaction.json"), &journal); e != nil {
		return e
	}
	if !strings.EqualFold(filepath.Clean(journal.Game), filepath.Clean(a.Game)) || len(journal.Files) != 81 {
		return errors.New("回退事务不属于当前游戏目录")
	}
	data := map[string][]byte{}
	for _, p := range expectedPaths() {
		row, ok := journal.Files[p]
		if !ok {
			return errors.New("回退清单缺少文件")
		}
		path, e := safePath(a.Game, p)
		if e != nil {
			return e
		}
		h, e := fileHash(path)
		if e != nil || (h != row.Before && h != row.After) {
			return fmt.Errorf("文件被外部修改，停止回退：%s", p)
		}
		backup, e := safePath(filepath.Join(tx, "before"), p)
		if e != nil {
			return e
		}
		data[p], e = os.ReadFile(backup)
		if e != nil || digest(data[p]) != row.Before {
			return errors.New("回退备份损坏")
		}
	}
	journal.Status = "ROLLBACK_PREPARED"
	if e = saveJSON(filepath.Join(tx, "transaction.json"), journal); e != nil {
		return e
	}
	for _, p := range expectedPaths() {
		if e = atomicWrite(filepath.Join(a.Game, filepath.FromSlash(p)), data[p]); e != nil {
			return e
		}
	}
	journal.Status = "ROLLED_BACK"
	return saveJSON(filepath.Join(tx, "transaction.json"), journal)
}

// Single-file VPK v1/v2. External archive references and corrupt CRCs are rejected.
func readVPK(raw []byte) (map[string][]byte, error) {
	if len(raw) < 12 || le.Uint32(raw) != 0x55aa1234 {
		return nil, errors.New("VPK 文件头损坏")
	}
	version := le.Uint32(raw[4:])
	header := 12
	if version == 2 {
		header = 28
	} else if version != 1 {
		return nil, errors.New("VPK 版本未支持")
	}
	end := header + int(le.Uint32(raw[8:]))
	if end > len(raw) || end < header {
		return nil, errors.New("VPK 目录越界")
	}
	at := header
	files := map[string][]byte{}
	str := func() (string, error) {
		if at >= end {
			return "", errors.New("VPK 字符串越界")
		}
		n := bytes.IndexByte(raw[at:end], 0)
		if n < 0 {
			return "", errors.New("VPK 字符串截断")
		}
		s := string(raw[at : at+n])
		at += n + 1
		return s, nil
	}
	for {
		ext, e := str()
		if e != nil {
			return nil, e
		}
		if ext == "" {
			break
		}
		for {
			dir, e := str()
			if e != nil {
				return nil, e
			}
			if dir == "" {
				break
			}
			for {
				name, e := str()
				if e != nil {
					return nil, e
				}
				if name == "" {
					break
				}
				if at+18 > end {
					return nil, errors.New("VPK 条目截断")
				}
				crc, pre, archive, offset, size, term := le.Uint32(raw[at:]), int(le.Uint16(raw[at+4:])), le.Uint16(raw[at+6:]), int(le.Uint32(raw[at+8:])), int(le.Uint32(raw[at+12:])), le.Uint16(raw[at+16:])
				at += 18
				if term != 0xffff || at+pre > end || offset > len(raw)-end || size > len(raw)-end-offset || (size > 0 && archive != 0x7fff) {
					return nil, errors.New("VPK 条目无效或外部分卷")
				}
				data := append([]byte{}, raw[at:at+pre]...)
				at += pre
				data = append(data, raw[end+offset:end+offset+size]...)
				if crc32.ChecksumIEEE(data) != crc {
					return nil, errors.New("VPK CRC 校验失败")
				}
				key := name
				if ext != " " {
					key += "." + ext
				}
				if dir != " " {
					key = dir + "/" + key
				}
				if _, exists := files[key]; exists {
					return nil, errors.New("VPK 重复文件")
				}
				files[key] = data
			}
		}
	}
	if at != end {
		return nil, errors.New("VPK 目录结尾异常")
	}
	return files, nil
}

func writeVPK(files map[string][]byte) ([]byte, error) {
	type entry struct{ ext, dir, name, key string }
	var entries []entry
	for key := range files {
		ext := strings.TrimPrefix(filepath.Ext(key), ".")
		if ext == "" {
			ext = " "
		}
		dir := filepath.ToSlash(filepath.Dir(key))
		if dir == "." {
			dir = " "
		}
		name := strings.TrimSuffix(filepath.Base(key), filepath.Ext(key))
		entries = append(entries, entry{ext, dir, name, key})
	}
	sort.Slice(entries, func(i, j int) bool {
		a, b := entries[i], entries[j]
		if a.ext != b.ext {
			return a.ext < b.ext
		}
		if a.dir != b.dir {
			return a.dir < b.dir
		}
		return a.name < b.name
	})
	var tree, payload bytes.Buffer
	oldExt, oldDir := "", ""
	for _, item := range entries {
		if item.ext != oldExt {
			if oldExt != "" {
				tree.WriteByte(0)
				tree.WriteByte(0)
			}
			tree.WriteString(item.ext)
			tree.WriteByte(0)
			oldExt = item.ext
			oldDir = ""
		}
		if item.dir != oldDir {
			if oldDir != "" {
				tree.WriteByte(0)
			}
			tree.WriteString(item.dir)
			tree.WriteByte(0)
			oldDir = item.dir
		}
		tree.WriteString(item.name)
		tree.WriteByte(0)
		data := files[item.key]
		_ = binary.Write(&tree, le, crc32.ChecksumIEEE(data))
		_ = binary.Write(&tree, le, uint16(0))
		_ = binary.Write(&tree, le, uint16(0x7fff))
		_ = binary.Write(&tree, le, uint32(payload.Len()))
		_ = binary.Write(&tree, le, uint32(len(data)))
		_ = binary.Write(&tree, le, uint16(0xffff))
		payload.Write(data)
	}
	if len(entries) > 0 {
		tree.WriteByte(0)
		tree.WriteByte(0)
	}
	tree.WriteByte(0)
	var out bytes.Buffer
	for _, v := range []uint32{0x55aa1234, 1, uint32(tree.Len())} {
		_ = binary.Write(&out, le, v)
	}
	out.Write(tree.Bytes())
	out.Write(payload.Bytes())
	result := out.Bytes()
	round, e := readVPK(result)
	if e != nil {
		return nil, e
	}
	if len(round) != len(files) {
		return nil, errors.New("VPK 写入条目数量不一致")
	}
	for k, v := range files {
		if !bytes.Equal(v, round[k]) {
			return nil, errors.New("VPK 读回不一致")
		}
	}
	return result, nil
}
