package main

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"hash/crc32"
	"image"
	"image/draw"
	"image/png"
	"io"
)

var be = binary.BigEndian

type animationImport struct {
	Original, Kept, Bytes, Size int
}

func (a *animationImport) description() string {
	if a == nil {
		return ""
	}
	return fmt.Sprintf("APNG：保留前 %d/%d 帧，舍弃 %d 帧；输出 %d×%d，%d 字节", a.Kept, a.Original, a.Original-a.Kept, a.Size, a.Size, a.Bytes)
}

type apngFrame struct {
	area           image.Rectangle
	delay          float64
	dispose, blend byte
	data           [][]byte
	defaultFrame   bool
	hasData        bool
}

const apngInputLimit = 1 << 30
const apngCompressedLimit = 128 << 20

func pngChunk(out *bytes.Buffer, kind string, data []byte) {
	var n [4]byte
	be.PutUint32(n[:], uint32(len(data)))
	out.Write(n[:])
	out.WriteString(kind)
	out.Write(data)
	hash := crc32.NewIEEE()
	hash.Write([]byte(kind))
	hash.Write(data)
	be.PutUint32(n[:], hash.Sum32())
	out.Write(n[:])
}

// Parse all chunk bounds, CRCs, frame counts and sequence numbers before any
// pixel allocation. Only the retained continuous prefix is decompressed.
func parseAPNG(raw []byte) ([]byte, []byte, []apngFrame, error) {
	return parseAPNGReader(bytes.NewReader(raw))
}

