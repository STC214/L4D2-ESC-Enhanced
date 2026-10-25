"""Bounded, read-only queries against the preserved Evolved DLL."""

import argparse
import json
import re
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from release_paths import ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exports", action="store_true")
    parser.add_argument("--disasm", nargs=2)
    parser.add_argument("--strings", nargs=2)
    parser.add_argument("--find")
    parser.add_argument("--path")
    parser.add_argument("--words", nargs=2)
    parser.add_argument("--wide", nargs=2)
    parser.add_argument("--settings-table", action="store_true")
    args = parser.parse_args()
    from pathlib import Path
    path = Path(args.path) if args.path else ROOT / "research/workshop_3785109042/unpacked/bin/neko/plugins/L4D2Evolved.dll"
    data = path.read_bytes()
    u32 = lambda at: struct.unpack_from("<I", data, at)[0]
    pe = u32(0x3C)
    opt = pe + 24
    base = u32(opt + 28)
    table = opt + struct.unpack_from("<H", data, pe + 20)[0]
    sections = [struct.unpack_from("<IIII", data, table + i * 40 + 8)
                for i in range(struct.unpack_from("<H", data, pe + 6)[0])]

    def offset(va):
        for vs, rva, size, raw in sections:
            if base + rva <= va < base + rva + max(vs, size):
                return raw + va - base - rva
        raise ValueError(hex(va))

    def address(at):
        for _, rva, size, raw in sections:
            if raw <= at < raw + size:
                return base + rva + at - raw
        return 0

    if args.settings_table:
        def entry(va):
            try:
                at = offset(va)
                s = offset(u32(at))
                key = data[s:data.index(b"\0", s)].decode("ascii")
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]+", key) or u32(at + 4) > 8:
                    return None
                label_at = offset(u32(at + 8))
                end = label_at
                while data[end:end + 2] != b"\0\0":
                    end += 2
                label = data[label_at:end].decode("utf-16-le")
                return {"va": hex(va), "key": key, "type": u32(at + 4), "label": label}
            except (ValueError, UnicodeError, struct.error):
                return None
        first = 0x103fee90
        while entry(first - 40):
            first -= 40
        at = first
        rows = []
        while row := entry(at):
            rows.append(row)
            at += 40
        print("TABLE_RANGE", hex(first), hex(at), "COUNT", len(rows))
        report = {"start": hex(first), "end": hex(at), "rows": rows}
        target = ROOT / "research/workshop_3785109042/settings_table.json"
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))

    if args.exports:
        at = offset(base + u32(opt + 96))
        functions, names, ordinals = (offset(base + u32(at + n)) for n in (28, 32, 36))
        for i in range(u32(at + 24)):
            s = offset(base + u32(names + i * 4))
            name = data[s:data.index(b"\0", s)].decode("ascii")
            ordinal = struct.unpack_from("<H", data, ordinals + 2 * i)[0]
            print(name, hex(base + u32(functions + 4 * ordinal)))
    if args.find:
        for encoding in ("utf-8", "utf-16-le"):
            needle = args.find.encode(encoding)
            at = data.find(needle)
            while at >= 0:
                print(encoding, hex(address(at)), "file=" + hex(at),
                      repr(data[max(0, at - 30):at + 110].decode(encoding, errors="replace")))
                at = data.find(needle, at + len(needle))
    if args.words:
        va, count = (int(v, 0) for v in args.words)
        assert 0 < count <= 512
        at = offset(va)
        for i in range(count):
            print(hex(va + i * 4), hex(u32(at + i * 4)))
    if args.wide:
        va, count = (int(v, 0) for v in args.wide)
        assert 0 < count <= 16384
        at = offset(va)
        print(data[at:at + count].decode("utf-16-le", errors="replace").split("\0")[0])
    for field in ("disasm", "strings"):
        selected = getattr(args, field)
        if not selected:
            continue
        va, count = (int(v, 0) for v in selected)
        assert 0 < count <= 16384
        at = offset(va)
        if field == "strings":
            for part in data[at:at + count].split(b"\0"):
                if part:
                    print(hex(address(at)), repr(part.decode("utf-8", errors="replace")))
                at += len(part) + 1
        else:
            for ins in Cs(CS_ARCH_X86, CS_MODE_32).disasm(data[at:at + count], va):
                print(f"{ins.address:08x}: {ins.mnemonic} {ins.op_str}")


if __name__ == "__main__":
    main()
