"""Read-only deployment assessment for the explicitly selected local game.

Writes reports only inside this project. Never loads DLLs or starts the game.
"""

import hashlib
import json
from pathlib import Path
import re
import struct

from release_paths import ROOT, OUTPUT


GAME = Path(r"E:\SteamLibrary\steamapps\common\Left 4 Dead 2")
STUDY = ROOT / "research/workshop_3785109042"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_info(path):
    if not path.is_file():
        return {"exists": False}
    raw = path.read_bytes()
    result = {"exists": True, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    if raw[:2] == b"MZ":
        pe = struct.unpack_from("<I", raw, 0x3C)[0]
        assert raw[pe:pe + 4] == b"PE\0\0"
        result["pe_machine"] = hex(struct.unpack_from("<H", raw, pe + 4)[0])
    return result


def text(path):
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeError:
            pass
    return raw.decode("utf-8", errors="replace")


def exported_names(path):
    raw = path.read_bytes()
    assert raw[:2] == b"MZ"
    pe = struct.unpack_from("<I", raw, 0x3C)[0]
    count = struct.unpack_from("<H", raw, pe + 6)[0]
    opt = pe + 24
    size = struct.unpack_from("<H", raw, pe + 20)[0]
    magic = struct.unpack_from("<H", raw, opt)[0]
    table = opt + size

    def off(rva):
        for i in range(count):
            vs, va, rs, rp = struct.unpack_from("<IIII", raw, table + i * 40 + 8)
            if va <= rva < va + max(vs, rs):
                return rp + rva - va
        raise ValueError("Export RVA outside sections")

    export_rva = struct.unpack_from("<I", raw, opt + (96 if magic == 0x10B else 112))[0]
    if not export_rva:
        return []
    at = off(export_rva)
    names_count = struct.unpack_from("<I", raw, at + 24)[0]
    names_rva = struct.unpack_from("<I", raw, at + 32)[0]
    assert names_count < 100000
    names_at = off(names_rva)
    names = []
    for i in range(names_count):
        start = off(struct.unpack_from("<I", raw, names_at + 4 * i)[0])
        names.append(raw[start:raw.index(b"\0", start)].decode("ascii"))
    return names


def main():
    assert GAME.is_dir() and (GAME / "left4dead2.exe").is_file()
    watched = ["left4dead2.exe", "bin/left4neko.dll", "bin/neko/plugins/l4n_plugin.h",
               "winmm.dll", "bin/winmm.dll", "d3d9.dll", "dxgi.dll", "dxvk_d3d9.dll",
               "bin/dxvk_d3d9.dll", "Evolved/config.txt", "Evolved/config2.txt",
               "Evolved/version.txt", "left4dead2/cfg/video.txt", "left4dead2/gameinfo.txt",
               "left4dead2/cfg/config.cfg", "left4dead2/cfg/autoexec.cfg", "left4dead2/addonlist.txt",
               "left4dead2 no-insecure.bat", "readme_l4n.txt"]
    package = json.loads((STUDY / "extraction_verification.json").read_text(encoding="utf-8"))
    watched = sorted(set(watched) | {m["path"] for m in package["members"]})
    before = {n: file_info(GAME / n) for n in watched}
    footprints = []
    for row in package["members"]:
        local = before[row["path"]]
        footprints.append({"path": row["path"], "package_sha256": row["sha256"],
                           "local": local, "action": "add" if not local["exists"] else
                           "already-identical" if local["sha256"] == row["sha256"] else "review-before-overwrite"})
    config_files = []
    for directory in (GAME / "left4dead2/neko", GAME / "bin/neko"):
        if directory.is_dir():
            for path in sorted(directory.rglob("*")):
                if path.is_file() and path.suffix.lower() in (".vdf", ".ini", ".cfg", ".json", ".txt") and path.stat().st_size < 256000:
                    config_files.append(path)
    # Keep only the selected configuration tree, not unrelated personal/Steam files.
    configs = {p.relative_to(GAME).as_posix(): {"sha256": digest(p), "text": text(p)} for p in config_files}
    readme = text(GAME / "readme_l4n.txt").splitlines()
    snippets = []
    pattern = re.compile(r"l4nplugin|plugins|插件系统|插件接口|加载.*模块|三方模块|dxvk_d3d9|启动项.*vulkan", re.I)
    selected = set()
    for i, line in enumerate(readme):
        if pattern.search(line):
            selected.update(range(max(0, i - 2), min(len(readme), i + 5)))
    for i in sorted(selected):
        snippets.append({"line": i + 1, "text": readme[i]})
    logs = {}
    for name in ("left4dead2_d3d9.log", "logging_system.log"):
        path = GAME / name
        if path.is_file():
            rows = text(path).splitlines()
            logs[name] = {"bytes": path.stat().st_size,
                          "matches": [{"line": i + 1, "text": line} for i, line in enumerate(rows)
                                      if re.search(r"L4N|left4neko|Evolved|DXVK|Vulkan|Device name|plugin|Command.?line", line, re.I)][:80]}
    installed_c = GAME / "left4dead2/addons" / OUTPUT.name
    c = {"path": str(installed_c), "local": file_info(installed_c), "project": file_info(OUTPUT)}
    runtime = {name: file_info(Path(r"C:\Windows\SysWOW64") / name)
               for name in ("MSVCP140.dll", "VCRUNTIME140.dll", "ucrtbase.dll")}
    symbols = {name: exported_names(STUDY / "unpacked" / name) for name in (
        "bin/neko/plugins/L4D2Evolved.dll", "bin/neko/plugins/L4d2evomodel.dll")}
    bindings = {}
    for name in ("left4dead2/cfg/config.cfg", "left4dead2/cfg/autoexec.cfg", "left4dead2/addonlist.txt"):
        path = GAME / name
        if path.is_file():
            bindings[name] = [{"line": i + 1, "text": line} for i, line in enumerate(text(path).splitlines())
                              if re.search(r'bind\s+"?(F[4-8]|p|alt|ctrl|m|\\)"?\s|exec\s|net_graph|crosshair|l4n_|3785109042|C_ESC', line, re.I)]
    workshop = GAME / "left4dead2/addons/workshop"
    addon_names = [p.name for p in sorted((GAME / "left4dead2/addons").glob("*.vpk"))]
    candidate_names = [p.name for p in sorted(workshop.glob("*")) if re.search(r"3785109042|3558049615|3576501343|638169501|3230782214|2256147202|469986973", p.name)] if workshop.is_dir() else []
    after = {n: file_info(GAME / n) for n in watched}
    assert before == after, "Selected game inputs changed during read-only inspection"
    assert all(digest(GAME / n) == v["sha256"] for n, v in configs.items())
    report = {"scope": "read-only on selected game paths/configuration; no installs, binary execution, or Steam account inspection",
              "game_root": str(GAME), "package_version": "1.2.5", "package_install_footprints": footprints,
              "selected_game_files": before, "configuration_snapshots": configs, "local_readme_evidence": snippets,
              "historical_logs_not_live_state": logs, "installed_C": c, "x86_runtime_file_presence_only": runtime,
              "evolved_plugin_export_names": symbols, "selected_bindings_and_addon_settings": bindings,
              "local_addon_filenames_not_full_conflict_scan": addon_names,
              "selected_workshop_filenames": candidate_names, "game_write_operations": 0,
              "input_hashes_unchanged_at_end": True}
    dest = STUDY / "local_game_assessment.json"
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert json.loads(dest.read_text(encoding="utf-8")) == report
    for row in footprints:
        print(row["action"], row["path"])
    print("CONFIG_FILES " + json.dumps(list(configs), ensure_ascii=False))
    print("RUNTIME " + json.dumps(runtime, ensure_ascii=False))
    print("C_IDENTICAL " + str(c["local"].get("sha256") == c["project"].get("sha256")))
    print("EXPORTS " + json.dumps(symbols, ensure_ascii=False))
    print("BINDINGS " + json.dumps(bindings, ensure_ascii=False))
    print("PASS selected game/config input hashes unchanged; game writes=0")
    print("REPORT " + str(dest))


if __name__ == "__main__":
    main()
