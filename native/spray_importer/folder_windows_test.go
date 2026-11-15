package main

import (
	"image"
	"runtime"
	"testing"
	"unsafe"
)

func TestExplorerFolderDialogNativeOptions(t *testing.T) {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	hr, _, _ := ole.NewProc("CoInitializeEx").Call(0, 2)
	if int32(hr) < 0 {
		t.Fatalf("COM 0x%x", hr)
	}
	defer ole.NewProc("CoUninitialize").Call()
	dialog, err := newFolderDialog()
	must(t, err)
	defer dialog.invoke(2)
	var options uint32
	if hr := dialog.invoke(10, uintptr(unsafe.Pointer(&options))); int32(hr) < 0 {
		t.Fatalf("GetOptions 0x%x", hr)
	}
	const required = 0x20 | 0x40 | 0x800 | 0x8 | 0x2000000
	if options&required != required {
		t.Fatalf("folder/filesystem/path/no-cwd/no-recent flags: %x", options)
	}
	// Instantiate/configure the real native dialog, without opening a window
	// or enumerating thumbnails from user directories during development.
	if hr := dialog.invoke(17, uintptr(unsafe.Pointer(utf("fixture folder dialog")))); int32(hr) < 0 {
		t.Fatalf("SetTitle 0x%x", hr)
	}
}

func TestAnimationInvalidationIsLocal(t *testing.T) {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	oldWindow, oldArea, oldScale, oldPreview := window, previewArea, scale, preview
	defer func() { window, previewArea, scale, preview = oldWindow, oldArea, oldScale, oldPreview }()
	window = call("CreateWindowExW", 0, uintptr(unsafe.Pointer(utf("STATIC"))), uintptr(unsafe.Pointer(utf("self-authored invalidation fixture"))), 0x90000000, 0, 0, 800, 600, 0, 0, 0, 0)
	if window == 0 {
		t.Fatal("fixture window creation")
	}
	defer call("DestroyWindow", window)
	scale = 1
	previewArea = placement{20, 30, 100, 100}
	call("ValidateRect", window, 0)
	setPreview(image.NewNRGBA(image.Rect(0, 0, 256, 256)))
	var dirty rect
	if call("GetUpdateRect", window, uintptr(unsafe.Pointer(&dirty)), 0) == 0 || dirty != (rect{20, 30, 120, 130}) {
		t.Fatal("animation invalidated more than the preview rectangle", dirty)
	}
}
