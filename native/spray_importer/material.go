package main

import (
	"errors"
	"strings"
)

type materialToken struct {
	Text  string
	Brace bool
}

// Read bounded KeyValues tokens, preserving quoted paths and ignoring comments.
// Do not search for keys inside values, comments or nested proxy blocks.
func materialTexture(data []byte) (string, error) {
	bad := errors.New("喷漆材质结构损坏、过于复杂或含歧义参数")
	if len(data) > 1<<20 {
		return "", bad
	}
	s := strings.TrimPrefix(string(data), "\xef\xbb\xbf")
	var tokens []materialToken
	for i := 0; i < len(s); {
		if len(tokens) >= 16384 || s[i] == 0 {
			return "", bad
		}
		if s[i] <= ' ' {
			i++
			continue
		}
		if strings.HasPrefix(s[i:], "//") {
			if end := strings.IndexByte(s[i:], '\n'); end >= 0 {
				i += end + 1
				continue
			}
			break
		}
		if strings.HasPrefix(s[i:], "/*") {
			end := strings.Index(s[i+2:], "*/")
			if end < 0 {
				return "", bad
			}
			i += end + 4
			continue
		}
		if s[i] == '{' || s[i] == '}' {
			tokens = append(tokens, materialToken{string(s[i]), true})
			i++
			continue
		}
		if s[i] == '"' {
			i++
			var value strings.Builder
			for i < len(s) && s[i] != '"' {
				if s[i] == 0 || s[i] == '\r' || s[i] == '\n' {
					return "", bad
				}
				if s[i] == '\\' && i+1 < len(s) && s[i+1] == '"' {
					i++
				}
				value.WriteByte(s[i])
				i++
			}
			if i == len(s) {
				return "", bad
			}
			i++
			tokens = append(tokens, materialToken{Text: value.String()})
			continue
		}
		start := i
		for i < len(s) && s[i] > ' ' && s[i] != '{' && s[i] != '}' && !strings.HasPrefix(s[i:], "//") && !strings.HasPrefix(s[i:], "/*") {
			if s[i] == '"' {
				return "", bad
			}
			i++
		}
		tokens = append(tokens, materialToken{Text: s[start:i]})
	}
	if len(tokens) < 3 || tokens[0].Brace || tokens[0].Text == "" || !tokens[1].Brace || tokens[1].Text != "{" {
		return "", bad
	}
	at := 2
	reference := ""
	var block func(int) error
	block = func(depth int) error {
		if depth > 32 {
			return bad
		}
		for at < len(tokens) {
			key := tokens[at]
			at++
			if key.Brace {
				if key.Text == "}" {
					return nil
				}
				return bad
			}
			if key.Text == "" || at >= len(tokens) {
				return bad
			}
			value := tokens[at]
			at++
			isBase := depth == 0 && strings.EqualFold(key.Text, "$basetexture")
			if value.Brace {
				if value.Text != "{" || isBase {
					return bad
				}
				if err := block(depth + 1); err != nil {
					return err
				}
			} else if isBase {
				if reference != "" || value.Text == "" {
					return bad
				}
				reference = value.Text
			}
		}
		return bad
	}
	if err := block(0); err != nil || at != len(tokens) || reference == "" {
		return "", bad
	}
	return reference, nil
}
