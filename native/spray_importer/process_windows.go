package main

import (
	"errors"
	"strings"
	"syscall"
	"unsafe"
)

func gameStopped() error {
	kernel := syscall.NewLazyDLL("kernel32.dll")
	snapshot, _, err := kernel.NewProc("CreateToolhelp32Snapshot").Call(2, 0)
	if snapshot == ^uintptr(0) {
		return err
	}
	defer syscall.CloseHandle(syscall.Handle(snapshot))
	type processEntry struct {
		Size, Usage, PID        uint32
		Heap                    uintptr
		Module, Threads, Parent uint32
		Priority                int32
		Flags                   uint32
		Name                    [260]uint16
	}
	var entry processEntry
	entry.Size = uint32(unsafe.Sizeof(entry))
	first := kernel.NewProc("Process32FirstW")
	next := kernel.NewProc("Process32NextW")
	ok, _, e := first.Call(snapshot, uintptr(unsafe.Pointer(&entry)))
	if ok == 0 {
		return e
	}
	for ok != 0 {
		if strings.EqualFold(syscall.UTF16ToString(entry.Name[:]), "left4dead2.exe") {
			return errors.New("请先退出求生之路 2，再部署或回退；工具不会结束游戏")
		}
		ok, _, e = next.Call(snapshot, uintptr(unsafe.Pointer(&entry)))
	}
	if e != syscall.ERROR_NO_MORE_FILES {
		return e
	}
	return nil
}
