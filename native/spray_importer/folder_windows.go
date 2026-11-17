package main

import (
	"fmt"
	"runtime"
	"syscall"
	"unsafe"
)

type comGUID struct {
	A    uint32
	B, C uint16
	D    [8]byte
}

type comObject struct{ Table *[29]uintptr }

//go:uintptrescapes
func (o *comObject) invoke(index int, args ...uintptr) uintptr {
	result, _, _ := syscall.SyscallN(o.Table[index], append([]uintptr{uintptr(unsafe.Pointer(o))}, args...)...)
	runtime.KeepAlive(o)
	return result
}

func newFolderDialog() (*comObject, error) {
	cls := comGUID{0xdc1c5a9c, 0xe88a, 0x4dde, [8]byte{0xa5, 0xa1, 0x60, 0xf8, 0x2a, 0x20, 0xae, 0xf7}}
	iid := comGUID{0xd57c7288, 0xd4ad, 0x4768, [8]byte{0xbe, 0x02, 0x9d, 0x96, 0x95, 0x32, 0xd9, 0x60}}
	var dialog *comObject
	hr, _, _ := ole.NewProc("CoCreateInstance").Call(uintptr(unsafe.Pointer(&cls)), 0, 1,
		uintptr(unsafe.Pointer(&iid)), uintptr(unsafe.Pointer(&dialog)))
	if int32(hr) < 0 {
		return nil, fmt.Errorf("资源管理器目录窗口创建失败：0x%x", hr)
	}
	var options uint32
	if hr = dialog.invoke(10, uintptr(unsafe.Pointer(&options))); int32(hr) >= 0 {
		hr = dialog.invoke(9, uintptr(options|0x20|0x40|0x800|0x8|0x2000000))
	}
	if int32(hr) < 0 {
		dialog.invoke(2)
		return nil, fmt.Errorf("目录窗口选项设置失败：0x%x", hr)
	}
	return dialog, nil
}

func modernDirectory(owner uintptr, titles ...string) (string, error) {
	dialog, err := newFolderDialog()
	if err != nil {
		return "", err
	}
	defer dialog.invoke(2)
	text := "选择喷漆素材目录（包含子目录）"
	if len(titles) == 1 {
		text = titles[0]
	}
	title := utf(text)
	if hr := dialog.invoke(17, uintptr(unsafe.Pointer(title))); int32(hr) < 0 {
		return "", fmt.Errorf("目录窗口标题设置失败：0x%x", hr)
	}
	hr := dialog.invoke(3, owner)
	if uint32(hr) == 0x800704c7 {
		return "", nil
	}
	if int32(hr) < 0 {
		return "", fmt.Errorf("目录窗口错误：0x%x", hr)
	}
	var item *comObject
	if hr = dialog.invoke(20, uintptr(unsafe.Pointer(&item))); int32(hr) < 0 {
		return "", fmt.Errorf("读取所选目录失败：0x%x", hr)
	}
	defer item.invoke(2)
	var path *uint16
	if hr = item.invoke(5, 0x80058000, uintptr(unsafe.Pointer(&path))); int32(hr) < 0 {
		return "", fmt.Errorf("所选项目不是文件系统目录：0x%x", hr)
	}
	defer ole.NewProc("CoTaskMemFree").Call(uintptr(unsafe.Pointer(path)))
	// Windows extended-length paths are bounded by 32767 UTF-16 units.
	units := unsafe.Slice(path, 32768)
	for n, unit := range units {
		if unit == 0 {
			return syscall.UTF16ToString(units[:n]), nil
		}
	}
	return "", fmt.Errorf("所选目录路径过长")
}