func parseAPNGReader(input io.Reader) ([]byte, []byte, []apngFrame, error) {
	bad := errors.New("APNG 结构、CRC、帧序号或尺寸异常")
	var signature [8]byte
	if _, err := io.ReadFull(input, signature[:]); err != nil || string(signature[:]) != "\x89PNG\r\n\x1a\n" {
		return nil, nil, nil, bad
	}
	var header []byte
	var palette bytes.Buffer
	var frames []apngFrame
	declared, sequence := uint32(0), uint32(0)
	sawIDAT, endedIDAT, ended := false, false, false
	seenPalette, seenTransparency := false, false
	w, h := 0, 0
	total, retained := uint64(8), uint64(0)
	buffer := make([]byte, 32<<10)
	for chunks := 0; !ended; chunks++ {
		if chunks >= 100000 {
			return nil, nil, nil, errors.New("APNG 块数量超过 100000")
		}
		var chunkHeader [8]byte
		if _, err := io.ReadFull(input, chunkHeader[:]); err != nil {
			return nil, nil, nil, bad
		}
		n := uint64(be.Uint32(chunkHeader[:]))
		if n > 0x7fffffff || n+12 > apngInputLimit-total {
			return nil, nil, nil, errors.New("APNG 输入超过 1 GiB 流式处理上限或块长度异常")
		}
		total += n + 12
		kind := string(chunkHeader[4:])
		// Validate chunk names before discarding ancillary payloads.
		for _, c := range chunkHeader[4:] {
			if !(c >= 'A' && c <= 'Z' || c >= 'a' && c <= 'z') {
				return nil, nil, nil, bad
			}
		}
		if chunkHeader[6]&32 != 0 {
			return nil, nil, nil, bad
		}
		take := uint64(0)
		switch kind {
		case "IHDR":
			if n != 13 {
				return nil, nil, nil, bad
			}
			take = n
		case "acTL":
			if n != 8 {
				return nil, nil, nil, bad
			}
			take = n
		case "fcTL":
			if n != 26 {
				return nil, nil, nil, bad
			}
			take = n
		case "PLTE":
			if n > 768 {
				return nil, nil, nil, bad
			}
			take = n
		case "tRNS":
			if n > 256 {
				return nil, nil, nil, bad
			}
			take = n
		case "fdAT":
			if n < 4 {
				return nil, nil, nil, bad
			}
			take = 4
		}
		keepPayload := kind == "IDAT" && len(frames) == 1 && frames[0].defaultFrame || kind == "fdAT" && len(frames) > 0 && len(frames) <= 31
		if keepPayload {
			if n > apngCompressedLimit-retained {
				return nil, nil, nil, errors.New("APNG 保留帧压缩数据超过 128 MiB 内存预算")
			}
			retained += n
			take = n
		}
		hash := crc32.NewIEEE()
		hash.Write(chunkHeader[4:])
		data := make([]byte, int(take))
		if _, err := io.ReadFull(io.TeeReader(input, hash), data); err != nil {
			return nil, nil, nil, bad
		}
		copied, err := io.CopyBuffer(hash, io.LimitReader(input, int64(n-take)), buffer)
		if err != nil || uint64(copied) != n-take {
			return nil, nil, nil, bad
		}
		var checksum [4]byte
		if _, err := io.ReadFull(input, checksum[:]); err != nil || hash.Sum32() != be.Uint32(checksum[:]) {
			return nil, nil, nil, bad
		}
		if header == nil && kind != "IHDR" {
			return nil, nil, nil, bad
		}
		if sawIDAT && kind != "IDAT" {
			endedIDAT = true
		}
		switch kind {
		case "IHDR":
			if header != nil || len(data) != 13 {
				return nil, nil, nil, bad
			}
			header = append([]byte{}, data...)
			w, h = int(be.Uint32(data)), int(be.Uint32(data[4:]))
			if w < 1 || h < 1 || w > 8192 || h > 8192 || w*h > 8<<20 {
				return nil, nil, nil, bad
			}
		case "PLTE", "tRNS":
			if sawIDAT || kind == "PLTE" && seenPalette || kind == "tRNS" && seenTransparency {
				return nil, nil, nil, bad
			}
			if kind == "PLTE" {
				seenPalette = true
			} else {
				seenTransparency = true
			}
			pngChunk(&palette, kind, data)
		case "acTL":
			if declared != 0 || sawIDAT || len(data) != 8 {
				return nil, nil, nil, bad
			}
			declared = be.Uint32(data)
			if declared < 1 || declared > 10000 {
				return nil, nil, nil, bad
			}
		case "fcTL":
			if len(data) != 26 || be.Uint32(data) != sequence || (len(frames) > 0 && !frames[len(frames)-1].hasData) {
				return nil, nil, nil, bad
			}
			sequence++
			fw, fh, x, y := int(be.Uint32(data[4:])), int(be.Uint32(data[8:])), int(be.Uint32(data[12:])), int(be.Uint32(data[16:]))
			if fw < 1 || fh < 1 || x > w || y > h || fw > w-x || fh > h-y || data[24] > 2 || data[25] > 1 || len(frames) >= 10000 {
				return nil, nil, nil, bad
			}
			if !sawIDAT && (len(frames) != 0 || x != 0 || y != 0 || fw != w || fh != h) {
				return nil, nil, nil, bad
			}
			den := be.Uint16(data[22:])
			if den == 0 {
				den = 100
			}
			delay := float64(be.Uint16(data[20:])) / float64(den)
			if delay == 0 {
				delay = 0.01
			}
			frames = append(frames, apngFrame{area: image.Rect(x, y, x+fw, y+fh), delay: delay, dispose: data[24], blend: data[25], defaultFrame: !sawIDAT})
		case "IDAT":
			if endedIDAT || declared == 0 {
				return nil, nil, nil, bad
			}
			sawIDAT = true
			if len(frames) > 0 {
				if len(frames) != 1 || !frames[0].defaultFrame {
					return nil, nil, nil, bad
				}
				frames[0].hasData = true
				frames[0].data = append(frames[0].data, data)
			}
		case "fdAT":
			if !sawIDAT || len(frames) == 0 || frames[len(frames)-1].defaultFrame || len(data) < 4 || be.Uint32(data) != sequence {
				return nil, nil, nil, bad
			}
			sequence++
			frames[len(frames)-1].hasData = true
			if keepPayload {
				frames[len(frames)-1].data = append(frames[len(frames)-1].data, data[4:])
			}
		case "IEND":
			if n != 0 {
				return nil, nil, nil, bad
			}
			ended = true
		default:
			// Unknown critical chunks must not be silently discarded.
			if len(kind) != 4 || kind[0]&32 == 0 {
				return nil, nil, nil, bad
			}
		}
	}
	var trailing [1]byte
	if _, err := io.ReadFull(input, trailing[:]); err != io.EOF {
		return nil, nil, nil, bad
	}
	if !ended || !sawIDAT || int(declared) != len(frames) || len(frames) == 0 || !frames[len(frames)-1].hasData {
		return nil, nil, nil, bad
	}
	return header, palette.Bytes(), frames, nil
}

