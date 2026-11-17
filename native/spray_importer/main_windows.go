package main

import (
	"fmt"
	"image"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"time"
	"unicode/utf16"
	"unsafe"
)

var user = syscall.NewLazyDLL("user32.dll")
var kernel = syscall.NewLazyDLL("kernel32.dll")
var gdi = syscall.NewLazyDLL("gdi32.dll")
var common = syscall.NewLazyDLL("comdlg32.dll")
var theme = syscall.NewLazyDLL("uxtheme.dll")
var shell = syscall.NewLazyDLL("shell32.dll")
var ole = syscall.NewLazyDLL("ole32.dll")

func utf(s string) *uint16 { p, _ := syscall.UTF16PtrFromString(s); return p }
func call(name string, args ...uintptr) uintptr {
	value, _, _ := user.NewProc(name).Call(args...)
	return value
}
func send(hwnd, msg, w, l uintptr) uintptr { return call("SendMessageW", hwnd, msg, w, l) }
func text(hwnd uintptr, s string)          { call("SetWindowTextW", hwnd, uintptr(unsafe.Pointer(utf(s)))) }
func windowText(hwnd uintptr) string {
	n := call("GetWindowTextLengthW", hwnd) + 1
	buf := make([]uint16, n)
	call("GetWindowTextW", hwnd, uintptr(unsafe.Pointer(&buf[0])), n)
	return syscall.UTF16ToString(buf)
}

type rect struct{ Left, Top, Right, Bottom int32 }
type point struct{ X, Y int32 }
type message struct {
	Window         uintptr
	Message        uint32
	WParam, LParam uintptr
	Time           uint32
	Point          point
	Private        uint32
}
type windowClass struct {
	Size, Style                        uint32
	Proc                               uintptr
	ExtraClass, ExtraWindow            int32
	Instance, Icon, Cursor, Background uintptr
	Menu, Name                         *uint16
	IconSmall                          uintptr
}
type paintStruct struct {
	DC                 uintptr
	Erase              int32
	Area               rect
	Restore, IncUpdate int32
	Reserved           [32]byte
}
type bitmapInfo struct {
	Size                   uint32
	Width, Height          int32
	Planes, Bits           uint16
	Compression, ImageSize uint32
	Xppm, Yppm             int32
	Used, Important        uint32
}
type openFile struct {
	Size                      uint32
	Owner, Instance           uintptr
	Filter, Custom            *uint16
	CustomMax, FilterIndex    uint32
	File                      *uint16
	MaxFile                   uint32
	TitleFile                 *uint16
	MaxTitle                  uint32
	Initial, Title            *uint16
	Flags                     uint32
	FileOffset, FileExtension uint16
	DefaultExt                *uint16
	Data, Hook                uintptr
	Template                  *uint16
	Reserved                  uintptr
	Reserved2, FlagsEx        uint32
}

var window, slotList, pathEdit, statusLabel, font uintptr
var largeIcon, smallIcon uintptr
var buttons [10]uintptr
var labels [6]uintptr
var app *App
var preview []byte
var currentClip *previewClip
var currentFrame int
var previewStart time.Time
var smokeAnimationStarted, smokeAnimationTick bool
var previewFramePaints int
var selected = 1
var scale = 1.0
var smoke bool
var smokeReport string
var smokeError string
var smokeWorkerDone bool
var busy bool
var savedFocus uintptr
var importProgress, minimumEdit uintptr
var progressObserved bool
var gamePathRestored bool

type progressEvent struct {
	Percent int
	Stage   string
}

var importUpdates = make(chan progressEvent, 1)

func queueImportProgress(percent int, stage string) {
	value := progressEvent{percent, stage}
	select {
	case <-importUpdates:
	default:
	}
	select {
	case importUpdates <- value:
	default:
	}
	call("PostMessageW", window, 0x8002, 0, 0)
}

type jobResult struct {
	ID      int
	Message string
	Err     error
}

var completed = make(chan jobResult, 1)

type cleanupRequest struct {
	Plan    *gamePlan
	Preview string
}

var cleanupPrepared = make(chan cleanupRequest, 1)

func beginJob(id int, work func() (string, error)) {
	if id == 101 || id == 106 || id == 107 {
		n, err := strconv.Atoi(strings.TrimSpace(windowText(minimumEdit)))
		if err != nil {
			failure(fmt.Errorf("动画最低帧数须为 2～256 的整数"))
			return
		}
		if err = app.SetMinimumFrames(n); err != nil {
			failure(err)
			return
		}
	}
	select {
	case <-importUpdates:
	default:
	}
	send(importProgress, 0x402, 0, 0)
	uiBusy(true)
	go func() {
		result := jobResult{ID: id}
		defer func() {
			if value := recover(); value != nil {
				result.Err = fmt.Errorf("操作异常：%v；如涉及部署，请保留并使用恢复记录", value)
			}
			completed <- result
			call("PostMessageW", window, 0x8001, 0, 0)
		}()
		result.Message, result.Err = work()
	}()
}

func px(n int) int         { return int(float64(n)*scale + .5) }
func ptrInt(n int) uintptr { return uintptr(n) }

func widget(class, title string, style uint32, id int) uintptr {
	h, _, _ := user.NewProc("CreateWindowExW").Call(0, uintptr(unsafe.Pointer(utf(class))), uintptr(unsafe.Pointer(utf(title))), uintptr(style|0x50000000), 0, 0, 0, 0, window, uintptr(id), 0, 0)
	if h != 0 {
		send(h, 0x30, font, 1)
		theme.NewProc("SetWindowTheme").Call(h, uintptr(unsafe.Pointer(utf("Explorer"))), 0)
	}
	return h
}

