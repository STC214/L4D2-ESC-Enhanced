"""Read-only archive/config/PE inspection; never execute downloaded payloads."""

import hashlib
import json
import re
import struct

from release_paths import ROOT, OUTPUT
from vpk import read


BASE = ROOT / "research/workshop_3785109042"
UNPACKED = BASE / "unpacked"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pe_info(path):
    data = path.read_bytes()
    assert data[:2] == b"MZ"
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[pe:pe + 4] == b"PE\0\0"
    machine, sections = struct.unpack_from("<HH", data, pe + 4)
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    magic = struct.unpack_from("<H", data, optional)[0]
    section_table = optional + optional_size
    section_rows = []
    for i in range(sections):
        at = section_table + 40 * i
        virtual_size, rva, raw_size, raw_at = struct.unpack_from("<IIII", data, at + 8)
        section_rows.append((rva, max(virtual_size, raw_size), raw_at))

    def offset(rva):
        for start, size, raw_at in section_rows:
            if start <= rva < start + size:
                return raw_at + rva - start
        raise ValueError("Unmapped RVA")

    def cstr(at):
        return data[at:data.index(b"\0", at)].decode("ascii", errors="replace")

    directory = optional + (96 if magic == 0x10B else 112)
    import_rva = struct.unpack_from("<I", data, directory + 8)[0]
    imports = []
    if import_rva:
        at = offset(import_rva)
        while any(data[at:at + 20]):
            name_rva = struct.unpack_from("<I", data, at + 12)[0]
            imports.append(cstr(offset(name_rva)))
            at += 20
    strings = [s.decode("ascii") for s in re.findall(rb"[\x20-\x7e]{5,}", data)]
    selected = sorted(set(s for s in strings if any(k.lower() in s.lower() for k in (
        "config.txt", "config.sample", "-noevo", "NoHmdMinimapToggleKey",
        "NoHmdConfigMenuKey", "L4D2Evolved.dll", "L4d2evomodel.dll", "Evolved/", "Evolved\\",
    )) and len(s) < 400))
    return {"path": path.relative_to(UNPACKED).as_posix(), "sha256": sha(path),
            "machine": hex(machine), "architecture": "x86" if machine == 0x14C else hex(machine),
            "pe_optional_magic": hex(magic), "imports": imports,
            "selected_ascii_strings_not_execution_evidence": selected}


def main():
    c_before = sha(OUTPUT)
    record = json.loads((BASE / "extraction_verification.json").read_text(encoding="utf-8"))
    for member in record["members"]:
        assert sha(UNPACKED / member["path"]) == member["sha256"]
    sample = (UNPACKED / "Evolved/config.sample").read_text(encoding="utf-8-sig")
    active, commented = {}, {}
    for line in sample.splitlines():
        line = line.strip()
        if "=" not in line:
            continue
        target = commented if line.startswith("#") else active
        key, value = line.lstrip("#").split("=", 1)
        target[key] = value
    bundled = []
    c_paths = {n.lower(): n for n in read(OUTPUT)}
    for path in sorted((UNPACKED / "left4dead2/addons").glob("*.vpk")):
        members = read(path)
        common = sorted(n for n in members if n.lower() in c_paths)
        collisions = [{"path": n, "same_bytes": members[n] == read_c[c_paths[n.lower()]]}
                      for n in common] if (read_c := read(OUTPUT)) else []
        bundled.append({"path": path.relative_to(UNPACKED).as_posix(), "sha256": sha(path),
                        "crc_verified_members": len(members), "members": sorted(members),
                        "shared_paths_with_C": collisions})
    report = {"scope": "read-only static inspection; no DLL/BAT/EXE or game execution",
              "version": (UNPACKED / "Evolved/version.txt").read_text(encoding="utf-8-sig"),
              "native_modules": [pe_info(p) for p in sorted(UNPACKED.rglob("*.dll"))],
              "active_sample_settings_not_proven_runtime_defaults": active,
              "commented_sample_settings_not_active": commented,
              "bundled_addons": bundled, "current_C_sha256": c_before}
    assert sha(OUTPUT) == c_before
    target = BASE / "static_inspection.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert json.loads(target.read_text(encoding="utf-8")) == report
    print("VERSION " + report["version"])
    for module in report["native_modules"]:
        print("PE " + module["architecture"] + " " + module["path"])
        print("STRINGS " + json.dumps(module["selected_ascii_strings_not_execution_evidence"], ensure_ascii=False))
    for addon in bundled:
        print("BUNDLED " + addon["path"] + " members=" + str(addon["crc_verified_members"]))
        print("C_COMMON " + json.dumps(addon["shared_paths_with_C"], ensure_ascii=False))
    print("PASS extracted file hashes, bundled VPK CRCs, and unchanged C " + c_before)
    print("REPORT " + str(target))


if __name__ == "__main__":
    main()
