package main

import (
	"fmt"
	"image"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
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
var buttons [6]uintptr
var labels [6]uintptr
var app *App
var preview []byte
var selected = 1
var scale = 1.0
var smoke bool
var smokeReport string
var smokeError string
var smokeWorkerDone bool
var busy bool
var savedFocus uintptr

type jobResult struct {
	ID      int
	Message string
	Err     error
}

var completed = make(chan jobResult, 1)

func beginJob(id int, work func() (string, error)) {
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
func failure(err error) {
	if err == nil {
		return
	}
	setStatus("操作未完成：" + err.Error())
	call("MessageBoxW", window, uintptr(unsafe.Pointer(utf(err.Error()))), uintptr(unsafe.Pointer(utf("CSP 喷漆管理器"))), 0x10)
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
		title := fmt.Sprintf("%02d    编号测试图", n)
		if row, ok := app.State.Slots[n]; ok {
			title = fmt.Sprintf("%02d    %s", n, row.Title)
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
	call("InvalidateRect", window, 0, 1)
}

func selectionChanged() {
	result := send(slotList, 0x188, 0, 0)
	if result > 39 {
		return
	}
	selected = int(result) + 1
	img, e := app.Preview(selected)
	if e != nil {
		preview = nil
		text(labels[2], fmt.Sprintf("槽位 %02d · 预览读取失败", selected))
		call("InvalidateRect", window, 0, 1)
		setStatus(e.Error())
		return
	}
	setPreview(img)
	title := "内置编号测试图"
	if row, ok := app.State.Slots[selected]; ok {
		title = row.Title
	}
	text(labels[2], fmt.Sprintf("槽位 %02d  ·  %s", selected, title))
}

func chooseFile() (string, error) {
	buf := make([]uint16, 32768)
	filter := utf16.Encode([]rune("支持的静态图片 (*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.vtf)\x00*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.vtf\x00所有文件\x00*.*\x00\x00"))
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

func chooseDirectory() (string, error) {
	type browseInfo struct {
		Owner, Root     uintptr
		Display, Title  *uint16
		Flags           uint32
		Callback, Param uintptr
		Image           int32
	}
	display := make([]uint16, 260)
	info := browseInfo{Owner: window, Display: &display[0], Title: utf("选择喷漆图片目录（包含子目录，导入后按名称自动排序）"), Flags: 0x41}
	pidl, _, _ := shell.NewProc("SHBrowseForFolderW").Call(uintptr(unsafe.Pointer(&info)))
	if pidl == 0 {
		return "", nil
	}
	defer ole.NewProc("CoTaskMemFree").Call(pidl)
	path := make([]uint16, 32768)
	ok, _, _ := shell.NewProc("SHGetPathFromIDListEx").Call(pidl, uintptr(unsafe.Pointer(&path[0])), uintptr(len(path)), 0)
	if ok == 0 {
		return "", fmt.Errorf("所选项目不是可读取的文件系统目录")
	}
	return syscall.UTF16ToString(path), nil
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
	} else {
		call("EnableWindow", slotList, 1)
		call("EnableWindow", pathEdit, 1)
		if savedFocus != 0 && call("IsChild", window, savedFocus) != 0 {
			call("SetFocus", savedFocus)
		}
	}
}

func operation(id int) {
	if busy {
		return
	}
	if id == 103 || id == 104 {
		game := strings.Trim(strings.TrimSpace(windowText(pathEdit)), "\"")
		if !filepath.IsAbs(game) {
			failure(fmt.Errorf("请输入游戏目录的绝对路径"))
			return
		}
		app.Game = filepath.Clean(game)
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
		setStatus("正在转换图片……")
		beginJob(id, func() (string, error) {
			err := app.Import(path, number)
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
		if !confirm("导入整个目录及子目录，与已有图片合并后按名称自然排序，槽位编号可能变化。\n超过 40 张或存在损坏图片将停止整批提交，不会静默截断。\n\n这一步只导入，不部署到游戏。继续？") {
			return
		}
		setStatus("正在扫描、转换并排序目录图片……")
		beginJob(id, func() (string, error) {
			r, e := app.ImportFolder(folder)
			return fmt.Sprintf("目录导入完成：新增 %d，更新 %d，共 %d 张；略过 %d 个非图片或链接。请重新构建。", r.Imported, r.Updated, r.Total, r.Skipped), e
		})
		return
	}
	if id == 103 && !confirm("请先退出游戏。将同步更新选择器 VPK 和 80 个编号素材，并备份全部 81 个原文件。\n\n继续部署？") {
		return
	}
	if id == 104 && !confirm("请先退出游戏。恢复最近一次部署前的 81 个文件？\n外部改动会阻止回退。") {
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
			return "已恢复最近部署前的全部 81 个文件。", app.Rollback(false)
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
	for hwnd, r := range map[uintptr]placement{pathEdit: p.Path, slotList: p.List, statusLabel: p.Status} {
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
		if id == 100 && notification == 1 {
			selectionChanged()
			return 0
		}
		if id >= 101 && id <= 106 && notification == 0 {
			operation(id)
			return 0
		}
	case 0x8001:
		select {
		case result := <-completed:
			uiBusy(false)
			if smoke && result.ID == 0 {
				smokeWorkerDone = result.Err == nil
			}
			if result.Err != nil {
				failure(result.Err)
			} else {
				if result.ID == 101 || result.ID == 106 {
					if result.ID == 106 {
						selected = 1
					}
					updateList()
					selectionChanged()
				}
				setStatus(result.Message)
			}
		default:
		}
		return 0
	case 0x000f:
		var p paintStruct
		dc := call("BeginPaint", hwnd, uintptr(unsafe.Pointer(&p)))
		studioPaint(dc)
		if len(preview) > 0 {
			info := bitmapInfo{Size: 40, Width: 256, Height: -256, Planes: 1, Bits: 32}
			gdi.NewProc("StretchDIBits").Call(dc, ptrInt(px(previewArea.X)), ptrInt(px(previewArea.Y)), ptrInt(px(previewArea.W)), ptrInt(px(previewArea.H)), 0, 0, 256, 256, uintptr(unsafe.Pointer(&preview[0])), uintptr(unsafe.Pointer(&info)), 0, 0x00cc0020)
		}
		call("EndPaint", hwnd, uintptr(unsafe.Pointer(&p)))
		return 0
	case 0x0113:
		if smoke {
			if !smokeWorkerDone {
				if !busy {
					beginJob(0, func() (string, error) { return digest(embeddedVPK), nil })
				}
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
			call("DestroyWindow", hwnd)
		}
		return 0
	case 0x0002:
		call("PostQuitMessage", 0)
		return 0
	}
	return call("DefWindowProcW", hwnd, uintptr(msg), w, l)
}

func runSmoke() {
	var client rect
	call("GetClientRect", window, uintptr(unsafe.Pointer(&client)))
	good := true
	controls := append([]uintptr{slotList, pathEdit, statusLabel}, buttons[:]...)
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
	if send(slotList, 0x18b, 0, 0) != 40 || len(preview) != 256*256*4 || !smokeWorkerDone || busy {
		good = false
	}
	iconsOK := largeIcon != 0 && smallIcon != 0 && send(window, 0x7f, 1, 0) == largeIcon && send(window, 0x7f, 0, 0) == smallIcon
	if !iconsOK {
		good = false
	}
	styled := studioPaints > 0 && paintedList && len(paintedActions) == 6 && paintedListFocus
	if !styled {
		good = false
	}
	status := "PASS"
	if !good {
		status = "FAIL"
		smokeError = "native control bounds/count/preview"
	}
	if e := saveJSON(smokeReport, map[string]any{"status": status, "runtime": "native Win32 window/message loop/GDI preview", "slots": 40, "controls_fit": good, "client_width": client.Right, "client_height": client.Bottom, "python_used": false, "async_worker_completed": smokeWorkerDone, "embedded_icons_loaded": iconsOK, "studio_theme_painted": styled}); e != nil {
		smokeError = e.Error()
	}
}

func runWindow() error {
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
	window, _, _ = user.NewProc("CreateWindowExW").Call(0, uintptr(unsafe.Pointer(class.Name)), uintptr(unsafe.Pointer(utf("CSP Spray Studio 1.2.1 · Go + Win32"))), 0x02cf0000, ptrInt(x), ptrInt(y), ptrInt(width), ptrInt(height), 0, 0, instance, 0)
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
	labels[3] = widget("STATIC", "选图 → 构建 → 部署\r\n请在进入战役前选择喷漆", 0, 0)
	labels[4] = widget("STATIC", "40 SLOTS  /  原生 Windows  /  你的喷漆素材工作台", 0, 0)
	labels[5] = widget("STATIC", "素材目录", 0, 0)
	statusLabel = widget("STATIC", "就绪。未导入的槽位保留内置编号图，C 与 DLL 不变。", 0, 0)
	for i, item := range []struct {
		ID    int
		Title string
	}{{106, "整目录导入并排序…"}, {101, "单张导入到当前槽位…"}, {102, "构建部署包"}, {103, "部署到游戏"}, {104, "回退最近部署"}, {105, "打开数据目录"}} {
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
	if e == nil {
		e = runWindow()
	}
	if e != nil {
		if smoke {
			saveJSON(smokeReport, map[string]string{"status": "FAIL", "error": e.Error()})
			os.Exit(1)
		}
		call("MessageBoxW", 0, uintptr(unsafe.Pointer(utf(e.Error()))), uintptr(unsafe.Pointer(utf("CSP 启动失败"))), 0x10)
	}
}