func setStatus(s string) { text(statusLabel, s) }

func saveGamePath(showStatus bool) error {
	err := app.RememberGameDirectory(windowText(pathEdit))
	if showStatus {
		if err != nil {
			setStatus("游戏目录尚未保存：" + err.Error())
		} else {
			setStatus("游戏目录已自动保存，下次启动将恢复。")
		}
	}
	return err
}
func failure(err error) {
	if err == nil {
		return
	}
	message := err.Error()
	if app != nil {
		if logErr := recordFailure(app.Home, err); logErr != nil {
			message += "\n诊断记录写入异常：" + logErr.Error()
		}
	}
	setStatus("操作未完成：" + message)
	call("MessageBoxW", window, uintptr(unsafe.Pointer(utf(message))), uintptr(unsafe.Pointer(utf("CSP 喷漆管理器"))), 0x10)
}
func confirm(s string) bool {
	return call("MessageBoxW", window, uintptr(unsafe.Pointer(utf(s))), uintptr(unsafe.Pointer(utf("确认操作"))), 0x24) == 6
}

func updateList() {
	importedCount = len(app.State.Slots)
	if labels[5] != 0 {
		text(labels[5], fmt.Sprintf("素材目录   %02d / 40", importedCount))
	}
	send(slotList, 0x184, 0, 0)
	for n := 1; n <= 40; n++ {
		title := slotTitle(n) + "    默认"
		if _, ok := app.State.Slots[n]; ok {
			title = slotTitle(n) + "    已导入"
		}
		send(slotList, 0x180, 0, uintptr(unsafe.Pointer(utf(title))))
	}
	send(slotList, 0x186, uintptr(selected-1), 0)
}

func setPreview(img image.Image) {
	bg := previewBG(img)
	preview = make([]byte, 256*256*4)
	for y := 0; y < 256; y++ {
		for x := 0; x < 256; x++ {
			c := bg.RGBAAt(x, y)
			i := (y*256 + x) * 4
			preview[i], preview[i+1], preview[i+2], preview[i+3] = c.B, c.G, c.R, 255
		}
	}
	r := logicalRect(previewArea)
	call("InvalidateRect", window, uintptr(unsafe.Pointer(&r)), 0)
}

func selectionChanged() {
	result := send(slotList, 0x188, 0, 0)
	if result > 39 {
		return
	}
	selected = int(result) + 1
	call("KillTimer", window, 2)
	currentClip, currentFrame = nil, 0
	preview = nil
	clip, e := app.LoadPreview(selected)
	var img image.Image
	if e == nil {
		img, e = clip.Frame(0)
	}
	if e != nil {
		preview = nil
		text(labels[2], fmt.Sprintf("槽位 %02d · 预览读取失败", selected))
		call("InvalidateRect", window, 0, 1)
		setStatus(e.Error())
		return
	}
	setPreview(img)
	currentClip, previewStart = clip, time.Now()
	if clip.Info.Frames > 1 {
		call("SetTimer", window, 2, ptrInt(max(10, int(1000/clip.FPS))), 0)
		setStatus(fmt.Sprintf("动画喷漆 · %d 帧 · %.3g FPS · 预览循环播放，构建保留全部帧", clip.Info.Frames, clip.FPS))
	} else {
		setStatus(fmt.Sprintf("静态喷漆预览 · %d×%d", clip.Info.Width, clip.Info.Height))
	}
	title := slotTitle(selected) + "（默认）"
	if row, ok := app.State.Slots[selected]; ok {
		title = slotTitle(selected)
		if row.Animation != nil {
			setStatus(row.Animation.description() + "；循环预览，构建后部署")
		}
	}
	text(labels[2], fmt.Sprintf("槽位 %02d  ·  %s", selected, title))
}

func chooseFile() (string, error) {
	buf := make([]uint16, 32768)
	filter := utf16.Encode([]rune("静态图片／动画 GIF／APNG／VTF\x00*.png;*.apng;*.jpg;*.jpeg;*.gif;*.bmp;*.vtf\x00所有文件\x00*.*\x00\x00"))
	of := openFile{Owner: window, Filter: &filter[0], FilterIndex: 1, File: &buf[0], MaxFile: uint32(len(buf)), Title: utf("选择要导入的喷漆图片"), Flags: 0x80000 | 0x1000 | 0x800 | 8}
	of.Size = uint32(unsafe.Sizeof(of))
	ok, _, _ := common.NewProc("GetOpenFileNameW").Call(uintptr(unsafe.Pointer(&of)))
	if ok == 0 {
		code, _, _ := common.NewProc("CommDlgExtendedError").Call()
		if code != 0 {
			return "", fmt.Errorf("文件选择窗口错误：0x%x", code)
		}
		return "", nil
	}
	return syscall.UTF16ToString(buf), nil
}

func selectedVPKPaths(buf []uint16) ([]string, error) {
	var parts []string
	terminated := false
	for start, i := 0, 0; i < len(buf); i++ {
		if buf[i] != 0 {
			continue
		}
		if i == start {
			terminated = true
			break
		}
		parts = append(parts, syscall.UTF16ToString(buf[start:i]))
		start = i + 1
	}
	if !terminated {
		return nil, fmt.Errorf("文件选择结果已截断，请重新选择")
	}
	if len(parts) <= 1 {
		return parts, nil
	}
	if len(parts) > 3 {
		return nil, fmt.Errorf("一次最多选择两个喷漆 VPK")
	}
	paths := make([]string, 0, len(parts)-1)
	for _, name := range parts[1:] {
		if filepath.Base(name) != name || strings.ContainsAny(name, `\/:`) {
			return nil, fmt.Errorf("文件选择结果路径异常")
		}
		paths = append(paths, filepath.Join(parts[0], name))
	}
	return paths, nil
}

