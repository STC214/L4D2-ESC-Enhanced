package main

import (
	"bytes"
	"errors"
	"fmt"
	"path/filepath"
	"runtime"
	"strings"
	"unsafe"
)

const portableCVPKHash = "8a4f8578a1385e6238de779f42921d25d8df97556d16e245cdc74da6586bb476"
const portableCDLLHash = "d20fdaf5faefc335ac470e5a1416f4b53b4a8bf7f898c26472dad4b04724cef2"
const portableBaseHash = "27cd1dbfdba0e9fbdb02c0340a3fc6fe89298315a1a6edc0020248868f37ec70"

// The portable payload is the published numbered baseline, never the current
// game's VPK or the user's catalog. Validate every installed byte before writes.
func (a *App) PlanPortableInstall(payload string, skipProcessCheck bool) (*gamePlan, error) {
	if err := a.checkPending(); err != nil {
		return nil, err
	}
	if !skipProcessCheck {
		if err := gameStopped(); err != nil {
			return nil, err
		}
	}
	if err := a.validateActionGame(true); err != nil {
		return nil, err
	}
	if digest(embeddedVPK) != portableBaseHash || digest(embeddedSelectorDLL) != selectorDLLHash {
		return nil, errors.New("内置数字底板或选择器 DLL 校验失败")
	}
	packed, err := readVPK(embeddedVPK)
	if err != nil {
		return nil, err
	}
	after := map[string]gameFile{}
	for _, p := range expectedPaths() {
		data := embeddedVPK
		if strings.HasPrefix(p, "update/") {
			data = packed[strings.TrimPrefix(p, "update/")]
		}
		f, err := readGameFile(payload, p)
		if err != nil {
			return nil, err
		}
		if !f.Exists || len(data) == 0 || !bytes.Equal(f.Data, data) {
			return nil, fmt.Errorf("便携包不是原始数字喷漆底板：%s", p)
		}
		after[p] = f
	}
	for p, pin := range map[string]string{
		selectorDLLPath:                         selectorDLLHash,
		"left4dead2/addons/" + cProjectVPK:      portableCVPKHash,
		"bin/neko/plugins/CSessionDefaults.dll": portableCDLLHash,
	} {
		f, err := readGameFile(payload, p)
		if err != nil {
			return nil, err
		}
		if !f.Exists || f.Hash != pin {
			return nil, fmt.Errorf("便携包 C／选择器组件哈希异常：%s", p)
		}
		after[p] = f
	}
	addon, err := readGameFile(a.Game, addonListPath)
	if err != nil {
		return nil, err
	}
	if !addon.Exists {
		addon = actionFile([]byte("\"AddonList\"\n{\n}\n"))
	}
	patched, err := patchProjectAddons(addon.Data, false, true)
	if err != nil {
		return nil, err
	}
	after[addonListPath] = actionFile(patched)
	return a.newGamePlan("install-bundle", after)
}

func portableMessage(text string, flags uintptr) uintptr {
	return call("MessageBoxW", 0, uintptr(unsafe.Pointer(utf(text))), uintptr(unsafe.Pointer(utf("C＋数字喷漆便携部署"))), flags)
}

func (a *App) runPortableInstall(payload string) error {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	hr, _, _ := ole.NewProc("CoInitializeEx").Call(0, 2)
	if int32(hr) < 0 {
		return errors.New("游戏目录选择器初始化失败")
	}
	defer ole.NewProc("CoUninitialize").Call()
	game := a.Settings.GameDirectory
	if game == "" || a.validateActionGame(true) != nil || portableMessage("使用上次保存的游戏目录？\n"+game+"\n选择“否”可更换目录。", 0x24) != 6 {
		var err error
		game, err = modernDirectory(0, "选择包含 left4dead2.exe 的游戏根目录")
		if err != nil || game == "" {
			return err
		}
	}
	if err := a.SetGameDirectory(game); err != nil {
		return err
	}
	plan, err := a.PlanPortableInstall(payload, false)
	if err != nil {
		return err
	}
	if len(plan.After) == 0 {
		portableMessage("C 和原始数字喷漆已全部安装，无需更新。", 0x40)
		return nil
	}
	text := fmt.Sprintf("游戏目录：%s\n将更新 %d 个文件／配置。\n\n安装 C＋原始 40 槽数字喷漆，覆盖当前游戏中的同名组件（包括自定义喷漆）。不会修改工具内个人槽位。\n已有 L4N 为前提，不安装 L4N 或地图。\n先备份后写入；失败或需撤销时，在喷漆工具点击“回退最近操作”。\n\n确认部署？", a.Game, len(plan.After))
	if portableMessage(text, 0x124) != 6 {
		return nil
	}
	folder, err := a.ApplyGamePlan(plan, false)
	if err != nil {
		return fmt.Errorf("%w\n恢复记录：%s\n请在喷漆工具中回退最近操作。", err, folder)
	}
	portableMessage("部署完成。请在进入战役前选择喷漆。\n恢复记录："+folder+"\n工具数据："+filepath.Clean(a.Home), 0x40)
	return nil
}
