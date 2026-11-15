package main

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

// The square hit area stays fixed. Only its image child/sibling rectangle is
// fitted, so raw VTF frames/mips need no resampling or content inspection.
func previewRect(w, h, x, y, size int) (int, int, int, int) {
	fw, fh := size, size
	if w > h {
		fh = max(1, (h*size+w/2)/w)
	} else if h > w {
		fw = max(1, (w*size+h/2)/h)
	}
	return x + (size-fw)/2, y + (size-fh)/2, fw, fh
}

func fitPreviewControl(raw []byte, name string, w, h, x, y, size int) ([]byte, error) {
	// Embedded resources contain flat controls, with no nested objects here.
	pattern := regexp.MustCompile(`"` + regexp.QuoteMeta(name) + `"\s*\{[^{}]*\}`)
	matches := pattern.FindAllIndex(raw, -1)
	if len(matches) != 1 {
		return nil, fmt.Errorf("预览控件缺失或重复：%s", name)
	}
	x, y, w, h = previewRect(w, h, x, y, size)
	block := raw[matches[0][0]:matches[0][1]]
	for _, field := range []struct {
		key   string
		value int
	}{{"xpos", x}, {"ypos", y}, {"wide", w}, {"tall", h}} {
		p := regexp.MustCompile(`("` + field.key + `"\s*)"[^"]*"`)
		if len(p.FindAllIndex(block, -1)) != 1 {
			return nil, fmt.Errorf("预览控件参数异常：%s/%s", name, field.key)
		}
		block = p.ReplaceAll(block, []byte(`${1}"`+strconv.Itoa(field.value)+`"`))
	}
	out := append([]byte{}, raw[:matches[0][0]]...)
	out = append(out, block...)
	return append(out, raw[matches[0][1]:]...), nil
}

func configureSlotPreview(files map[string][]byte, slot int, info *VTFInfo, fps float64) error {
	index := (slot - 1) % 12
	page := fmt.Sprintf("resource/ui/csp_test/page_%d.res", (slot-1)/12+1)
	confirm := fmt.Sprintf("resource/ui/csp_test/confirm_%03d.res", slot)
	var err error
	files[page], err = fitPreviewControl(files[page], fmt.Sprintf("CSPPreview%03d", slot), info.Width, info.Height,
		33+(index%4)*108, 32+(index/4)*83, 58)
	if err != nil {
		return err
	}
	files[confirm], err = fitPreviewControl(files[confirm], "CSPConfirmPreview", info.Width, info.Height, 145, 35, 160)
	if err != nil {
		return err
	}
	path := fmt.Sprintf("materials/vgui/logos/ui/csp_test/test_%03d.vmt", slot)
	if _, ok := files[path]; !ok {
		return fmt.Errorf("预览材质缺失：%s", path)
	}
	files[path] = previewMaterial(slot, info.Frames, fps)
	return nil
}

func previewMaterial(slot, frames int, fps float64) []byte {
	// Reuse the same frame proxy/rate as the world decal, with the UI shader.
	world := string(animationMaterial(slot, frames, fps))
	world = strings.Replace(world, `"LightmappedGeneric"`, `"UnlitGeneric"`, 1)
	world = strings.Replace(world, `"$decal" "1"`,
		`"$vertexcolor" "1"`+"\n"+`"$vertexalpha" "1"`+"\n"+`"$ignorez" "1"`, 1)
	return []byte(world)
}