func chooseVPKs() ([]string, error) {
	buf := make([]uint16, 32768)
	filter := utf16.Encode([]rune("喷漆 MOD (*.vpk)\x00*.vpk\x00\x00"))
	of := openFile{Owner: window, Filter: &filter[0], FilterIndex: 1, File: &buf[0], MaxFile: uint32(len(buf)), Title: utf("选择 1～2 个喷漆 VPK（Ctrl 多选）"), Flags: 0x80000 | 0x200 | 0x1000 | 0x800 | 8}
	of.Size = uint32(unsafe.Sizeof(of))
	ok, _, _ := common.NewProc("GetOpenFileNameW").Call(uintptr(unsafe.Pointer(&of)))
	if ok == 0 {
		code, _, _ := common.NewProc("CommDlgExtendedError").Call()
		if code != 0 {
			return nil, fmt.Errorf("VPK 选择窗口错误：0x%x", code)
		}
		return nil, nil
	}
	return selectedVPKPaths(buf)
}

func chooseDirectory() (string, error) {
	return modernDirectory(window)
}

func uiBusy(value bool) {
	if value {
		savedFocus = call("GetFocus")
	}
	busy = value
	for _, h := range buttons {
		if value {
			call("EnableWindow", h, 0)
		} else {
			call("EnableWindow", h, 1)
		}
	}
	if value {
		call("EnableWindow", slotList, 0)
		call("EnableWindow", pathEdit, 0)
		call("EnableWindow", minimumEdit, 0)
	} else {
		call("EnableWindow", slotList, 1)
		call("EnableWindow", pathEdit, 1)
		call("EnableWindow", minimumEdit, 1)
		if savedFocus != 0 && call("IsChild", window, savedFocus) != 0 {
			call("SetFocus", savedFocus)
		}
	}
}

