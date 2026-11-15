package main

import (
	"errors"
	"fmt"
	"image"
	"math"
)

func animationFPS(value float64) float64 {
	if math.IsNaN(value) || math.IsInf(value, 0) || value <= 0 {
		return 10
	}
	return min(100, max(1, value))
}

// VTF stores all frames of the smallest mip first, then the next larger mip.
// Decode only the requested frame for runtime preview. Source bytes stay intact.
func decodeVTFFrame(raw []byte, frame int) (*image.NRGBA, error) {
	info, err := inspectVTF(raw)
	if err != nil {
		return nil, err
	}
	if frame < 0 || frame >= info.Frames {
		return nil, errors.New("动画预览帧编号越界")
	}
	start := int(le.Uint32(raw[12:]))
	if info.Minor >= 3 {
		for at := 80; at < 80+int(le.Uint32(raw[68:]))*8; at += 8 {
			if string(raw[at:at+3]) == "\x30\x00\x00" {
				start = int(le.Uint32(raw[at+4:]))
				break
			}
		}
	} else if raw[61] > 0 && raw[62] > 0 {
		start += vtfLevelBytes(int(raw[61]), int(raw[62]), le.Uint32(raw[57:]))
	}
	for level := 1; level < info.Mips; level++ {
		start += vtfLevelBytes(max(1, info.Width>>level), max(1, info.Height>>level), info.Format) * info.Frames
	}
	size := vtfLevelBytes(info.Width, info.Height, info.Format)
	start += frame * size
	if start < 0 || start > len(raw) || size > len(raw)-start {
		return nil, errors.New("动画预览帧数据截断")
	}
	// Reuse the tested single-frame pixel decoder with an in-memory frame view.
	view := make([]byte, 80, 80+size)
	copy(view, "VTF\x00")
	le.PutUint32(view[4:], 7)
	le.PutUint32(view[8:], 2)
	le.PutUint32(view[12:], 80)
	le.PutUint16(view[16:], uint16(info.Width))
	le.PutUint16(view[18:], uint16(info.Height))
	le.PutUint16(view[24:], 1)
	le.PutUint32(view[52:], info.Format)
	view[56] = 1
	le.PutUint32(view[57:], 0xffffffff)
	le.PutUint16(view[63:], 1)
	return decodeVTF(append(view, raw[start:start+size]...))
}

type previewClip struct {
	Raw  []byte
	Info *VTFInfo
	FPS  float64
}

func (clip *previewClip) Frame(frame int) (*image.NRGBA, error) {
	img, err := decodeVTFFrame(clip.Raw, frame)
	if err != nil {
		return nil, err
	}
	return fitImage(img), nil
}

func animationMaterial(slot int, frames int, rate float64) []byte {
	material := fmt.Sprintf("\"LightmappedGeneric\"\n{\n\"$basetexture\" \"vgui/logos/csp_test/test_%03d\"\n\"$translucent\" \"1\"\n\"$decal\" \"1\"\n", slot)
	if frames > 1 {
		material += fmt.Sprintf("\"$frame\" \"0\"\n\"Proxies\"\n{\n\"AnimatedTexture\"\n{\n\"animatedTextureVar\" \"$basetexture\"\n\"animatedTextureFrameNumVar\" \"$frame\"\n\"animatedTextureFrameRate\" \"%.6g\"\n}\n}\n", animationFPS(rate))
	}
	return []byte(material + "}\n")
}
