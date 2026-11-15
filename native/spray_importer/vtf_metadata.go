package main

import "errors"

// VTFInfo contains structural fields only, never decoded pixels.
type VTFInfo struct {
	Major, Minor, Width, Height, Frames, Mips int
	Format                                    uint32
}

var errMetadataPreview = errors.New("VPK 素材仅显示结构参数，不生成画面预览")

func vtfLevelBytes(w, h int, format uint32) int {
	switch format {
	case 0, 12:
		return w * h * 4
	case 2, 3:
		return w * h * 3
	case 13:
		return max(1, (w+3)/4) * max(1, (h+3)/4) * 8
	case 14, 15:
		return max(1, (w+3)/4) * max(1, (h+3)/4) * 16
	}
	return -1
}

// Validate every mip/frame byte range without decompressing or sampling pixels.
// Keep the original bytes below the existing engine upload size boundary.
func inspectVTF(raw []byte) (*VTFInfo, error) {
	bad := errors.New("VTF 结构、帧数据或资源范围无效")
	if len(raw) < 64 || string(raw[:4]) != "VTF\x00" {
		return nil, bad
	}
	if len(raw) >= 512<<10 {
		return nil, errors.New("原样保留的 VTF 须小于 512 KiB；不会自动丢帧或转换画面")
	}
	info := &VTFInfo{Major: int(le.Uint32(raw[4:])), Minor: int(le.Uint32(raw[8:])), Width: int(le.Uint16(raw[16:])), Height: int(le.Uint16(raw[18:])), Frames: int(le.Uint16(raw[24:])), Format: le.Uint32(raw[52:]), Mips: int(raw[56])}
	header := int(le.Uint32(raw[12:]))
	if info.Major != 7 || info.Minor > 5 || header < 64 || header > len(raw) || info.Width < 1 || info.Height < 1 || info.Width > 8192 || info.Height > 8192 || info.Width*info.Height > 32<<20 || info.Frames < 1 || info.Frames > 256 || info.Mips < 1 || info.Mips > 14 || le.Uint32(raw[20:])&0x4000 != 0 {
		return nil, bad
	}
	if info.Minor >= 2 && (header < 65 || le.Uint16(raw[63:]) != 1) {
		return nil, bad
	}
	first := int(le.Uint16(raw[26:]))
	if first != 0xffff && first >= info.Frames {
		return nil, bad
	}
	maxMips := 1
	for n := max(info.Width, info.Height); n > 1; n >>= 1 {
		maxMips++
	}
	if info.Mips > maxMips {
		return nil, bad
	}
	start := header
	thumbnailStart, thumbnailSize := -1, 0
	var auxiliaryOffsets []int
	if (raw[61] == 0) != (raw[62] == 0) {
		return nil, bad
	}
	if raw[61] > 0 {
		thumbnailSize = vtfLevelBytes(int(raw[61]), int(raw[62]), le.Uint32(raw[57:]))
		if thumbnailSize < 0 {
			return nil, bad
		}
	}
	if info.Minor >= 3 {
		if header < 80 {
			return nil, bad
		}
		count := int(le.Uint32(raw[68:]))
		if count > 32 || 80+count*8 > header {
			return nil, bad
		}
		found := 0
		seen := map[string]bool{}
		for at := 80; at < 80+count*8; at += 8 {
			tag, flags := string(raw[at:at+3]), raw[at+3]
			if seen[tag] || (flags != 0 && flags != 2) {
				return nil, bad
			}
			seen[tag] = true
			offset := int(le.Uint32(raw[at+4:]))
			if flags == 0 && (offset < header || offset >= len(raw)) {
				return nil, bad
			}
			switch tag {
			case "\x30\x00\x00":
				if flags != 0 {
					return nil, bad
				}
				start = offset
				found++
			case "\x01\x00\x00":
				if flags != 0 || thumbnailSize == 0 || thumbnailSize > len(raw)-offset {
					return nil, bad
				}
				thumbnailStart = offset
			default:
				if flags == 0 {
					auxiliaryOffsets = append(auxiliaryOffsets, offset)
				}
			}
		}
		if found != 1 || start < header || start > len(raw) || (thumbnailSize > 0 && thumbnailStart < 0) {
			return nil, bad
		}
	} else {
		start += thumbnailSize
	}
	total := 0
	for level := 0; level < info.Mips; level++ {
		n := vtfLevelBytes(max(1, info.Width>>level), max(1, info.Height>>level), info.Format)
		if n < 0 || n > (len(raw)-min(start, len(raw))-total)/info.Frames {
			return nil, bad
		}
		total += n * info.Frames
	}
	if start > len(raw) || total > len(raw)-start {
		return nil, bad
	}
	if info.Minor < 3 && start+total != len(raw) {
		return nil, bad
	}
	if thumbnailStart >= 0 && thumbnailStart < start+total && thumbnailStart+thumbnailSize > start {
		return nil, bad
	}
	for _, offset := range auxiliaryOffsets {
		if (offset >= start && offset < start+total) || (thumbnailStart >= 0 && offset >= thumbnailStart && offset < thumbnailStart+thumbnailSize) {
			return nil, bad
		}
	}
	return info, nil
}