func operation(id int) {
	if busy {
		return
	}
	if id == 109 || id == 113 {
		if err := saveGamePath(true); err != nil {
			failure(err)
			return
		}
		if id == 109 {
			if !confirm("一键部署目标：" + app.Game + "\n请先退出游戏并确保已有配套 L4N。\n将自动构建当前槽位，安装／更新喷漆 VPK、80 个贴图材质、CSPSelector.dll 及选择器启用记录；无导入时安装默认槽位。C 和其他 MOD 不变。\n先备份，完成后可用‘回退最近操作’恢复。继续？") {
				return
			}
			setStatus("正在自动构建并部署喷漆选择器……")
			beginJob(id, func() (string, error) {
				tx, err := app.OneClickDeploy(false)
				if tx == "" && err == nil {
					return "当前喷漆已是目标版本，无需重复写入。", nil
				}
				return "一键部署完成；重启游戏，在进入战役前选择喷漆。恢复记录：" + filepath.Base(tx), err
			})
		} else {
			setStatus("正在检查游戏内 C 与喷漆组件，尚未删除文件……")
			beginJob(id, func() (string, error) {
				plan, err := app.PlanProjectCleanup(false)
				if err != nil {
					return "", err
				}
				preview, err := app.SaveCleanupPreview(plan)
				if err != nil {
					return "", err
				}
				cleanupPrepared <- cleanupRequest{plan, preview}
				return "清理预检完成", nil
			})
		}
		return
	}
	if id == 108 {
		if !confirm("恢复全部 40 个槽位为默认编号喷漆？\n将清空当前导入绑定，保留原始文件、历史母版及清单备份，方便重新导入。\n这一步不直接修改游戏；如需恢复游戏内喷漆，请随后构建并退出游戏后部署。") {
			return
		}
		setStatus("正在备份清单并恢复全部默认槽位……")
		beginJob(id, func() (string, error) {
			folder, err := app.ResetDefaults()
			if err != nil {
				return "", err
			}
			if folder == "" {
				return "全部槽位已是默认状态；可直接导入新素材，或构建默认包后部署。", nil
			}
			return "已恢复全部 40 个默认槽位；可重新导入。需恢复游戏内效果请构建后部署。清单备份：" + filepath.Base(folder), nil
		})
		return
	}
	if id == 107 {
		paths, e := chooseVPKs()
		if e != nil {
			failure(e)
			return
		}
		if len(paths) == 0 || !confirm("将自动拆解所选 VPK 的静态／动画喷漆，与已有素材合并并重新编号 01～40。\n动画 VTF 保留全部帧与 mip，支持循环预览；原始 VPK 保持不变。\n坏包、坏图或超出 40 槽时整批停止。导入后请重新构建，再退出游戏后部署。继续？") {
			return
		}
		setStatus("正在拆解喷漆 VPK、转换并重新编号……")
		beginJob(id, func() (string, error) {
			r, err := app.ImportVPKs(paths)
			return fmt.Sprintf("VPK 导入完成：新增 %d，更新 %d，共 %d 张，已重新编号。请重新构建。", r.Imported, r.Updated, r.Total), err
		})
		return
	}
	if id == 103 || id == 104 {
		if err := saveGamePath(true); err != nil {
			failure(err)
			return
		}
	}
	if id == 101 {
		path, e := chooseFile()
		if e != nil {
			failure(e)
			return
		}
		if path == "" {
			return
		}
		number := selected
		setStatus("正在导入静态／动画喷漆素材……")
		beginJob(id, func() (string, error) {
			err := app.Import(path, number)
			if err == nil {
				row := app.State.Slots[number]
				if row.Animation != nil {
					return row.Animation.description() + "。已导入，请构建后部署。", nil
				}
				if row.VTF != nil && row.VTF.Frames > 1 {
					return fmt.Sprintf("动画喷漆已导入槽位 %02d：%d 帧，%.3g FPS；支持循环预览。请构建后部署。", number, row.VTF.Frames, animationFPS(row.FrameRate)), nil
				}
			}
			return fmt.Sprintf("槽位 %02d 已导入。请构建，再退出游戏后部署。", number), err
		})
		return
	}
	if id == 106 {
		folder, e := chooseDirectory()
		if e != nil {
			failure(e)
			return
		}
		if folder == "" {
			return
		}
		if !confirm("导入整个目录及子目录中的静态图片、动画 GIF／APNG／VTF，与已有素材合并后自然排序，槽位编号可能变化。\n图片保存 1024 母版，静态导出接近 1024，GIF／APNG 动画导出 512，最多保留连续前 3 帧；DXT1 使用 1 位透明。原始 VTF 原样保留。\n超过 40 张或存在损坏素材将停止整批提交。继续？") {
			return
		}
		setStatus("正在扫描、转换并排序目录图片……")
		beginJob(id, func() (string, error) {
			r, e := app.ImportFolder(folder)
			message := fmt.Sprintf("目录导入完成：新增 %d，更新 %d，共 %d 张；略过 %d 个非图片或链接。请重新构建。", r.Imported, r.Updated, r.Total, r.Skipped)
			if len(r.Notices) > 0 {
				message += "\n" + strings.Join(r.Notices[:min(3, len(r.Notices))], "\n")
				if len(r.Notices) > 3 {
					message += fmt.Sprintf("\n另 %d 项参数请点击对应槽位查看。", len(r.Notices)-3)
				}
			}
			return message, e
		})
		return
	}
	if id == 103 && !confirm("请先退出游戏。将同步更新选择器 VPK 和 80 个编号素材，并备份全部 81 个原文件。\n\n继续部署？") {
		return
	}
	if id == 104 && !confirm("请先退出游戏。回退最近一次部署或项目清理？\n新安装的项目文件会移除，原有文件从备份恢复；外部改动会阻止回退。工具本地槽位不清空。") {
		return
	}
	switch id {
	case 102:
		setStatus("正在构建并校验 VPK 与 MOD 素材……")
		beginJob(id, func() (string, error) {
			folder, e := app.Build()
			return "构建完成：" + filepath.Base(folder) + "。现在可以部署。", e
		})
	case 103:
		setStatus("正在备份、部署并逐文件校验……")
		beginJob(id, func() (string, error) {
			tx, e := app.Deploy(false)
			return "部署完成。重启游戏，在进入战役前选择对应编号。备份：" + filepath.Base(tx), e
		})
	case 104:
		setStatus("正在核对备份并恢复……")
		beginJob(id, func() (string, error) {
			return "已恢复最近一次游戏部署或项目清理前的状态；本地槽位未清空。", app.Rollback(false)
		})
	case 105:
		if e := os.MkdirAll(app.Home, 0755); e != nil {
			failure(e)
			return
		}
		result, _, _ := syscall.NewLazyDLL("shell32.dll").NewProc("ShellExecuteW").Call(window, uintptr(unsafe.Pointer(utf("open"))), uintptr(unsafe.Pointer(utf(app.Home))), 0, 0, 1)
		if result <= 32 {
			failure(fmt.Errorf("数据目录已创建，但资源管理器打开失败：%d", result))
		}
	}
}

func place(h uintptr, x, y, w, hgt int) {
	call("MoveWindow", h, ptrInt(px(x)), ptrInt(px(y)), ptrInt(px(w)), ptrInt(px(hgt)), 1)
}
func layout() {
	var r rect
	call("GetClientRect", window, uintptr(unsafe.Pointer(&r)))
	w, h := int(float64(r.Right)/scale), int(float64(r.Bottom)/scale)
	p := studioGeometry(w, h)
	for i, r := range p.Labels {
		place(labels[i], r.X, r.Y, r.W, r.H)
	}
	for i, r := range p.Buttons {
		place(buttons[i], r.X, r.Y, r.W, r.H)
	}
	for hwnd, r := range map[uintptr]placement{pathEdit: p.Path, slotList: p.List, statusLabel: p.Status, importProgress: p.Progress, minimumEdit: p.Minimum} {
		place(hwnd, r.X, r.Y, r.W, r.H)
	}
	previewArea = p.Preview
	call("InvalidateRect", window, 0, 1)
}

