"""Inspect KeyValues controls without discarding duplicate conditional keys."""

import re
from pathlib import Path


TOKEN = re.compile(r'//[^\n]*|"(?:\\.|[^"\\])*"|\[[^\]]*\]|[{}]|[^\s{}"]+')


def blocks(text):
    tokens = [m for m in TOKEN.finditer(text) if not m[0].startswith("//")]
    depth = 0
    result = []
    for i, token in enumerate(tokens):
        if token[0] == "{":
            depth += 1
            if depth == 2:
                previous = i - 1
                while tokens[previous][0].startswith("["):
                    previous -= 1
                start = tokens[previous].start()
                name = tokens[previous][0].strip('"')
        elif token[0] == "}":
            if depth == 2:
                result.append((name, start, token.end(), text[start:token.end()]))
            depth -= 1
    assert depth == 0
    return result


def fields(block):
    tokens = [m[0] for m in TOKEN.finditer(block) if not m[0].startswith("//")]
    result = {}
    depth = 0
    consumed_value = -1
    for i, token in enumerate(tokens):
        if i == consumed_value:
            continue
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
        elif depth == 1 and token.startswith('"'):
            if i + 1 < len(tokens) and tokens[i + 1].startswith('"'):
                result.setdefault(token.strip('"').lower(), tokens[i + 1].strip('"'))
                consumed_value = i + 1
    return result


if __name__ == "__main__":
    for label in ("A", "B"):
        path = Path("extracted") / label / "resource/ui/l4d360ui/ingamemainmenu.res"
        print("\n", label)
        for name, _, _, block in blocks(path.read_text(encoding="utf-8-sig")):
            f = fields(block)
            labels = re.findall(r'"labeltext"\s+"([^"\n]*)"', block, re.I)
            print(name, f.get("controlname"), f.get("visible"),
                  f.get("xpos"), f.get("ypos"), f.get("wide"), f.get("tall"),
                  f.get("concommand", ""), f.get("minvalue", ""),
                  f.get("maxvalue", ""), "/".join(labels))
