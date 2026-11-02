package main

import (
	"bytes"
	"encoding/binary"
	"image"
	"image/color"
	"image/png"
)

var iconSizes = []int{16, 24, 32, 48, 64, 128, 256}

// Area-average the canonical square image. Preserve the full composition and
// premultiplied alpha; no crop, redraw or original-file modification.
func iconImage(source *image.NRGBA, size int) *image.NRGBA {
	out := image.NewNRGBA(image.Rect(0, 0, size, size))
	for y := 0; y < size; y++ {
		for x := 0; x < size; x++ {
			x0, x1 := x*256/size, (x+1)*256/size
			y0, y1 := y*256/size, (y+1)*256/size
			var r, g, b, a uint64
			count := uint64((x1 - x0) * (y1 - y0))
			for sy := y0; sy < y1; sy++ {
				for sx := x0; sx < x1; sx++ {
					cr, cg, cb, ca := source.At(sx, sy).RGBA()
					r += uint64(cr)
					g += uint64(cg)
					b += uint64(cb)
					a += uint64(ca)
				}
			}
			c := color.NRGBA{A: uint8((a/count + 128) / 257)}
			if a > 0 {
				c.R = uint8((r*255 + a/2) / a)
				c.G = uint8((g*255 + a/2) / a)
				c.B = uint8((b*255 + a/2) / a)
			}
			out.SetNRGBA(x, y, c)
		}
	}
	return out
}

func makeIcon(source *image.NRGBA) ([]byte, error) {
	var frames [][]byte
	for _, size := range iconSizes {
		var frame bytes.Buffer
		if e := png.Encode(&frame, iconImage(source, size)); e != nil {
			return nil, e
		}
		frames = append(frames, frame.Bytes())
	}
	header := make([]byte, 6+16*len(frames))
	binary.LittleEndian.PutUint16(header[2:], 1)
	binary.LittleEndian.PutUint16(header[4:], uint16(len(frames)))
	offset := len(header)
	for i, frame := range frames {
		entry := header[6+i*16:]
		entry[0], entry[1] = byte(iconSizes[i]%256), byte(iconSizes[i]%256)
		binary.LittleEndian.PutUint16(entry[4:], 1)
		binary.LittleEndian.PutUint16(entry[6:], 32)
		binary.LittleEndian.PutUint32(entry[8:], uint32(len(frame)))
		binary.LittleEndian.PutUint32(entry[12:], uint32(offset))
		offset += len(frame)
	}
	out := header
	for _, frame := range frames {
		out = append(out, frame...)
	}
	return out, nil
}