func wndProc(hwnd uintptr, msg uint32, w, l uintptr) uintptr {
	switch msg {
	case 0x0005:
		if w == 1 {
			return 0
		}
		if slotList != 0 {
			layout()
		}
		return 0
	case 0x0014:
		return 1
	case 0x0133:
		return studioControlColour(w, l, true)
	case 0x0138, 0x0134:
		return studioControlColour(w, l, false)
	case 0x002b:
		if studioDraw((*drawItem)(unsafe.Pointer(l))) {
			return 1
		}
	case 0x0024:
		// MINMAXINFO: reserved point, max size/pos, minimum tracking, maximum tracking.
		points := (*[5]point)(unsafe.Pointer(l))
		points[3] = point{int32(px(920)), int32(px(650))}
		return 0
	case 0x0111:
		if busy {
			return 0
		}
		id, notification := int(w&0xffff), int(w>>16)
		if id == 110 && pathEdit != 0 {
			if notification == 0x300 {
				call("SetTimer", window, 3, 800, 0)
			}
			if notification == 0x200 {
				call("KillTimer", window, 3)
				saveGamePath(true)
			}
			return 0
		}
		if id == 100 && notification == 1 {
			selectionChanged()
			return 0
		}
		if ((id >= 101 && id <= 109) || id == 113) && notification == 0 {
			operation(id)
			return 0
		}
	case 0x8002:
		select {
		case value := <-importUpdates:
			if busy {
				send(importProgress, 0x402, uintptr(value.Percent), 0)
				setStatus(fmt.Sprintf("%d%% · %s", value.Percent, value.Stage))
				if smoke && value.Percent == 50 && send(importProgress, 0x408, 0, 0) == 50 {
					progressObserved = true
				}
			}
		default:
		}
		return 0
	case 0x8001:
		select {
		case result := <-completed:
			uiBusy(false)
			if result.Err == nil {
				send(importProgress, 0x402, 100, 0)
			} else {
				send(importProgress, 0x402, 0, 0)
			}
			if smoke && result.ID == 0 {
				smokeWorkerDone = result.Err == nil
			}
			if result.Err != nil {
				failure(result.Err)
			} else {
				if result.ID == 113 {
					select {
					case request := <-cleanupPrepared:
						if len(request.Plan.After) == 0 {
							setStatus("游戏目录中没有待清理的项目组件，未删除文件。")
							return 0
						}
						question := fmt.Sprintf("清理目标：%s\n将处理 %d 个项目目标，范围仅限：\nC 的 VPK 与 CSessionDefaults.dll；喷漆选择器 VPK、CSPSelector.dll、40 份 VTF 和 40 份 VMT、诊断编号 VPK，以及这些项目在 addonlist.txt 中的条目。\n不删除 L4N、其他 MOD、游戏原生文件、config.cfg、工具数据或原图。\n完整绝对路径清单：%s\n先备份再清理，可用‘回退最近操作’恢复。确认执行？", request.Plan.Game, len(request.Plan.After), request.Preview)
						if !confirm(question) {
							setStatus("已取消清理；游戏文件未更改。")
							return 0
						}
						beginJob(114, func() (string, error) {
							tx, err := app.ApplyGamePlan(request.Plan, false)
							return "游戏内 C 与喷漆项目组件已清理；L4N、其他 MOD 和工具本地素材已保留。恢复记录：" + filepath.Base(tx), err
						})
						return 0
					default:
					}
				}
				if result.ID == 101 || result.ID == 106 || result.ID == 107 || result.ID == 108 || result.ID == 109 {
					if result.ID == 106 || result.ID == 107 || result.ID == 108 {
						selected = 1
					}
					updateList()
					selectionChanged()
				}
				if app.MaintenanceWarning != "" {
					result.Message += "；" + app.MaintenanceWarning
				}
				setStatus(result.Message)
				if (result.ID == 101 || result.ID == 106) && (strings.Contains(result.Message, "DXT1") || strings.Contains(result.Message, "APNG")) {
					call("MessageBoxW", window, uintptr(unsafe.Pointer(utf(result.Message))), uintptr(unsafe.Pointer(utf("高清导入结果"))), 0x40)
				}
			}
		default:
		}
		return 0
	case 0x000f:
		var p paintStruct
		dc := call("BeginPaint", hwnd, uintptr(unsafe.Pointer(&p)))
		r := logicalRect(previewArea)
		// An animation frame replaces every pixel in its rectangle. Do not
		// clear/repaint the scene underneath it between two frame blits.
		if len(preview) == 0 || p.Area.Left < r.Left || p.Area.Top < r.Top || p.Area.Right > r.Right || p.Area.Bottom > r.Bottom {
			studioPaint(dc)
		} else {
			previewFramePaints++
		}
		if len(preview) > 0 {
			info := bitmapInfo{Size: 40, Width: 256, Height: -256, Planes: 1, Bits: 32}
			gdi.NewProc("StretchDIBits").Call(dc, ptrInt(px(previewArea.X)), ptrInt(px(previewArea.Y)), ptrInt(px(previewArea.W)), ptrInt(px(previewArea.H)), 0, 0, 256, 256, uintptr(unsafe.Pointer(&preview[0])), uintptr(unsafe.Pointer(&info)), 0, 0x00cc0020)
		}
		call("EndPaint", hwnd, uintptr(unsafe.Pointer(&p)))
		return 0
	case 0x0113:
		if w == 3 {
			call("KillTimer", hwnd, 3)
			if !busy {
				saveGamePath(true)
			}
			return 0
		}
		if w == 2 {
			if !busy && currentClip != nil && currentClip.Info.Frames > 1 {
				frame := int(time.Since(previewStart).Seconds()*currentClip.FPS) % currentClip.Info.Frames
				if frame != currentFrame {
					img, err := currentClip.Frame(frame)
					if err != nil {
						call("KillTimer", hwnd, 2)
						preview, currentClip = nil, nil
						call("InvalidateRect", hwnd, 0, 1)
						setStatus(err.Error())
					} else {
						currentFrame = frame
						setPreview(img)
						if smoke {
							smokeAnimationTick = true
						}
					}
				}
			}
			return 0
		}
		if smoke {
			if !smokeWorkerDone {
				if !busy {
					game := filepath.Join(filepath.Dir(smokeReport), "game-path-fixture")
					err := atomicWrite(filepath.Join(game, "left4dead2.exe"), []byte("fixture, never executed"))
					if err == nil {
						err = atomicWrite(filepath.Join(game, "left4dead2/gameinfo.txt"), []byte("fixture metadata"))
					}
					if err != nil {
						smokeError = err.Error()
						call("DestroyWindow", hwnd)
						return 0
					}
					text(pathEdit, game)
					send(window, 0x111, 110|(0x200<<16), pathEdit)
					reopened, err := newApp(app.Home, defaultGame)
					gamePathRestored = err == nil && reopened.Game == game && reopened.Settings.MinimumAnimationFrames == app.Settings.MinimumAnimationFrames
					beginJob(0, func() (string, error) { app.Progress(50, "进度控件测试"); return digest(embeddedVPK), nil })
				}
				return 0
			}
			if !smokeAnimationStarted {
				raw := make([]byte, 88)
				copy(raw, "VTF\x00")
				le.PutUint32(raw[4:], 7)
				le.PutUint32(raw[8:], 2)
				le.PutUint32(raw[12:], 80)
				le.PutUint16(raw[16:], 1)
				le.PutUint16(raw[18:], 1)
				le.PutUint16(raw[24:], 2)
				raw[56] = 1
				le.PutUint32(raw[57:], 0xffffffff)
				le.PutUint16(raw[63:], 1)
				copy(raw[80:], []byte{255, 0, 0, 255, 0, 255, 0, 255})
				info, err := inspectVTF(raw)
				if err != nil {
					smokeError = err.Error()
					call("DestroyWindow", hwnd)
					return 0
				}
				currentClip = &previewClip{Raw: raw, Info: info, FPS: 10}
				currentFrame, previewStart = 0, time.Now()
				smokeAnimationStarted = true
				call("SetTimer", hwnd, 2, 50, 0)
				return 0
			}
			if !smokeAnimationTick {
				return 0
			}
			call("KillTimer", hwnd, 1)
			send(window, 0x127, 0x10002, 0)
			call("SetFocus", slotList)
			call("RedrawWindow", window, 0, 0, 0x181)
			runSmoke()
			call("DestroyWindow", hwnd)
			return 0
		}
	case 0x0010:
		if !busy {
			if err := saveGamePath(true); err != nil && strings.Trim(strings.TrimSpace(windowText(pathEdit)), "\"") != app.Game {
				if !confirm("游戏目录未保存：" + err.Error() + "\n仍要关闭吗？下次将使用上次保存的目录。") {
					return 0
				}
			}
			call("DestroyWindow", hwnd)
		}
		return 0
	case 0x0002:
		call("KillTimer", hwnd, 2)
		call("KillTimer", hwnd, 3)
		call("PostQuitMessage", 0)
		return 0
	}
	return call("DefWindowProcW", hwnd, uintptr(msg), w, l)
}

