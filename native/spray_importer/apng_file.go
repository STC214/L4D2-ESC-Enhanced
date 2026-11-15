package main

import (
	"errors"
	"image"
	"io"
	"os"
	"path/filepath"
	"strings"
)

// Sniff only structural chunk headers. The actual parser re-reads the same
// file handle and checks all CRCs, including discarded animation payloads.
func fileHasAPNG(f *os.File, size int64) (bool, error) {
	var signature [8]byte
	if _, err := f.ReadAt(signature[:], 0); err != nil || string(signature[:]) != "\x89PNG\r\n\x1a\n" {
		return false, nil
	}
	for at, count := int64(8), 0; at+12 <= size && count < 100000; count++ {
		var header [8]byte
		if _, err := f.ReadAt(header[:], at); err != nil {
			return false, err
		}
		n := int64(be.Uint32(header[:]))
		if n > size-at-12 {
			return false, errors.New("PNG/APNG 块长度超过文件范围")
		}
		switch string(header[4:]) {
		case "acTL":
			return true, nil
		case "IDAT", "IEND":
			return false, nil
		}
		at += n + 12
	}
	return false, errors.New("PNG/APNG 头部截断或块数量超限")
}

func preparePNGFile(path string, options ...importOptions) (preparedTexture, error) {
	var result preparedTexture
	o := conversionOptions(options)
	f, err := os.Open(path)
	if err != nil {
		return result, err
	}
	defer f.Close()
	stat, err := f.Stat()
	if err != nil {
		return result, err
	}
	if !stat.Mode().IsRegular() {
		return result, errors.New("PNG/APNG 素材须为普通文件")
	}
	if stat.Size() > apngInputLimit {
		return result, errors.New("PNG/APNG 输入超过 1 GiB 流式处理上限")
	}
	animated := strings.EqualFold(filepath.Ext(path), ".apng")
	if !animated {
		animated, err = fileHasAPNG(f, stat.Size())
		if err != nil {
			return result, err
		}
	}
	if _, err = f.Seek(0, io.SeekStart); err != nil {
		return result, err
	}
	if animated {
		header, palette, frames, err := parseAPNGReader(&progressReader{reader: f, total: stat.Size(), options: o})
		if err != nil {
			return result, err
		}
		return convertAPNGFrames(header, palette, frames, o)
	}
	if stat.Size() > 32<<20 {
		return result, errors.New("静态 PNG 输入超过 32 MiB；动画 APNG 另走流式导入")
	}
	raw, err := io.ReadAll(io.LimitReader(f, (32<<20)+1))
	if err != nil {
		return result, err
	}
	if len(raw) > 32<<20 {
		return result, errors.New("静态图片输入超过 32 MiB")
	}
	img, err := loadImageSizeData(raw, masterSize)
	if err != nil {
		return result, err
	}
	return qualityTexture([]*image.NRGBA{img})
}
