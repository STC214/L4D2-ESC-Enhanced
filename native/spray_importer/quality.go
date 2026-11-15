package main

import (
	"errors"
	"fmt"
	"image"
	"image/color"
	"path/filepath"
)

const masterSize = 1024
const qualityAnimationFrames = 3

func rgb565(c color.NRGBA) uint16 {
	return uint16((int(c.R)*31+127)/255)<<11 | uint16((int(c.G)*63+127)/255)<<5 | uint16((int(c.B)*31+127)/255)
}

func expand565(v uint16) color.NRGBA {
	return color.NRGBA{uint8((int(v>>11)*255 + 15) / 31), uint8((int((v>>5)&63)*255 + 31) / 63), uint8((int(v&31)*255 + 15) / 31), 255}
}

func colorDistance(a, b color.NRGBA) int {
	r, g, bl := int(a.R)-int(b.R), int(a.G)-int(b.G), int(a.B)-int(b.B)
	return 3*r*r + 6*g*g + bl*bl
}

// BC1/DXT1 with one-bit alpha. Select endpoints from the most distant opaque
// pair in the block, not a black/white RGB bounding-box diagonal.
func encodeDXT1(img *image.NRGBA) []byte {
	w, h := img.Bounds().Dx(), img.Bounds().Dy()
	out := make([]byte, vtfLevelBytes(w, h, 13))
	at := 0
	for by := 0; by < h; by += 4 {
		for bx := 0; bx < w; bx += 4 {
			var pixels [16]color.NRGBA
			var opaque [16]color.NRGBA
			count := 0
			transparent := false
			for i := 0; i < 16; i++ {
				c := img.NRGBAAt(img.Rect.Min.X+min(w-1, bx+i%4), img.Rect.Min.Y+min(h-1, by+i/4))
				pixels[i] = c
				if c.A < 128 {
					transparent = true
				} else {
					opaque[count] = c
					count++
				}
			}
			block := out[at : at+8]
			at += 8
			if count == 0 {
				le.PutUint32(block[4:], 0xffffffff)
				continue
			}
			a, b := rgb565(opaque[0]), rgb565(opaque[0])
			uniform := true
			for i := 1; i < count; i++ {
				if rgb565(opaque[i]) != a {
					uniform = false
					break
				}
			}
			if !uniform {
				best := -1
				for i := 0; i < count; i++ {
					for j := i + 1; j < count; j++ {
						if distance := colorDistance(opaque[i], opaque[j]); distance > best {
							best = distance
							a, b = rgb565(opaque[i]), rgb565(opaque[j])
						}
					}
				}
			}
			if transparent {
				if a > b {
					a, b = b, a
				}
			} else {
				if a < b {
					a, b = b, a
				}
				if a == b {
					if a == 65535 {
						b--
					} else {
						a++
					}
				}
			}
			palette := [4]color.NRGBA{expand565(a), expand565(b)}
			mix := func(x, y color.NRGBA, wx, wy, div int) color.NRGBA {
				return color.NRGBA{uint8((int(x.R)*wx + int(y.R)*wy) / div), uint8((int(x.G)*wx + int(y.G)*wy) / div), uint8((int(x.B)*wx + int(y.B)*wy) / div), 255}
			}
			limit := 4
			if transparent {
				palette[2] = mix(palette[0], palette[1], 1, 1, 2)
				limit = 3
			} else {
				palette[2] = mix(palette[0], palette[1], 2, 1, 3)
				palette[3] = mix(palette[0], palette[1], 1, 2, 3)
			}
			var indices uint32
			for i, c := range pixels {
				index := 3
				if c.A >= 128 {
					index = 0
					best := colorDistance(c, palette[0])
					for j := 1; j < limit; j++ {
						if distance := colorDistance(c, palette[j]); distance < best {
							index, best = j, distance
						}
					}
				}
				indices |= uint32(index) << uint(2*i)
			}
			le.PutUint16(block, a)
			le.PutUint16(block[2:], b)
			le.PutUint32(block[4:], indices)
		}
	}
	return out
}

func qualityTexture(masters []*image.NRGBA) (preparedTexture, error) {
	var result preparedTexture
	if len(masters) < 1 || len(masters) > qualityAnimationFrames {
		return result, errors.New("高清母版帧数量异常")
	}
	w, h := 1020, 1024
	if len(masters) > 1 {
		w, h = 512, 512
	}
	out := make([]byte, 80, 80+vtfLevelBytes(w, h, 13)*len(masters))
	copy(out, "VTF\x00")
	le.PutUint32(out[4:], 7)
	le.PutUint32(out[8:], 2)
	le.PutUint32(out[12:], 80)
	le.PutUint16(out[16:], uint16(w))
	le.PutUint16(out[18:], uint16(h))
	le.PutUint32(out[20:], 0x130c)
	le.PutUint16(out[24:], uint16(len(masters)))
	le.PutUint32(out[52:], 13)
	out[56] = 1
	le.PutUint32(out[57:], 0xffffffff)
	le.PutUint16(out[63:], 1)
	for _, master := range masters {
		if master == nil || master.Bounds() != image.Rect(0, 0, masterSize, masterSize) {
			return result, errors.New("高清母版尺寸须为 1024×1024")
		}
		out = append(out, encodeDXT1(fitImageRect(master, w, h))...)
	}
	info, err := inspectVTF(out)
	return preparedTexture{Raw: out, Info: info, Preview: masters[0], Masters: masters, Animation: &animationImport{Original: len(masters), Kept: len(masters), Bytes: len(out), Size: w, Kind: "图片", Encoding: "DXT1", Width: w, Height: h, MasterSize: masterSize}}, err
}

// The first 1024 master uses the existing preview.png role. Other retained
// frames are separate PNG masters. They are not placed into game/deploy VPKs.
func persistMasters(home, rel, previewPath string, prepared preparedTexture) ([]string, error) {
	if len(prepared.Masters) == 0 {
		return nil, nil
	}
	if previewPath == "" {
		return nil, errors.New("高清母版首帧路径缺失")
	}
	paths := []string{previewPath}
	for i := 1; i < len(prepared.Masters); i++ {
		path := fmt.Sprintf("%s/master_%03d.png", rel, i+1)
		full, err := safePath(home, path)
		if err != nil {
			return nil, err
		}
		if err = savePNG(filepath.Clean(full), prepared.Masters[i]); err != nil {
			return nil, err
		}
		paths = append(paths, path)
	}
	return paths, nil
}