func runSmoke() {
	var client rect
	call("GetClientRect", window, uintptr(unsafe.Pointer(&client)))
	good := true
	controls := append([]uintptr{slotList, pathEdit, statusLabel, importProgress, minimumEdit}, buttons[:]...)
	controls = append(controls, labels[:]...)
	for _, h := range controls {
		var r rect
		call("GetWindowRect", h, uintptr(unsafe.Pointer(&r)))
		a, b := point{r.Left, r.Top}, point{r.Right, r.Bottom}
		call("ScreenToClient", window, uintptr(unsafe.Pointer(&a)))
		call("ScreenToClient", window, uintptr(unsafe.Pointer(&b)))
		if h == 0 || a.X < 0 || a.Y < 0 || b.X > client.Right || b.Y > client.Bottom {
			good = false
		}
	}
	if send(slotList, 0x18b, 0, 0) != 40 || len(preview) != 256*256*4 || !smokeWorkerDone || !smokeAnimationTick || previewFramePaints == 0 || busy {
		good = false
	}
	iconsOK := largeIcon != 0 && smallIcon != 0 && send(window, 0x7f, 1, 0) == largeIcon && send(window, 0x7f, 0, 0) == smallIcon
	resetPresent := call("GetDlgItem", window, 108) == buttons[7] && buttons[7] != 0
	if !iconsOK || !resetPresent || call("GetDlgItem", window, 109) != buttons[8] || call("GetDlgItem", window, 113) != buttons[9] || buttons[8] == 0 || buttons[9] == 0 || !progressObserved || !gamePathRestored || windowText(minimumEdit) != strconv.Itoa(app.Settings.MinimumAnimationFrames) {
		good = false
	}
	styled := studioPaints > 0 && paintedList && len(paintedActions) == len(buttons) && paintedListFocus
	if !styled {
		good = false
	}
	status := "PASS"
	if !good {
		status = "FAIL"
		smokeError = "native control bounds/count/preview"
	}
	if e := saveJSON(smokeReport, map[string]any{"status": status, "runtime": "native Win32 window/message loop/GDI preview", "slots": 40, "action_buttons": len(buttons), "reset_button_present": resetPresent, "progress_control_observed": progressObserved, "game_path_saved_and_restored": gamePathRestored, "minimum_frames": app.Settings.MinimumAnimationFrames, "controls_fit": good, "client_width": client.Right, "client_height": client.Bottom, "python_used": false, "async_worker_completed": smokeWorkerDone, "embedded_icons_loaded": iconsOK, "studio_theme_painted": styled, "animation_timer_completed": smokeAnimationTick, "preview_only_paints": previewFramePaints}); e != nil {
		smokeError = e.Error()
	}
}

