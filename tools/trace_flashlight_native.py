"""Bounded read-only PE/x86 flashlight CVar and consumer investigation."""

import argparse
import hashlib
import json
from pathlib import Path
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from c_session_release import ROOT, GAME, save

OUT = ROOT / "reports/flashlight_native"


class PE:
    def __init__(self, path):
        self.path = path
        self.raw = path.read_bytes()
        raw = self.raw
        pe = struct.unpack_from("<I", raw, 0x3c)[0]
        opt = pe + 24
        assert struct.unpack_from("<H", raw, pe + 4)[0] == 0x14c
        self.base = struct.unpack_from("<I", raw, opt + 28)[0]
        table = opt + struct.unpack_from("<H", raw, pe + 20)[0]
        self.sections = []
        for i in range(struct.unpack_from("<H", raw, pe + 6)[0]):
            at = table + i * 40
            name = raw[at:at + 8].split(b"\0")[0].decode()
            vs, rva, size, offset = struct.unpack_from("<IIII", raw, at + 8)
            self.sections.append((name, self.base + rva, size, offset))
        self.md = Cs(CS_ARCH_X86, CS_MODE_32)
        self.md.skipdata = True

    def va(self, offset):
        for _, address, size, start in self.sections:
            if start <= offset < start + size:
                return address + offset - start
        raise ValueError(offset)

    def offset(self, va):
        for _, address, size, start in self.sections:
            if address <= va < address + size:
                return start + va - address
        raise ValueError(hex(va))

    def refs(self, va):
        needle = struct.pack("<I", va)
        result = []
        for name, address, size, start in self.sections:
            if name != ".text":
                continue
            at = self.raw.find(needle, start, start + size)
            while at >= 0:
                result.append(self.va(at))
                at = self.raw.find(needle, at + 1, start + size)
        return result

    def listing(self, va, before=48, after=100):
        at = self.offset(va)
        start = max(0, at - before)
        boundary = self.raw.rfind(b"\xcc", start, at)
        if boundary >= 0:
            start = boundary + 1
        return [f"{address:08x}: {mnemonic} {operands}" for address, _, mnemonic, operands in
                self.md.disasm_lite(self.raw[start:at + after], self.va(start))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", default="left4dead2/bin/client.dll")
    parser.add_argument("--address", action="append", default=[])
    parser.add_argument("--refs", action="append", default=[])
    parser.add_argument("--after", type=int, default=120)
    parser.add_argument("--fields", action="store_true")
    args = parser.parse_args()
    path = GAME / args.module
    assert path.resolve().is_relative_to(GAME.resolve())
    pe = PE(path)
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"path": str(path), "sha256": hashlib.sha256(pe.raw).hexdigest(),
              "image_base": hex(pe.base), "strings": {}, "addresses": {}, "refs": {}}
    if not args.address and not args.refs and not args.fields:
        for needle in ("r_flashlightconstant", "r_flashlightlinear", "r_flashlightquadratic", "r_flashlightfar",
                       "UpdateDefaultFlashlightState"):
            at = pe.raw.find(needle.encode() + b"\0")
            assert at >= 0, needle
            va = pe.va(at)
            refs = pe.refs(va)
            report["strings"][needle] = {"va": hex(va), "refs": {hex(r): pe.listing(r) for r in refs}}
    for address in args.address:
        report["addresses"][address] = pe.listing(int(address, 0), before=0, after=args.after)
    for address in args.refs:
        report["refs"][address] = {hex(r): pe.listing(r, after=args.after) for r in pe.refs(int(address, 0))}
    if args.fields:
        section = next(s for s in pe.sections if s[0] == ".text")
        rows = list(pe.md.disasm_lite(pe.raw[section[3]:section[3] + section[2]], section[1]))
        report["field_candidates"] = {}
        for i, row in enumerate(rows):
            if row[2] in ("movss", "fld") and "+ 0x34]" in row[3]:
                nearby = rows[max(0, i - 14):i + 25]
                if any("+ 0x30]" in r[3] for r in nearby):
                    report["field_candidates"][hex(row[0])] = [
                        f"{a:08x}: {m} {o}" for a, _, m, o in nearby]
    suffix = "_".join(args.address + args.refs) or ("fields" if args.fields else "cvars")
    if args.refs:
        suffix = "refs_" + suffix
    target = OUT / (path.stem + "_" + suffix + ".json")
    save(target, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("REPORT", target)


if __name__ == "__main__":
    main()
