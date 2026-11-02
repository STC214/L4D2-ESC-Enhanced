package main

import (
	"bytes"
	"debug/pe"
	"errors"
	"fmt"
)

// Verify the linked PE, not merely the ICO source or an old .syso hash.
func verifyEmbeddedIcon(executable, ico []byte) error {
	bad := errors.New("EXE 内置图标与当前 ICO 不一致，请重新生成资源对象")
	f, e := pe.NewFile(bytes.NewReader(executable))
	if e != nil {
		return e
	}
	defer f.Close()
	optional, ok := f.OptionalHeader.(*pe.OptionalHeader64)
	if !ok || f.Machine != pe.IMAGE_FILE_MACHINE_AMD64 || optional.DataDirectory[2].VirtualAddress == 0 {
		return bad
	}
	readRVA := func(rva, size uint32) ([]byte, error) {
		for _, s := range f.Sections {
			if rva >= s.VirtualAddress && uint64(rva)+uint64(size) <= uint64(s.VirtualAddress)+uint64(s.Size) {
				data, e := s.Data()
				if e != nil {
					return nil, e
				}
				start := uint64(rva - s.VirtualAddress)
				end := start + uint64(size)
				if end > uint64(len(data)) {
					return nil, bad
				}
				return data[start:end], nil
			}
		}
		return nil, bad
	}
	base := optional.DataDirectory[2].VirtualAddress
	root, e := readRVA(base, optional.DataDirectory[2].Size)
	if e != nil {
		return e
	}
	lookup := func(relative, id uint32) (uint32, error) {
		if uint64(relative)+16 > uint64(len(root)) {
			return 0, bad
		}
		count := int(le.Uint16(root[relative+12:])) + int(le.Uint16(root[relative+14:]))
		if uint64(relative)+16+uint64(count)*8 > uint64(len(root)) {
			return 0, bad
		}
		found := false
		var result uint32
		for i := 0; i < count; i++ {
			at := int(relative) + 16 + i*8
			if le.Uint32(root[at:]) == id {
				if found {
					return 0, bad
				}
				found = true
				result = le.Uint32(root[at+4:])
			}
		}
		if !found {
			return 0, bad
		}
		return result, nil
	}
	payload := func(kind, id uint32) ([]byte, error) {
		node, e := lookup(0, kind)
		if e != nil || node&0x80000000 == 0 {
			return nil, bad
		}
		node, e = lookup(node&0x7fffffff, id)
		if e != nil || node&0x80000000 == 0 {
			return nil, bad
		}
		node &= 0x7fffffff
		if uint64(node)+24 > uint64(len(root)) {
			return nil, bad
		}
		if int(le.Uint16(root[node+12:]))+int(le.Uint16(root[node+14:])) != 1 {
			return nil, bad
		}
		entry := le.Uint32(root[node+20:])
		if entry&0x80000000 != 0 || uint64(entry)+16 > uint64(len(root)) {
			return nil, bad
		}
		return readRVA(le.Uint32(root[entry:]), le.Uint32(root[entry+4:]))
	}
	group, e := payload(14, 101)
	if e != nil {
		return e
	}
	if len(ico) < 6+16*len(iconSizes) || len(group) != 6+14*len(iconSizes) || le.Uint16(ico) != 0 || le.Uint16(ico[2:]) != 1 || int(le.Uint16(ico[4:])) != len(iconSizes) || le.Uint16(group) != 0 || le.Uint16(group[2:]) != 1 || int(le.Uint16(group[4:])) != len(iconSizes) {
		return bad
	}
	for i, size := range iconSizes {
		a, b := group[6+i*14:], ico[6+i*16:]
		if a[0] != byte(size%256) || a[1] != byte(size%256) || !bytes.Equal(a[:12], b[:12]) {
			return bad
		}
		n, start := le.Uint32(b[8:]), le.Uint32(b[12:])
		if uint64(start)+uint64(n) > uint64(len(ico)) {
			return bad
		}
		data, e := payload(3, uint32(le.Uint16(a[12:])))
		if e != nil || !bytes.Equal(data, ico[start:start+n]) {
			return fmt.Errorf("%w：%d 像素", bad, size)
		}
	}
	return nil
}