func runWindow() error {
	syscall.NewLazyDLL("comctl32.dll").NewProc("InitCommonControls").Call()
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	com, _, _ := ole.NewProc("CoInitializeEx").Call(0, 2)
	if int32(com) < 0 {
		return fmt.Errorf("目录选择器 COM 初始化失败：0x%x", com)
	}
	defer ole.NewProc("CoUninitialize").Call()
	user.NewProc("SetProcessDPIAware").Call()
	dc := call("GetDC", 0)
	dpi, _, _ := gdi.NewProc("GetDeviceCaps").Call(dc, 88)
	call("ReleaseDC", 0, dc)
	if dpi > 0 {
		scale = float64(dpi) / 96
	}
	hfont, _, _ := gdi.NewProc("CreateFontW").Call(uintptr(int64(-px(16))), 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 5, 0, uintptr(unsafe.Pointer(utf("Microsoft YaHei UI"))))
	font = hfont
	defer gdi.NewProc("DeleteObject").Call(font)
	closeStudio := initStudio()
	defer closeStudio()
	instance, _, _ := kernel.NewProc("GetModuleHandleW").Call(0)
	largeIcon = call("LoadImageW", instance, 101, 1, ptrInt(px(32)), ptrInt(px(32)), 0x8000)
	smallIcon = call("LoadImageW", instance, 101, 1, ptrInt(px(16)), ptrInt(px(16)), 0x8000)
	if largeIcon == 0 || smallIcon == 0 {
		return fmt.Errorf("内置图标资源 101 缺失，请使用带图标资源的正式构建")
	}
	cursor := call("LoadCursorW", 0, 32512)
	class := windowClass{Size: uint32(unsafe.Sizeof(windowClass{})), Style: 3, Proc: syscall.NewCallback(wndProc), Instance: instance, Cursor: cursor, Name: utf("CSPSprayManagerWin32"), Icon: largeIcon, IconSmall: smallIcon}
	if call("RegisterClassExW", uintptr(unsafe.Pointer(&class))) == 0 {
		return fmt.Errorf("Win32 窗口类注册失败")
	}
	var work rect
	call("SystemParametersInfoW", 0x30, 0, uintptr(unsafe.Pointer(&work)), 0)
	width, height := px(980), px(700)
	x, y := 100, 80
	if work.Right > work.Left && work.Bottom > work.Top {
		width = min(width, int(work.Right-work.Left))
		height = min(height, int(work.Bottom-work.Top))
		x = int(work.Left) + (int(work.Right-work.Left)-width)/2
		y = int(work.Top) + (int(work.Bottom-work.Top)-height)/2
	}
	window, _, _ = user.NewProc("CreateWindowExW").Call(0, uintptr(unsafe.Pointer(class.Name)), uintptr(unsafe.Pointer(utf("CSP Spray Studio 1.12.0 · Go + Win32"))), 0x02cf0000, ptrInt(x), ptrInt(y), ptrInt(width), ptrInt(height), 0, 0, instance, 0)
	if window == 0 {
		return fmt.Errorf("Win32 窗口创建失败")
	}
	send(window, 0x80, 1, largeIcon)
	send(window, 0x80, 0, smallIcon)
	darkTitlebar()
	labels[0] = widget("STATIC", "SPRAY STUDIO", 0, 0)
	labels[1] = widget("STATIC", "游戏安装目录", 0, 0)
	pathEdit = widget("EDIT", app.Game, 0x00010080, 110)
	slotList = widget("LISTBOX", "", 0x00210151, 100)
	send(slotList, 0x1a0, 0, ptrInt(px(40)))
	labels[2] = widget("STATIC", "", 0, 0)
	labels[3] = widget("STATIC", "动画最低帧数（2～256）", 0, 0)
	minimumEdit = widget("EDIT", strconv.Itoa(app.Settings.MinimumAnimationFrames), 0x00012080, 111)
	send(minimumEdit, 0xc5, 3, 0)
	importProgress = widget("msctls_progress32", "", 1, 112)
	send(importProgress, 0x406, 0, 100)
	app.Progress = queueImportProgress
	if minimumEdit == 0 || importProgress == 0 {
		return fmt.Errorf("导入设置或进度控件创建失败")
	}
	labels[4] = widget("STATIC", "40 SLOTS  /  GIF · APNG · VTF 动画  /  等比例循环预览", 0, 0)
	labels[5] = widget("STATIC", "素材目录", 0, 0)
	statusLabel = widget("STATIC", "就绪。未导入的槽位保留内置编号图，C 与 DLL 不变。", 0, 0)
	for i, item := range []struct {
		ID    int
		Title string
	}{{107, "导入 VPK（最多2个）…"}, {106, "整目录导入并排序…"}, {101, "单张导入到当前槽位…"}, {102, "构建部署包"}, {103, "部署到游戏（已有选择器）"}, {104, "回退最近操作"}, {105, "打开数据目录"}, {108, "恢复全部默认槽位…"}, {109, "一键部署到游戏…"}, {113, "清理游戏内本项目产物…"}} {
		buttons[i] = widget("BUTTON", item.Title, 0x0001000b, item.ID)
	}
	send(labels[0], 0x30, titleFont, 1)
	for _, h := range []uintptr{labels[2], labels[5]} {
		send(h, 0x30, captionFont, 1)
	}
	for _, h := range []uintptr{labels[1], labels[3], labels[4], statusLabel} {
		send(h, 0x30, smallFont, 1)
	}
	updateList()
	selectionChanged()
	layout()
	if !smoke {
		call("SetTimer", window, 3, 800, 0)
	}
	call("ShowWindow", window, 1)
	call("UpdateWindow", window)
	if smoke {
		call("SetTimer", window, 1, 700, 0)
	}
	var m message
	for {
		r, _, _ := user.NewProc("GetMessageW").Call(uintptr(unsafe.Pointer(&m)), 0, 0, 0)
		if int32(r) == -1 {
			return fmt.Errorf("Win32 消息循环异常")
		}
		if r == 0 {
			break
		}
		if call("IsDialogMessageW", window, uintptr(unsafe.Pointer(&m))) == 0 {
			call("TranslateMessage", uintptr(unsafe.Pointer(&m)))
			call("DispatchMessageW", uintptr(unsafe.Pointer(&m)))
		}
	}
	if smokeError != "" {
		return fmt.Errorf("%s", smokeError)
	}
	return nil
}