func convertAPNG(raw []byte) (preparedTexture, error) {
	var result preparedTexture
	header, palette, frames, err := parseAPNG(raw)
	if err != nil {
		return result, err
	}
	return convertAPNGFrames(header, palette, frames)
}

func convertAPNGFrames(header, palette []byte, frames []apngFrame) (preparedTexture, error) {
	var result preparedTexture
	size := 256
	for size > 64 && 80+size*size*4*len(frames) >= 512<<10 {
		size /= 2
	}
	kept := min(len(frames), ((512<<10)-81)/(size*size*4))
	w, h := int(be.Uint32(header)), int(be.Uint32(header[4:]))
	if w*h > (64<<20)/kept {
		return result, errors.New("APNG 保留帧累计画布超过 64M 像素")
	}
	canvas := image.NewNRGBA(image.Rect(0, 0, w, h))
	out := make([]byte, 80, 80+size*size*4*kept)
	copy(out, "VTF\x00")
	le.PutUint32(out[4:], 7)
	le.PutUint32(out[8:], 2)
	le.PutUint32(out[12:], 80)
	le.PutUint16(out[16:], uint16(size))
	le.PutUint16(out[18:], uint16(size))
	le.PutUint32(out[20:], 0x230c)
	le.PutUint16(out[24:], uint16(kept))
	out[56] = 1
	le.PutUint32(out[57:], 0xffffffff)
	le.PutUint16(out[63:], 1)
	totalDelay := 0.0
	for _, frame := range frames[:kept] {
		var encoded bytes.Buffer
		encoded.WriteString("\x89PNG\r\n\x1a\n")
		ihdr := append([]byte{}, header...)
		be.PutUint32(ihdr, uint32(frame.area.Dx()))
		be.PutUint32(ihdr[4:], uint32(frame.area.Dy()))
		pngChunk(&encoded, "IHDR", ihdr)
		encoded.Write(palette)
		for _, data := range frame.data {
			pngChunk(&encoded, "IDAT", data)
		}
		pngChunk(&encoded, "IEND", nil)
		img, e := png.Decode(bytes.NewReader(encoded.Bytes()))
		if e != nil {
			return result, e
		}
		var previous []byte
		if frame.dispose == 2 {
			previous = append([]byte{}, canvas.Pix...)
		}
		op := draw.Src
		if frame.blend == 1 {
			op = draw.Over
		}
		draw.Draw(canvas, frame.area, img, img.Bounds().Min, op)
		out = append(out, fitImageSize(canvas, size).Pix...)
		totalDelay += frame.delay
		switch frame.dispose {
		case 1:
			draw.Draw(canvas, frame.area, image.Transparent, image.Point{}, draw.Src)
		case 2:
			copy(canvas.Pix, previous)
		}
	}
	info, err := inspectVTF(out)
	return preparedTexture{Raw: out, Info: info, FPS: animationFPS(float64(kept) / totalDelay), Animation: &animationImport{len(frames), kept, len(out), size}}, err
}
