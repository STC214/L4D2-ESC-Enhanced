package main

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"image"
	"image/color"
	"image/draw"
	"image/gif"
	_ "image/jpeg"
	"image/png"
	"io"
	"math"
	"os"
	"path/filepath"
	"strings"
)

var le = binary.LittleEndian

func atomicWrite(path string, data []byte) error {
	if _, err := safePath(filepath.Dir(path), filepath.Base(path)); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	f, err := os.CreateTemp(filepath.Dir(path), ".csp-*.tmp")
	if err != nil {
		return err
	}
	name := f.Name()
	defer os.Remove(name)
	if _, err = f.Write(data); err != nil {
		f.Close()
		return err
	}
	if err = f.Sync(); err != nil {
		f.Close()
		return err
	}
	if err = f.Close(); err != nil {
		return err
	}
	if err = os.Rename(name, path); err != nil {
		return err
	}
	actual, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	if !bytes.Equal(actual, data) {
		return errors.New("写入读回校验失败")
	}
	return nil
}

func loadImage(path string) (*image.NRGBA, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil || info.Size() > 32<<20 {
		return nil, errors.New("图片须小于 32 MiB")
	}
	raw, err := io.ReadAll(io.LimitReader(f, (32<<20)+1))
	if err != nil {
		return nil, err
	}
	if len(raw) > 32<<20 {
		return nil, errors.New("图片须小于 32 MiB")
	}
	var src image.Image
	if bytes.HasPrefix(raw, []byte("VTF\x00")) {
		src, err = decodeVTF(raw)
	} else if bytes.HasPrefix(raw, []byte("BM")) {
		src, err = decodeBMP(raw)
	} else {
		config, format, e := image.DecodeConfig(bytes.NewReader(raw))
		if e != nil {
			return nil, errors.New("支持 PNG、JPEG、静态 GIF、24 位 BMP 和常用 VTF")
		}
		if config.Width < 1 || config.Height < 1 || config.Width > 8192 || config.Height > 8192 || config.Width*config.Height > 32<<20 {
			return nil, errors.New("图片尺寸超限（边长 8192，像素 32M）")
		}
		if format == "gif" {
			if e := validateStaticGIF(raw); e != nil {
				return nil, e
			}
			var g *gif.GIF
			g, err = gif.DecodeAll(bytes.NewReader(raw))
			if err == nil && len(g.Image) != 1 {
				return nil, errors.New("请使用静态图片")
			}
			if err == nil {
				src = g.Image[0]
			}
		} else {
			src, _, err = image.Decode(bytes.NewReader(raw))
		}
	}
	if err != nil {
		return nil, err
	}
	return fitImage(src), nil
}

// Count image descriptors before decompressing: animated GIFs must not allocate
// every frame merely so that we can reject them afterwards.
func validateStaticGIF(raw []byte) error {
	bad := errors.New("GIF 数据损坏或不是单帧静态图片")
	if len(raw) < 13 {
		return bad
	}
	at := 13
	if raw[10]&0x80 != 0 {
		at += 3 << ((raw[10] & 7) + 1)
	}
	frames := 0
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
				return bad
			}
			at++
			if !blocks() {
				return bad
			}
		case 0x2c:
			frames++
			if frames > 1 || len(raw)-at < 9 {
				return bad
			}
			flags := raw[at+8]
			at += 9
			if flags&0x80 != 0 {
				at += 3 << ((flags & 7) + 1)
			}
			if at >= len(raw) {
				return bad
			}
			at++
			if !blocks() {
				return bad
			}
		case 0x3b:
			if frames == 1 {
				return nil
			}
			return bad
		default:
			return bad
		}
	}
	return bad
}

func fitImage(src image.Image) *image.NRGBA {
	b := src.Bounds()
	w, h := b.Dx(), b.Dy()
	scale := math.Min(256/float64(w), 256/float64(h))
	nw, nh := max(1, int(math.Round(float64(w)*scale))), max(1, int(math.Round(float64(h)*scale)))
	out := image.NewNRGBA(image.Rect(0, 0, 256, 256))
	for y := 0; y < nh; y++ {
		for x := 0; x < nw; x++ {
			fx := math.Max(0, math.Min(float64(w-1), (float64(x)+.5)*float64(w)/float64(nw)-.5))
			fy := math.Max(0, math.Min(float64(h-1), (float64(y)+.5)*float64(h)/float64(nh)-.5))
			x0, y0 := int(fx), int(fy)
			dx, dy := fx-float64(x0), fy-float64(y0)
			var sums [4]float64
			for j := 0; j < 2; j++ {
				for i := 0; i < 2; i++ {
					weight := []float64{1 - dx, dx}[i] * []float64{1 - dy, dy}[j]
					r, g, bl, a := src.At(b.Min.X+min(w-1, x0+i), b.Min.Y+min(h-1, y0+j)).RGBA()
					for c, v := range []uint32{r, g, bl, a} {
						sums[c] += float64(v) * weight
					}
				}
			}
			pixel := color.NRGBA{A: uint8(math.Round(sums[3] / 257))}
			if sums[3] > 0 {
				pixel.R = uint8(math.Round(sums[0] * 255 / sums[3]))
				pixel.G = uint8(math.Round(sums[1] * 255 / sums[3]))
				pixel.B = uint8(math.Round(sums[2] * 255 / sums[3]))
			}
			out.SetNRGBA(x+(256-nw)/2, y+(256-nh)/2, pixel)
		}
	}
	return out
}