func main() {
	if len(os.Args) == 4 && os.Args[1] == "--verify-icon" {
		exe, err := os.Executable()
		var raw, ico []byte
		if err == nil {
			raw, err = os.ReadFile(exe)
		}
		if err == nil {
			ico, err = os.ReadFile(os.Args[2])
		}
		if err == nil {
			err = verifyEmbeddedIcon(raw, ico)
		}
		r := map[string]any{"status": "PASS", "exe_sha256": digest(raw), "ico_sha256": digest(ico), "sizes": iconSizes}
		if err != nil {
			r["status"] = "FAIL"
			r["error"] = err.Error()
		}
		if saveJSON(os.Args[3], r) != nil {
			os.Exit(1)
		}
		if err != nil {
			os.Exit(1)
		}
		return
	}
	if len(os.Args) == 3 && os.Args[1] == "--studio-preview" {
		if renderStudioPreview(os.Args[2]) != nil {
			os.Exit(1)
		}
		return
	}
	if len(os.Args) == 5 && os.Args[1] == "--make-icon" {
		img, err := loadImage(os.Args[2])
		var raw []byte
		if err == nil {
			raw, err = makeIcon(img)
		}
		if err == nil {
			err = atomicWrite(os.Args[3], raw)
		}
		report := map[string]any{"status": "PASS", "sizes": iconSizes, "ico_sha256": digest(raw)}
		if err != nil {
			report["status"] = "FAIL"
			report["error"] = err.Error()
		}
		if e := saveJSON(os.Args[4], report); e != nil {
			os.Exit(1)
		}
		if err != nil {
			os.Exit(1)
		}
		return
	}
	exe, e := os.Executable()
	if e != nil {
		return
	}
	home := filepath.Join(filepath.Dir(exe), "CSP_Spray_Data")
	mutex, _, lockError := kernel.NewProc("CreateMutexW").Call(0, 0,
		uintptr(unsafe.Pointer(utf(`Local\CSPSprayManager_`+digest([]byte(strings.ToLower(home)))[:16]))))
	if mutex == 0 || lockError == syscall.ERROR_ALREADY_EXISTS {
		if mutex != 0 {
			syscall.CloseHandle(syscall.Handle(mutex))
		}
		call("MessageBoxW", 0, uintptr(unsafe.Pointer(utf("该数据目录的喷漆管理器已经打开，或未能取得独占锁。"))),
			uintptr(unsafe.Pointer(utf("CSP 喷漆管理器"))), 0x30)
		return
	}
	defer syscall.CloseHandle(syscall.Handle(mutex))
	for i, arg := range os.Args[1:] {
		if arg == "--smoke" {
			smoke = true
			if i+2 < len(os.Args) {
				smokeReport = os.Args[i+2]
			}
		}
	}
	if smokeReport == "" {
		smokeReport = filepath.Join(filepath.Dir(exe), "win32-smoke.json")
	}
	app, e = newApp(home, defaultGame)
	if len(os.Args) == 3 && os.Args[1] == "--prune-backups" {
		if e == nil {
			e = app.PruneBackups()
		}
		result := map[string]any{"status": "PASS", "picture_decoding": false, "home": home}
		if e != nil {
			result["status"], result["error"] = "FAIL", e.Error()
		}
		if err := saveJSON(os.Args[2], result); err != nil || e != nil {
			os.Exit(1)
		}
		return
	}
	if e == nil && len(os.Args) == 2 && os.Args[1] == "--portable-install" {
		e = app.runPortableInstall(filepath.Join(filepath.Dir(exe), "..", "game"))
	} else if e == nil {
		if err := app.PruneBackups(); err != nil {
			app.MaintenanceWarning = "旧备份保留，清理待重试：" + err.Error()
		}
		e = runWindow()
	}
	if e != nil {
		if smoke {
			saveJSON(smokeReport, map[string]string{"status": "FAIL", "error": e.Error()})
			os.Exit(1)
		}
		call("MessageBoxW", 0, uintptr(unsafe.Pointer(utf(e.Error()))), uintptr(unsafe.Pointer(utf("CSP 启动失败"))), 0x10)
		if len(os.Args) == 2 && os.Args[1] == "--portable-install" {
			os.Exit(1)
		}
	}
}
