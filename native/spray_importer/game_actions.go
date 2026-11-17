package main

import (
	"bytes"
	_ "embed"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

//go:embed assets/CSPSelector.dll
var embeddedSelectorDLL []byte

const selectorDLLHash = "95960a82415de12ee920493b9915e4723332636dc82bf28c2f866e8693cb2129"
const selectorDLLPath = "bin/neko/plugins/CSPSelector.dll"
const addonListPath = "left4dead2/addonlist.txt"

type gameActionRef struct{ Kind, Reference string }
type gameFileState struct {
	Exists bool
	Hash   string
}
type gameChange struct{ Before, After gameFileState }
type gameJournal struct {
	Game, Kind, Status string
	Files              map[string]gameChange
	Guards             map[string]string
}
type gameFile struct {
	gameFileState
	Data []byte
}
type gamePlan struct {
	Game, Kind, StateHash string
	Before, After         map[string]gameFile
	Guards                map[string]string
}

func projectGamePaths() []string {
	paths := append([]string{}, expectedPaths()...)
	return append(paths, selectorDLLPath, "left4dead2/addons/"+cProjectVPK, "bin/neko/plugins/CSessionDefaults.dll", "left4dead2/addons/"+diagnosticVPK, addonListPath)
}
func allowedGameActionPath(path string, kind string) bool {
	for _, p := range projectGamePaths() {
		if path == p {
			if kind == "cleanup-all" || kind == "install-bundle" && path != "left4dead2/addons/"+diagnosticVPK {
				return true
			}
			return path != "left4dead2/addons/"+cProjectVPK && path != "bin/neko/plugins/CSessionDefaults.dll" && path != "left4dead2/addons/"+diagnosticVPK
		}
	}
	return false
}
func gameGuardPaths() []string {
	return []string{"bin/gameui.dll", "bin/engine.dll", "left4dead2/gameinfo.txt", "left4dead2/cfg/config.cfg", "bin/neko/source_nekomimi.exe"}
}

func readGameFile(base, relative string) (gameFile, error) {
	var result gameFile
	path, err := safePath(base, relative)
	if err != nil {
		return result, err
	}
	f, err := os.Open(path)
	if os.IsNotExist(err) {
		return result, nil
	}
	if err != nil {
		return result, err
	}
	defer f.Close()
	stat, err := f.Stat()
	if err != nil {
		return result, err
	}
	limit := int64(256 << 20)
	if relative == addonListPath {
		limit = 8 << 20
	}
	if !stat.Mode().IsRegular() || stat.Size() > limit {
		return result, errors.New("目标不是普通文件或超过备份预算")
	}
	data, err := io.ReadAll(io.LimitReader(f, limit+1))
	if err != nil {
		return result, err
	}
	if int64(len(data)) > limit {
		return result, errors.New("目标增长超过备份预算")
	}
	return gameFile{gameFileState{true, digest(data)}, data}, nil
}
func actionFile(data []byte) gameFile { return gameFile{gameFileState{true, digest(data)}, data} }

func (a *App) validateActionGame(install bool) error {
	if !filepath.IsAbs(a.Game) {
		return errors.New("游戏根目录须为绝对路径")
	}
	for _, p := range []string{"left4dead2.exe", "left4dead2/gameinfo.txt"} {
		f, err := readGameFile(a.Game, p)
		if err != nil {
			return err
		}
		if !f.Exists {
			return errors.New("未找到游戏根目录的 EXE 或 gameinfo.txt")
		}
	}
	if !install {
		return nil
	}
	info, err := readGameFile(a.Game, "left4dead2/gameinfo.txt")
	if err != nil {
		return err
	}
	clean := regexp.MustCompile(`(?m)//[^\r\n]*`).ReplaceAllString(string(info.Data), "")
	m := regexp.MustCompile(`(?is)"?SearchPaths"?\s*\{\s*"?Game"?\s+"?([^"\s}]+)`).FindStringSubmatch(clean)
	if len(m) != 2 || m[1] != "update" {
		return errors.New("MOD 首条路径须为 update")
	}
	loader, err := readGameFile(a.Game, "bin/neko/source_nekomimi.exe")
	if err != nil {
		return err
	}
	if !loader.Exists {
		return errors.New("请先安装配套 L4N；一键部署不安装或替换加载器")
	}
	return nil
}

func (a *App) actionGuards() (map[string]string, error) {
	guards := map[string]string{}
	for _, p := range gameGuardPaths() {
		f, err := readGameFile(a.Game, p)
		if err != nil {
			return nil, err
		}
		if f.Exists {
			guards[p] = f.Hash
		} else {
			guards[p] = ""
		}
	}
	return guards, nil
}
func (a *App) verifyActionGuards(guards map[string]string) error {
	if len(guards) != len(gameGuardPaths()) {
		return errors.New("受保护文件清单异常")
	}
	for _, p := range gameGuardPaths() {
		expected, ok := guards[p]
		if !ok {
			return errors.New("受保护文件清单缺项")
		}
		f, err := readGameFile(a.Game, p)
		if err != nil {
			return err
		}
		if f.Hash != expected {
			return fmt.Errorf("游戏原生文件、配置或 L4N 已变化：%s", p)
		}
	}
	return nil
}

func (a *App) newGamePlan(kind string, after map[string]gameFile) (*gamePlan, error) {
	plan := &gamePlan{Game: a.Game, Kind: kind, Before: map[string]gameFile{}, After: map[string]gameFile{}}
	var total int64
	for p, next := range after {
		if !allowedGameActionPath(p, kind) {
			return nil, errors.New("操作清单包含非项目路径")
		}
		before, err := readGameFile(a.Game, p)
		if err != nil {
			return nil, err
		}
		total += int64(len(before.Data) + len(next.Data))
		if total > 512<<20 {
			return nil, errors.New("项目操作超出 512 MiB 总备份预算")
		}
		if before.gameFileState == next.gameFileState {
			continue
		}
		plan.Before[p], plan.After[p] = before, next
	}
	var err error
	plan.Guards, err = a.actionGuards()
	return plan, err
}

// This is a dry run. No game files or local imports are changed.
func (a *App) PlanProjectCleanup(skipProcessCheck bool) (*gamePlan, error) {
	if err := a.checkPending(); err != nil {
		return nil, err
	}
	if !skipProcessCheck {
		if err := gameStopped(); err != nil {
			return nil, err
		}
	}
	if err := a.validateActionGame(false); err != nil {
		return nil, err
	}
	after := map[string]gameFile{}
	for _, p := range projectGamePaths() {
		after[p] = gameFile{}
	}
	addon, err := readGameFile(a.Game, addonListPath)
	if err != nil {
		return nil, err
	}
	if addon.Exists {
		patched, err := patchProjectAddons(addon.Data, true)
		if err != nil {
			return nil, err
		}
		after[addonListPath] = actionFile(patched)
	}
	return a.newGamePlan("cleanup-all", after)
}

func (a *App) OneClickDeploy(skipProcessCheck bool) (string, error) {
	if err := a.checkPending(); err != nil {
		return "", err
	}
	if !skipProcessCheck {
		if err := gameStopped(); err != nil {
			return "", err
		}
	}
	if err := a.validateActionGame(true); err != nil {
		return "", err
	}
	if digest(embeddedSelectorDLL) != selectorDLLHash {
		return "", errors.New("内置选择器 DLL 哈希异常")
	}
	if len(a.State.Slots) == 0 && !a.State.Defaults {
		err := func() error {
			progress := a.Progress
			a.Progress = nil
			defer func() { a.Progress = progress }()
			_, err := a.ResetDefaults()
			return err
		}()
		if err != nil {
			return "", err
		}
	}
	if a.Progress != nil {
		a.Progress(5, "自动构建喷漆部署包")
	}
	folder, err := a.Build()
	if err != nil {
		return "", err
	}
	var meta Build
	if err = loadJSON(filepath.Join(folder, "manifest.json"), &meta); err != nil {
		return "", err
	}
	if !exactFiles(meta.Files) || meta.BaseHash != digest(embeddedVPK) {
		return "", errors.New("构建清单不匹配内置基线")
	}
	after := map[string]gameFile{}
	for _, p := range expectedPaths() {
		f, err := readGameFile(folder, p)
		if err != nil {
			return "", err
		}
		if !f.Exists || f.Hash != meta.Files[p] {
			return "", errors.New("构建文件哈希异常")
		}
		after[p] = f
	}
	packed, err := readVPK(after["left4dead2/addons/"+vpkName].Data)
	if err != nil {
		return "", err
	}
	for _, p := range expectedPaths()[1:] {
		if !bytes.Equal(packed[strings.TrimPrefix(p, "update/")], after[p].Data) {
			return "", errors.New("构建包与游戏散装素材不一致")
		}
	}
	after[selectorDLLPath] = actionFile(embeddedSelectorDLL)
	addon, err := readGameFile(a.Game, addonListPath)
	if err != nil {
		return "", err
	}
	if !addon.Exists {
		addon = actionFile([]byte("\"AddonList\"\n{\n}\n"))
	}
	patched, err := patchProjectAddons(addon.Data, false)
	if err != nil {
		return "", err
	}
	after[addonListPath] = actionFile(patched)
	plan, err := a.newGamePlan("install-spray", after)
	if err != nil {
		return "", err
	}
	plan.StateHash = meta.StateHash
	return a.ApplyGamePlan(plan, skipProcessCheck)
}

func (a *App) saveGameAction(ref gameActionRef) error {
	path, err := safePath(a.Home, "last-action.json")
	if err != nil {
		return err
	}
	return saveJSON(path, ref)
}
func (a *App) readGameAction() (gameActionRef, error) {
	var ref gameActionRef
	path, err := safePath(a.Home, "last-action.json")
	if err != nil {
		return ref, err
	}
	err = loadJSON(path, &ref)
	if os.IsNotExist(err) {
		return gameActionRef{}, nil
	}
	if err != nil {
		return ref, err
	}
	if ref.Kind != "managed" && ref.Kind != "legacy" {
		return ref, errors.New("最近操作类型异常")
	}
	if ref.Kind == "managed" && (filepath.ToSlash(filepath.Dir(ref.Reference)) != "managed-transactions" || filepath.Base(ref.Reference) == "." || filepath.Base(ref.Reference) == "..") {
		return ref, errors.New("操作恢复路径异常")
	}
	if ref.Kind == "legacy" && filepath.ToSlash(filepath.Dir(ref.Reference)) != "transactions" {
		return ref, errors.New("旧部署恢复路径异常")
	}
	return ref, nil
}

func (a *App) loadGameJournal(ref gameActionRef) (string, gameJournal, error) {
	var journal gameJournal
	folder, err := safePath(a.Home, ref.Reference)
	if err != nil {
		return "", journal, err
	}
	err = loadJSON(filepath.Join(folder, "transaction.json"), &journal)
	if err != nil {
		return "", journal, err
	}
	if journal.Kind != "install-spray" && journal.Kind != "install-bundle" && journal.Kind != "cleanup-all" {
		return "", journal, errors.New("操作恢复类型异常")
	}
	if len(journal.Files) == 0 || len(journal.Files) > len(projectGamePaths()) {
		return "", journal, errors.New("操作恢复项目过多")
	}
	for p, row := range journal.Files {
		if !allowedGameActionPath(p, journal.Kind) {
			return "", journal, errors.New("恢复清单包含非项目文件")
		}
		for _, state := range []gameFileState{row.Before, row.After} {
			if state.Exists && (len(state.Hash) != 64) || !state.Exists && state.Hash != "" {
				return "", journal, errors.New("恢复文件哈希异常")
			}
		}
	}
	return folder, journal, nil
}

func (a *App) managedPending() error {
	ref, err := a.readGameAction()
	if err != nil {
		return err
	}
	if ref.Kind != "managed" {
		return nil
	}
	_, journal, err := a.loadGameJournal(ref)
	if err != nil {
		return err
	}
	if journal.Status != "DONE" && journal.Status != "ROLLED_BACK" {
		return errors.New("有未完成的一键部署或清理，请先回退最近操作；恢复记录已保留")
	}
	return nil
}

func (a *App) ApplyGamePlan(plan *gamePlan, skipProcessCheck bool) (string, error) {
	if plan == nil || !strings.EqualFold(filepath.Clean(a.Game), filepath.Clean(plan.Game)) {
		return "", errors.New("操作计划不属于当前游戏目录")
	}
	if err := a.checkPending(); err != nil {
		return "", err
	}
	if !skipProcessCheck {
		if err := gameStopped(); err != nil {
			return "", err
		}
	}
	if err := a.validateActionGame(plan.Kind == "install-spray" || plan.Kind == "install-bundle"); err != nil {
		return "", err
	}
	if plan.Kind != "install-spray" && plan.Kind != "install-bundle" && plan.Kind != "cleanup-all" {
		return "", errors.New("操作类型异常")
	}
	if plan.Kind == "install-spray" {
		h, err := fileHash(filepath.Join(a.Home, "slots.json"))
		if err != nil || h != plan.StateHash {
			return "", errors.New("槽位已变化，请重新一键部署")
		}
	}
	if len(plan.Before) != len(plan.After) {
		return "", errors.New("操作计划前后清单不匹配")
	}
	if err := a.verifyActionGuards(plan.Guards); err != nil {
		return "", err
	}
	paths := make([]string, 0, len(plan.After))
	for p, next := range plan.After {
		if !allowedGameActionPath(p, plan.Kind) {
			return "", errors.New("操作路径超出项目清单")
		}
		before, ok := plan.Before[p]
		if !ok {
			return "", errors.New("操作计划缺少原件")
		}
		current, err := readGameFile(a.Game, p)
		if err != nil {
			return "", err
		}
		if current.gameFileState != before.gameFileState {
			return "", fmt.Errorf("确认前后目标已变化，未执行：%s", p)
		}
		if next.Exists && digest(next.Data) != next.Hash || !next.Exists && (len(next.Data) != 0 || next.Hash != "") {
			return "", errors.New("操作计划数据校验失败")
		}
		paths = append(paths, p)
	}
	if len(paths) == 0 {
		return "", nil
	}
	sort.Strings(paths)
	rel := "managed-transactions/" + identifier()
	folder, err := safePath(a.Home, rel)
	if err != nil {
		return "", err
	}
	journal := gameJournal{Game: a.Game, Kind: plan.Kind, Status: "PREPARED", Files: map[string]gameChange{}, Guards: plan.Guards}
	for _, p := range paths {
		before := plan.Before[p]
		if before.Exists {
			if digest(before.Data) != before.Hash {
				return "", errors.New("计划备份哈希异常")
			}
			if err = atomicWrite(filepath.Join(folder, "before", filepath.FromSlash(p)), before.Data); err != nil {
				return "", err
			}
		}
		journal.Files[p] = gameChange{before.gameFileState, plan.After[p].gameFileState}
	}
	if err = saveJSON(filepath.Join(folder, "transaction.json"), journal); err != nil {
		return "", err
	}
	if err = a.saveGameAction(gameActionRef{"managed", rel}); err != nil {
		return "", err
	}
	if !skipProcessCheck {
		if err = gameStopped(); err != nil {
			return folder, err
		}
	}
	if err = a.verifyActionGuards(plan.Guards); err != nil {
		return folder, err
	}
	for i, p := range paths {
		current, err := readGameFile(a.Game, p)
		if err != nil {
			return folder, err
		}
		if current.gameFileState != plan.Before[p].gameFileState {
			return folder, fmt.Errorf("目标在备份后变化：%s；请保留恢复记录", p)
		}
		if a.Progress != nil {
			a.Progress(15+i*80/len(paths), fmt.Sprintf("处理项目文件 %d/%d", i+1, len(paths)))
		}
		if err = a.applyGameFile(p, plan.After[p]); err != nil {
			return folder, err
		}
	}
	if err = a.verifyActionGuards(plan.Guards); err != nil {
		return folder, err
	}
	journal.Status = "DONE"
	if err = saveJSON(filepath.Join(folder, "transaction.json"), journal); err != nil {
		return folder, err
	}
	if a.Progress != nil {
		a.Progress(100, "项目操作完成，恢复记录已保存")
	}
	return folder, nil
}

func (a *App) applyGameFile(relative string, next gameFile) error {
	path, err := safePath(a.Game, relative)
	if err != nil {
		return err
	}
	if next.Exists {
		if err = atomicWrite(path, next.Data); err != nil {
			return err
		}
	} else {
		if err = os.Remove(path); err != nil && !os.IsNotExist(err) {
			return err
		}
	}
	actual, err := readGameFile(a.Game, relative)
	if err != nil {
		return err
	}
	if actual.gameFileState != next.gameFileState {
		return errors.New("操作后文件读回校验失败")
	}
	return nil
}

func (a *App) RollbackGameAction(skipProcessCheck bool) error {
	if !skipProcessCheck {
		if err := gameStopped(); err != nil {
			return err
		}
	}
	ref, err := a.readGameAction()
	if err != nil {
		return err
	}
	if ref.Kind != "managed" {
		return errors.New("没有一键操作恢复记录")
	}
	folder, journal, err := a.loadGameJournal(ref)
	if err != nil {
		return err
	}
	if !strings.EqualFold(filepath.Clean(journal.Game), filepath.Clean(a.Game)) {
		return errors.New("恢复记录不属于当前游戏目录")
	}
	if journal.Status != "PREPARED" && journal.Status != "DONE" && journal.Status != "ROLLBACK_PREPARED" && journal.Status != "ROLLED_BACK" {
		return errors.New("恢复状态异常")
	}
	if err = a.verifyActionGuards(journal.Guards); err != nil {
		return err
	}
	paths := make([]string, 0, len(journal.Files))
	data := map[string]gameFile{}
	var backupBytes int64
	for p, row := range journal.Files {
		current, err := readGameFile(a.Game, p)
		if err != nil {
			return err
		}
		if current.gameFileState != row.Before && current.gameFileState != row.After {
			return fmt.Errorf("目标被外部修改，停止回退：%s", p)
		}
		if journal.Status == "ROLLED_BACK" && current.gameFileState != row.Before {
			return errors.New("已回退事务的目标后来发生变化，未重新覆盖")
		}
		before, err := readGameFile(filepath.Join(folder, "before"), p)
		if err != nil {
			return err
		}
		if before.gameFileState != row.Before {
			return errors.New("恢复备份缺失或哈希不符")
		}
		backupBytes += int64(len(before.Data))
		if backupBytes > 512<<20 {
			return errors.New("恢复数据超过 512 MiB 预算")
		}
		paths = append(paths, p)
		data[p] = before
	}
	if journal.Status == "ROLLED_BACK" {
		return nil
	}
	sort.Strings(paths)
	journal.Status = "ROLLBACK_PREPARED"
	if err = saveJSON(filepath.Join(folder, "transaction.json"), journal); err != nil {
		return err
	}
	if !skipProcessCheck {
		if err = gameStopped(); err != nil {
			return err
		}
	}
	for i, p := range paths {
		if a.Progress != nil {
			a.Progress(10+i*85/len(paths), fmt.Sprintf("回退项目文件 %d/%d", i+1, len(paths)))
		}
		// Backup validation may take time. Recheck each destination immediately
		// before restoring it, not just once before the whole batch.
		current, readErr := readGameFile(a.Game, p)
		if readErr != nil {
			return readErr
		}
		row := journal.Files[p]
		if current.gameFileState != row.Before && current.gameFileState != row.After {
			return fmt.Errorf("回退过程中目标被外部修改，恢复记录已保留：%s", p)
		}
		if err = a.applyGameFile(p, data[p]); err != nil {
			return err
		}
	}
	if err = a.verifyActionGuards(journal.Guards); err != nil {
		return err
	}
	journal.Status = "ROLLED_BACK"
	if err = saveJSON(filepath.Join(folder, "transaction.json"), journal); err != nil {
		return err
	}
	if a.Progress != nil {
		a.Progress(100, "最近项目操作已回退")
	}
	return nil
}

func (a *App) SaveCleanupPreview(plan *gamePlan) (string, error) {
	if plan == nil || plan.Kind != "cleanup-all" {
		return "", errors.New("清理计划异常")
	}
	var targets []string
	for p := range plan.After {
		path, err := safePath(a.Game, p)
		if err != nil {
			return "", err
		}
		targets = append(targets, path)
	}
	sort.Strings(targets)
	path, err := safePath(a.Home, "preflight/cleanup-plan.json")
	if err != nil {
		return "", err
	}
	err = saveJSON(path, map[string]any{"game": plan.Game, "action": "cleanup C and spray only; no wildcard/recursive deletion", "targets": targets, "backup_and_rollback": true, "local_imports_preserved": true})
	return path, err
}
