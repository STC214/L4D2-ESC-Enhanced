package main

import (
	"bytes"
	"errors"
	"image"
	"image/color"
	"image/draw"
	"image/gif"
	"io"
	"os"
	"path/filepath"
	"strings"
)

type preparedTexture struct {
	Raw     []byte
	Info    *VTFInfo
	FPS     float64
	Preview *image.NRGBA
}

func readTextureInput(path string) ([]byte, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	stat, err := f.Stat()
	if err != nil {
		return nil, err
	}
	if !stat.Mode().IsRegular() || stat.Size() > 32<<20 {
		return nil, errors.New("素材须为小于 32 MiB 的普通文件")
	}
	raw, err := io.ReadAll(io.LimitReader(f, (32<<20)+1))
	if err != nil {
		return nil, err
	}
	if len(raw) > 32<<20 {
		return nil, errors.New("素材超过 32 MiB")
	}
	return raw, nil
}

func prepareTexture(path string, preserve bool) (preparedTexture, error) {
	var result preparedTexture
	ext := strings.ToLower(filepath.Ext(path))
	if preserve || ext == ".vtf" || ext == ".gif" {
		raw, err := readTextureInput(path)
		if err != nil {
			return result, err
		}
		if preserve || ext == ".vtf" {
			info, err := inspectVTF(raw)
			return preparedTexture{Raw: raw, Info: info, FPS: 10}, err
		}
		return convertGIF(raw)
	}
	img, err := loadImage(path)
	if err != nil {
		return result, err
	}
	return preparedTexture{Raw: encodeVTF(img), Preview: img}, nil
}

// Bound frames and decoded rectangle area before gif.DecodeAll allocates them.
func inspectGIF(raw []byte) (int, error) {
	bad := errors.New("GIF 损坏或超限：最多 256 帧、画布 8M 像素、累计画布／帧区域 64M 像素")
	if len(raw) < 13 || (string(raw[:6]) != "GIF87a" && string(raw[:6]) != "GIF89a") {
		return 0, bad
	}
	w, h := int(le.Uint16(raw[6:])), int(le.Uint16(raw[8:]))
	if w < 1 || h < 1 || w > 8192 || h > 8192 || w*h > 8<<20 {
		return 0, bad
	}
	at := 13
	if raw[10]&0x80 != 0 {
		at += 3 << ((raw[10] & 7) + 1)
	}
	frames, pixels := 0, 0
	blocks := func() bool {
		for at < len(raw) {
			n := int(raw[at])
			at++
			if n == 0 {
				return true
			}
			if n > len(raw)-at {
				return false
			}
			at += n
		}
		return false
	}
	for at < len(raw) {
		tag := raw[at]
		at++
		switch tag {
		case 0x21:
			if at >= len(raw) {
				return 0, bad
			}
			at++
			if !blocks() {
				return 0, bad
			}
		case 0x2c:
			if len(raw)-at < 9 {
				return 0, bad
			}
			x, y := int(le.Uint16(raw[at:])), int(le.Uint16(raw[at+2:]))
			fw, fh := int(le.Uint16(raw[at+4:])), int(le.Uint16(raw[at+6:]))
			if fw < 1 || fh < 1 || x+fw > w || y+fh > h {
				return 0, bad
			}
			frames++
			pixels += fw * fh
			if frames > 256 || pixels > 64<<20 || w*h > (64<<20)/frames {
				return 0, bad
			}
			flags := raw[at+8]
			at += 9
			if flags&0x80 != 0 {
				at += 3 << ((flags & 7) + 1)
			}
			if at >= len(raw) {
				return 0, bad
			}
			at++
			if !blocks() {
				return 0, bad
			}
		case 0x3b:
			if frames > 0 {
				return frames, nil
			}
			return 0, bad
		default:
			return 0, bad
		}
	}
	return 0, bad
}

func convertGIF(raw []byte) (preparedTexture, error) {
	var result preparedTexture
	count, err := inspectGIF(raw)
	if err != nil {
		return result, err
	}
	g, err := gif.DecodeAll(bytes.NewReader(raw))
	if err != nil {
		return result, err
	}
	if len(g.Image) != count {
		return result, errors.New("GIF 帧数不一致")
	}
	size := 256
	for 80+size*size*4*count >= 512<<10 {
		size /= 2
	}
	canvas := image.NewNRGBA(image.Rect(0, 0, g.Config.Width, g.Config.Height))
	out := make([]byte, 80, 80+size*size*4*count)
	copy(out, "VTF\x00")
	le.PutUint32(out[4:], 7)
	le.PutUint32(out[8:], 2)
	le.PutUint32(out[12:], 80)
	le.PutUint16(out[16:], uint16(size))
	le.PutUint16(out[18:], uint16(size))
	le.PutUint16(out[24:], uint16(count))
	le.PutUint32(out[20:], 0x230c)
	out[56] = 1
	le.PutUint32(out[57:], 0xffffffff)
	le.PutUint16(out[63:], 1)
	totalDelay := 0
	for i, frame := range g.Image {
		disposal := byte(0)
		if i < len(g.Disposal) {
			disposal = g.Disposal[i]
		}
		var previous []byte
		if disposal == gif.DisposalPrevious {
			previous = append([]byte{}, canvas.Pix...)
		}
		draw.Draw(canvas, frame.Bounds(), frame, frame.Bounds().Min, draw.Over)
		fitted := fitImageSize(canvas, size)
		out = append(out, fitted.Pix...)
		delay := g.Delay[i]
		if delay <= 0 {
			delay = 10
		}
		totalDelay += delay
		switch disposal {
		case gif.DisposalBackground:
			background := color.Color(color.Transparent)
			if p, ok := g.Config.ColorModel.(color.Palette); ok && int(g.BackgroundIndex) < len(p) {
				background = p[g.BackgroundIndex]
				if int(g.BackgroundIndex) < len(frame.Palette) {
					_, _, _, a := frame.Palette[g.BackgroundIndex].RGBA()
					if a == 0 {
						background = color.Transparent
					}
				}
			}
			draw.Draw(canvas, frame.Bounds(), &image.Uniform{C: background}, image.Point{}, draw.Src)
		case gif.DisposalPrevious:
			copy(canvas.Pix, previous)
		}
	}
	info, err := inspectVTF(out)
	return preparedTexture{Raw: out, Info: info, FPS: animationFPS(float64(count) * 100 / float64(totalDelay))}, err
}