func encodeVTF(img *image.NRGBA) []byte {
	out := make([]byte, 80+256*256*4)
	copy(out, "VTF\x00")
	le.PutUint32(out[4:], 7)
	le.PutUint32(out[8:], 2)
	le.PutUint32(out[12:], 80)
	le.PutUint16(out[16:], 256)
	le.PutUint16(out[18:], 256)
	le.PutUint32(out[20:], 0x230c)
	le.PutUint16(out[24:], 1)
	le.PutUint32(out[48:], math.Float32bits(1))
	out[56] = 1
	le.PutUint32(out[57:], 0xffffffff)
	le.PutUint16(out[63:], 1)
	for y := 0; y < 256; y++ {
		copy(out[80+y*1024:], img.Pix[y*img.Stride:y*img.Stride+1024])
	}
	return out
}

func decodeVTF(raw []byte) (*image.NRGBA, error) {
	if len(raw) < 64 || string(raw[:4]) != "VTF\x00" {
		return nil, errors.New("VTF 文件头损坏")
	}
	major, minor, header := le.Uint32(raw[4:]), le.Uint32(raw[8:]), int(le.Uint32(raw[12:]))
	w, h := int(le.Uint16(raw[16:])), int(le.Uint16(raw[18:]))
	flags, frames, format, mips := le.Uint32(raw[20:]), le.Uint16(raw[24:]), le.Uint32(raw[52:]), int(raw[56])
	if major != 7 || minor > 5 || header < 64 || header > len(raw) || w < 1 || h < 1 || w > 8192 || h > 8192 || w*h > 32<<20 || frames != 1 || flags&0x4000 != 0 || mips < 1 || mips > 14 {
		return nil, errors.New("仅支持尺寸受限的单帧二维 VTF 7.0～7.5")
	}
	if minor >= 2 && (len(raw) < 65 || le.Uint16(raw[63:]) != 1) {
		return nil, errors.New("VTF 深度须为 1")
	}
	size := func(w, h int, f uint32) int {
		switch f {
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
	start := header
	if minor >= 3 {
		if header < 80 {
			return nil, errors.New("VTF 资源表损坏")
		}
		count := int(le.Uint32(raw[68:]))
		found := 0
		if count > 32 || 80+count*8 > header {
			return nil, errors.New("VTF 资源表越界")
		}
		for at := 80; at < 80+count*8; at += 8 {
			if string(raw[at:at+3]) == "\x30\x00\x00" {
				if raw[at+3]&2 != 0 {
					return nil, errors.New("VTF 图像资源标志异常")
				}
				start = int(le.Uint32(raw[at+4:]))
				found++
			}
		}
		if found != 1 || start < header {
			return nil, errors.New("VTF 高分辨率图像缺失")
		}
	} else if le.Uint32(raw[57:]) != 0xffffffff && raw[61] > 0 && raw[62] > 0 {
		n := size(int(raw[61]), int(raw[62]), le.Uint32(raw[57:]))
		if n < 0 {
			return nil, errors.New("缩略图编码未支持")
		}
		start += n
	}
	for level := 1; level < mips; level++ {
		n := size(max(1, w>>level), max(1, h>>level), format)
		if n < 0 {
			return nil, errors.New("VTF 编码未支持")
		}
		start += n
	}
	n := size(w, h, format)
	if n < 0 || start < 0 || start > len(raw) || n > len(raw)-start {
		return nil, errors.New("VTF 编码未支持或图像数据截断")
	}
	data := raw[start : start+n]
	img := image.NewNRGBA(image.Rect(0, 0, w, h))
	if format == 13 || format == 14 || format == 15 {
		decodeBlocks(img, data, format)
		return img, nil
	}
	step := 4
	if format == 2 || format == 3 {
		step = 3
	}
	for i := 0; i < w*h; i++ {
		p := data[i*step:]
		c := color.NRGBA{R: p[0], G: p[1], B: p[2], A: 255}
		if step == 4 {
			c.A = p[3]
		}
		if format == 3 || format == 12 {
			c.R, c.B = c.B, c.R
		}
		img.SetNRGBA(i%w, i/w, c)
	}
	return img, nil
}

func decodeBlocks(img *image.NRGBA, data []byte, format uint32) {
	w, h := img.Bounds().Dx(), img.Bounds().Dy()
	step := 8
	if format != 13 {
		step = 16
	}
	for by := 0; by < h; by += 4 {
		for bx := 0; bx < w; bx += 4 {
			block := data[:step]
			data = data[step:]
			colors := block
			if step == 16 {
				colors = block[8:]
			}
			a, b := le.Uint16(colors), le.Uint16(colors[2:])
			expand := func(v uint16) color.NRGBA {
				return color.NRGBA{uint8((int(v>>11)*255 + 15) / 31), uint8((int((v>>5)&63)*255 + 31) / 63), uint8((int(v&31)*255 + 15) / 31), 255}
			}
			palette := [4]color.NRGBA{expand(a), expand(b)}
			mix := func(x, y color.NRGBA, wx, wy, div int) color.NRGBA {
				return color.NRGBA{uint8((int(x.R)*wx + int(y.R)*wy) / div), uint8((int(x.G)*wx + int(y.G)*wy) / div), uint8((int(x.B)*wx + int(y.B)*wy) / div), 255}
			}
			if a > b || format != 13 {
				palette[2] = mix(palette[0], palette[1], 2, 1, 3)
				palette[3] = mix(palette[0], palette[1], 1, 2, 3)
			} else {
				palette[2] = mix(palette[0], palette[1], 1, 1, 2)
			}
			indices := le.Uint32(colors[4:])
			var alpha [8]uint8
			var bits uint64
			if format == 15 {
				alpha[0], alpha[1] = block[0], block[1]
				for i := 0; i < 6; i++ {
					bits |= uint64(block[i+2]) << uint(8*i)
				}
				if alpha[0] > alpha[1] {
					for i := 1; i <= 6; i++ {
						alpha[i+1] = uint8(((7-i)*int(alpha[0]) + i*int(alpha[1])) / 7)
					}
				} else {
					for i := 1; i <= 4; i++ {
						alpha[i+1] = uint8(((5-i)*int(alpha[0]) + i*int(alpha[1])) / 5)
					}
					alpha[7] = 255
				}
			}
			for i := 0; i < 16; i++ {
				c := palette[(indices>>uint(i*2))&3]
				if format == 14 {
					c.A = ((block[i/2] >> uint((i%2)*4)) & 15) * 17
				}
				if format == 15 {
					c.A = alpha[(bits>>uint(i*3))&7]
				}
				if bx+i%4 < w && by+i/4 < h {
					img.SetNRGBA(bx+i%4, by+i/4, c)
				}
			}
		}
	}
}

func decodeBMP(raw []byte) (*image.NRGBA, error) {
	if len(raw) < 54 || le.Uint32(raw[14:]) < 40 || le.Uint16(raw[26:]) != 1 || le.Uint16(raw[28:]) != 24 || le.Uint32(raw[30:]) != 0 {
		return nil, errors.New("BMP 请选择未压缩的 24 位格式")
	}
	w, h := int(int32(le.Uint32(raw[18:]))), int(int32(le.Uint32(raw[22:])))
	flip := h > 0
	if h < 0 {
		h = -h
	}
	start := int(le.Uint32(raw[10:]))
	stride := (w*3 + 3) &^ 3
	if w < 1 || h < 1 || w > 8192 || h > 8192 || w*h > 32<<20 || start < 54 || start > len(raw) || stride*h > len(raw)-start {
		return nil, errors.New("BMP 尺寸或数据异常")
	}
	img := image.NewNRGBA(image.Rect(0, 0, w, h))
	for y := 0; y < h; y++ {
		sy := y
		if flip {
			sy = h - 1 - y
		}
		for x := 0; x < w; x++ {
			p := raw[start+sy*stride+x*3:]
			img.SetNRGBA(x, y, color.NRGBA{p[2], p[1], p[0], 255})
		}
	}
	return img, nil
}

func savePNG(path string, img image.Image) error {
	var out bytes.Buffer
	if err := png.Encode(&out, img); err != nil {
		return err
	}
	return atomicWrite(path, out.Bytes())
}

func previewBG(img image.Image) *image.RGBA {
	out := image.NewRGBA(image.Rect(0, 0, 256, 256))
	for y := 0; y < 256; y++ {
		for x := 0; x < 256; x++ {
			v := uint8(210)
			if (x/16+y/16)%2 != 0 {
				v = 240
			}
			out.SetRGBA(x, y, color.RGBA{v, v, v, 255})
		}
	}
	draw.Draw(out, out.Bounds(), img, img.Bounds().Min, draw.Over)
	return out
}

func imageError(path string, err error) error {
	return fmt.Errorf("%s：%w", strings.TrimSpace(path), err)
}
