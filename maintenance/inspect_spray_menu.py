"""Read native spray-menu resources and binary references; never write game files."""

import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from trace_flashlight_native import PE

GAME = Path(r"E:\SteamLibrary\steamapps\common\Left 4 Dead 2")
OUT = ROOT / "reports/spray_menu_native"


def selected(path):
    raw = path.read_bytes()
    signature, version, size = struct.unpack_from("<III", raw)
    assert signature == 0x55AA1234 and version in (1, 2)
    header = 12 if version == 1 else 28
    tree, at = raw[header:header + size], 0

    def string():
        nonlocal at
        end = tree.index(b"\0", at)
        value = tree[at:end].decode("utf-8", errors="surrogateescape")
        at = end + 1
        return value

    while ext := string():
        while folder := string():
            while name := string():
                crc, preload, archive, offset, length, term = struct.unpack_from("<IHHIIH", tree, at)
                at += 18
                content = tree[at:at + preload]
                at += preload
                assert term == 0xFFFF
                key = (folder + "/" if folder != " " else "") + name + "." + ext
                if ext not in ("res", "txt") or not any(word in name.lower() for word in ("spray", "multiplayer")):
                    continue
                if length:
                    source = path if archive == 0x7FFF else path.with_name(path.name.replace("_dir.vpk", f"_{archive:03}.vpk"))
                    with source.open("rb") as stream:
                        stream.seek(header + size + offset if archive == 0x7FFF else offset)
                        content += stream.read(length)
                assert zlib.crc32(content) == crc and len(content) == preload + length
                yield key, content


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"scope": "Native game resources and gameui.dll only; no add-on images; static inspection", "resources": [], "strings": {}}
    for layer in ("update", "left4dead2_dlc3", "left4dead2_dlc2", "left4dead2_dlc1", "left4dead2", "hl2"):
        pak = GAME / layer / "pak01_dir.vpk"
        if not pak.exists():
            continue
        for key, content in selected(pak):
            output = OUT / layer / key
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(content)
            report["resources"].append(dict(pak=str(pak), member=key, sha256=hashlib.sha256(content).hexdigest(), output=str(output)))
            print(layer, key, len(content))
    pe = PE(GAME / "bin/gameui.dll")
    report["binary"] = dict(path=str(pe.path), sha256=hashlib.sha256(pe.raw).hexdigest())
    assert report["binary"]["sha256"] == "321ec9b5865582330af61e81eb347da31cc213cc6c95b80d6d98170b8a5fbb40", "Recheck addresses for a different binary"
    listing = pe.listing(0x1006aec4, before=0, after=0x1006b311 - 0x1006aec4)
    assert "1006af14: cmp dword ptr [esi + 0x2c8], 0x10" in listing
    assert "1006b092: cmp dword ptr [esi + 0x2c8], 0x10" in listing
    assert "1006b2a5: cmp ebx, 0x11" in listing
    report["manifest_population"] = listing
    dropdown = (OUT / "left4dead2/resource/ui/l4d360ui/dropdownspraypaint.res").read_text(encoding="utf-8-sig")
    names = re.findall(r'"fieldName"\s+"(BtnSpraypaint[^"\n]+)"', dropdown)
    assert names == ["BtnSpraypaint" + chr(0x30 + i) for i in range(17)]
    report["findings"] = dict(manifest_entry_limit=16, extra_custom_logo_slot=1, resource_buttons=names,
                              scrolling="Fixed FlyoutMenu resource without a scroll control; mouse-wheel behavior not tested live",
                              boundary="Native menu; unrelated add-on UI overrides not audited")
    for label in ("scripts/sprays_manifest.txt", "sprays_manifest", "DrpSpraypaint", "SpraypaintList", "BtnBrowseSpraypaint"):
        at = pe.raw.find(label.encode() + b"\0")
        if at < 0:
            continue
        va = pe.va(at)
        report["strings"][label] = dict(va=hex(va), refs={hex(ref): pe.listing(ref, before=100, after=350) for ref in pe.refs(va)})
    target = OUT / "inspection.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert json.loads(target.read_text(encoding="utf-8")) == report
    print("REPORT", target)


if __name__ == "__main__":
    main()
