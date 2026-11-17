package main

import (
	"bytes"
	"errors"
	"strings"
	"syscall"
	"unicode/utf8"
	"unsafe"
)

const cProjectVPK = "【00】C_ESC_LED_血条和速度_TUMTaRA.vpk"
const diagnosticVPK = "CSP_Numbered_Test_Assets.vpk"

type addonToken struct {
	value      string
	start, end int
	brace      bool
}

func addonTokens(raw []byte) ([]addonToken, error) {
	if len(raw) > 8<<20 || bytes.IndexByte(raw, 0) >= 0 {
		return nil, errors.New("addonlist 编码或大小不受支持，原文件保留")
	}
	var out []addonToken
	legacyBytes := !utf8.Valid(raw)
	for at := 0; at < len(raw); {
		if len(out) >= 100000 {
			return nil, errors.New("addonlist 项目过多")
		}
		if at == 0 && bytes.HasPrefix(raw, []byte{239, 187, 191}) {
			at = 3
			continue
		}
		if raw[at] == ' ' || raw[at] == '\t' || raw[at] == '\n' || raw[at] == '\r' {
			at++
			continue
		}
		if at+1 < len(raw) && raw[at] == '/' && raw[at+1] == '/' {
			for at < len(raw) && raw[at] != '\n' {
				at++
			}
			continue
		}
		if at+1 < len(raw) && raw[at] == '/' && raw[at+1] == '*' {
			end := bytes.Index(raw[at+2:], []byte("*/"))
			if end < 0 {
				return nil, errors.New("addonlist 注释截断")
			}
			at += end + 4
			continue
		}
		start := at
		if raw[at] == '{' || raw[at] == '}' {
			out = append(out, addonToken{string(raw[at : at+1]), at, at + 1, true})
			at++
			continue
		}
		var value []byte
		if raw[at] == '"' {
			at++
			closed := false
			for at < len(raw) {
				c := raw[at]
				at++
				if legacyBytes && c >= 0x81 && c <= 0xfe && at < len(raw) && raw[at] >= 0x40 && raw[at] <= 0xfe && raw[at] != 0x7f {
					value = append(value, c, raw[at])
					at++
					continue
				}
				if c == '"' {
					closed = true
					break
				}
				if c == '\\' && at < len(raw) && (raw[at] == '"' || raw[at] == '\\') {
					c = raw[at]
					at++
				}
				value = append(value, c)
			}
			if !closed {
				return nil, errors.New("addonlist 引号截断")
			}
		} else {
			for at < len(raw) && !strings.ContainsRune(" \t\r\n{}\"", rune(raw[at])) {
				value = append(value, raw[at])
				at++
			}
		}
		if len(value) == 0 || len(out) > 100000 {
			return nil, errors.New("addonlist 项目异常或过多")
		}
		out = append(out, addonToken{string(value), start, at, false})
	}
	return out, nil
}

func addonKey(s string) string {
	b := []byte(strings.ReplaceAll(s, "\\", "/"))
	for i, c := range b {
		if c >= 'A' && c <= 'Z' {
			b[i] = c + 32
		}
	}
	return string(b)
}

// Match legacy CP936 keys without decoding/re-encoding unrelated addon bytes.
func legacyAddonName(name string) (string, error) {
	wide, err := syscall.UTF16FromString(name)
	if err != nil {
		return "", err
	}
	p := syscall.NewLazyDLL("kernel32.dll").NewProc("WideCharToMultiByte")
	var used uint32
	n, _, _ := p.Call(936, 0x400, uintptr(unsafe.Pointer(&wide[0])), uintptr(len(wide)-1), 0, 0, 0, uintptr(unsafe.Pointer(&used)))
	if n == 0 {
		return "", errors.New("addonlist 本地编码转换失败")
	}
	out := make([]byte, n)
	r, _, _ := p.Call(936, 0x400, uintptr(unsafe.Pointer(&wide[0])), uintptr(len(wide)-1), uintptr(unsafe.Pointer(&out[0])), n, 0, uintptr(unsafe.Pointer(&used)))
	if r != n || used != 0 {
		return "", errors.New("addonlist 项目名称不适用于本地编码")
	}
	return string(out), nil
}

// Install enables only the selector (and disables its diagnostic-only pack).
// Cleanup removes only the three exact project entries; unrelated bytes survive.
func patchProjectAddons(raw []byte, cleanup bool) ([]byte, error) {
	tokens, err := addonTokens(raw)
	if err != nil {
		return nil, err
	}
	if len(tokens) < 3 || !strings.EqualFold(tokens[0].value, "AddonList") || tokens[0].brace || !tokens[1].brace || !tokens[len(tokens)-1].brace || tokens[1].value != "{" || tokens[len(tokens)-1].value != "}" {
		return nil, errors.New("addonlist 根结构异常")
	}
	type edit struct {
		start, end int
		data       []byte
	}
	var edits []edit
	seen := map[string]bool{}
	projectSeen := map[string]bool{}
	names := map[string]string{}
	for _, name := range []string{vpkName, cProjectVPK, diagnosticVPK} {
		names[addonKey(name)] = name
	}
	legacy, err := legacyAddonName(cProjectVPK)
	if err != nil {
		return nil, err
	}
	names[addonKey(legacy)] = cProjectVPK
	found := false
	foundDiagnostic := false
	for i := 2; i < len(tokens)-1; i += 2 {
		if i+1 >= len(tokens)-1 || tokens[i].brace || tokens[i+1].brace {
			return nil, errors.New("addonlist 不是平面键值表")
		}
		key := addonKey(tokens[i].value)
		if seen[key] {
			return nil, errors.New("addonlist 含重复项目，原文件保留")
		}
		seen[key] = true
		name := names[key]
		if name == "" {
			continue
		}
		if projectSeen[name] {
			return nil, errors.New("addonlist 同一项目存在多种编码重复项")
		}
		projectSeen[name] = true
		if name == vpkName {
			found = true
		}
		if name == diagnosticVPK {
			foundDiagnostic = true
		}
		if cleanup {
			edits = append(edits, edit{tokens[i].start, tokens[i+1].end, nil})
		} else if name == vpkName || name == diagnosticVPK {
			state := []byte("\"1\"")
			if name == diagnosticVPK {
				state = []byte("\"0\"")
			}
			edits = append(edits, edit{tokens[i+1].start, tokens[i+1].end, state})
		}
	}
	if !cleanup && !found {
		newline := "\n"
		if bytes.Contains(raw, []byte("\r\n")) {
			newline = "\r\n"
		}
		at := tokens[len(tokens)-1].start
		edits = append(edits, edit{at, at, []byte("\t\"" + vpkName + "\"\t\"1\"" + newline)})
	}
	if !cleanup && !foundDiagnostic {
		newline := "\n"
		if bytes.Contains(raw, []byte("\r\n")) {
			newline = "\r\n"
		}
		at := tokens[len(tokens)-1].start
		edits = append(edits, edit{at, at, []byte("\t\"" + diagnosticVPK + "\"\t\"0\"" + newline)})
	}
	result := append([]byte{}, raw...)
	for i := len(edits) - 1; i >= 0; i-- {
		e := edits[i]
		next := append([]byte{}, result[:e.start]...)
		next = append(next, e.data...)
		result = append(next, result[e.end:]...)
	}
	return result, nil
}
