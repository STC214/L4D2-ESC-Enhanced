"""Read-only x86 string/immediate-reference trace for Evolved map UI/config."""

import hashlib
import json
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM
from release_paths import ROOT


BASE = ROOT / "research/workshop_3785109042"
DLL = BASE / "unpacked/bin/neko/plugins/L4D2Evolved.dll"


def main():
    data = DLL.read_bytes()
    assert hashlib.sha256(data).hexdigest() == "05819c701943781c9d7868502f7926fbfa763b600be4bfe8c88fa3b4892fcd6d"
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt = pe + 24
    table = opt + struct.unpack_from("<H", data, pe + 20)[0]
    image_base = struct.unpack_from("<I", data, opt + 28)[0]
    sections = []
    for i in range(count):
        at = table + 40 * i
        name = data[at:at + 8].split(b"\0")[0].decode()
        vs, va, size, raw = struct.unpack_from("<IIII", data, at + 8)
        sections.append({"name": name, "va": image_base + va, "size": size, "raw": raw})
    strings = {}
    terms = ("minimap", "navigation", "地图", "导航", "show map", "config.txt", "config2.txt")
    for section in sections:
        if section["name"] not in (".rdata", ".data"):
            continue
        at, end = section["raw"], section["raw"] + section["size"]
        while at < end:
            stop = data.find(b"\0", at, end)
            if stop < 0:
                break
            raw = data[at:stop]
            try:
                value = raw.decode("utf-8")
            except UnicodeError:
                value = ""
            if 3 <= len(value) <= 500 and any(t in value.lower() for t in terms):
                va = section["va"] + at - section["raw"]
                strings[va] = {"va": hex(va), "file_offset": at, "text": value, "references": []}
            at = stop + 1
    text = next(s for s in sections if s["name"] == ".text")
    engine = Cs(CS_ARCH_X86, CS_MODE_32)
    engine.detail = True
    engine.skipdata = True
    instructions = list(engine.disasm(data[text["raw"]:text["raw"] + text["size"]], text["va"]))
    for i, ins in enumerate(instructions):
        if ins.id == 0:
            continue
        matches = {op.imm & 0xFFFFFFFF for op in ins.operands if op.type == X86_OP_IMM} & strings.keys()
        for va in matches:
            context = [f"{row.address:08x}: {row.mnemonic} {row.op_str}" for row in instructions[max(0, i - 10):i + 27]]
            strings[va]["references"].append({"instruction": hex(ins.address), "context": context})
    report = {"scope": "static x86 direct-immediate references; not all computed references or runtime behavior",
              "dll_sha256": hashlib.sha256(data).hexdigest(), "image_base": hex(image_base),
              "strings": list(strings.values())}
    target = BASE / "minimap_code_trace.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert json.loads(target.read_text(encoding="utf-8")) == report
    lines = []
    for row in strings.values():
        lines.append(row["va"] + " " + row["text"])
        for ref in row["references"]:
            lines.extend(ref["context"])
            lines.append("")
    listing = BASE / "minimap_code_trace.txt"
    listing.write_text("\n".join(lines), encoding="utf-8")
    for row in strings.values():
        print(row["va"], row["text"], "refs=" + str(len(row["references"])))
    print("TRACE " + str(listing))


if __name__ == "__main__":
    main()
