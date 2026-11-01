"""Verify checkbox+commit pair, exact menu/FOV delta, replay and pair rollback."""

import difflib
import json
import shutil
import subprocess
import sys
import zipfile

from c_binary_switches import SWITCHES, CONTROL
from c_menu_consolidation import MENU, CFG, validate
from c_session_release import GAME, DLL, ROOT, OUTPUT, TARGETS, save, sha
from inspect_menu import blocks, fields
from review_c_switch_fix import probe
from vpk import read, write

WORK = ROOT / "reports/c_checkbox_bridge"
BASE = ROOT / "originals/C_before_checkbox_commit.vpk"
OLD_DLL = ROOT / "originals/CSessionDefaults_before_checkbox_commit.dll"
BASE_HASH = "32c0014408baadb5d63bcdd3738de9f98a8a636e63449d83122e1dad5c9bed2b"
OLD_DLL_HASH = "6dd4c6b297f22cc4264590588bc08dea3cd8e6d6f37d935bce6086810420c908"


def settings(files):
    props = [fields(block) for _, _, _, block in blocks(files[MENU].decode("utf-8-sig")) if fields(block).get("concommand")]
    return sorted(props, key=lambda item: (item["xpos"] == "r196", int(item["ypos"])))


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "probe":
        from pathlib import Path
        probe(Path(sys.argv[2]))
        return
    WORK.mkdir(parents=True, exist_ok=True)
    for target, source, digest in ((BASE, GAME / TARGETS["vpk"], BASE_HASH),
                                   (OLD_DLL, GAME / TARGETS["helper"], OLD_DLL_HASH)):
        if not target.exists():
            assert sha(source) == digest
            shutil.copyfile(source, target)
        assert sha(target) == digest
    before, after = read(BASE), read(OUTPUT)
    changed = {MENU, CFG}
    assert set(before) == set(after) and {key for key in before if before[key] != after[key]} == changed
    assert before[CFG].count(b"r_flashlightfov 165") == 1
    assert before[CFG].replace(b"r_flashlightfov 165", b"r_flashlightfov 114") == after[CFG]
    validate(after)
    old, new = settings(before), settings(after)
    assert [item["concommand"] for item in old] == [item["concommand"] for item in new]
    binary = [item for item in new if item["concommand"].lower() in SWITCHES]
    assert len(binary) == 10 and new[:10] == binary
    assert all(item["controlname"] == CONTROL and item["fieldname"] == "C_ESC_BOOL_" + item["concommand"].lower()
               for item in binary)
    build = json.loads((ROOT / "reports/c_session_plugin_build.json").read_text(encoding="utf-8"))
    assert build["helper_version"] == "1.3.1" and build["dll_sha256"] == sha(DLL)
    assert all(item["exit_status"] == 0 for item in build["records"])
    assert any("checkbox_bridge_test.exe" in " ".join(item["command"]) and "actual x86 hook/trampoline/unhook" in item["stdout"]
               for item in build["records"])
    diff = "".join("".join(difflib.unified_diff(before[path].decode("utf-8-sig").splitlines(True),
                                              after[path].decode("utf-8-sig").splitlines(True),
                                              fromfile="before/" + path, tofile="after/" + path))
                   for path in sorted(changed))
    (WORK / "menu.patch").write_text(diff, encoding="utf-8", newline="\n")
    patch = WORK / "patch.zip"
    manifest = {"baseline_sha256": BASE_HASH, "result_sha256": sha(OUTPUT), "changed": sorted(changed),
                "helper_before": OLD_DLL_HASH, "helper_after": sha(DLL)}
    with zipfile.ZipFile(patch, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("menu.patch", diff)
        for path in sorted(changed):
            archive.writestr(path, after[path])
        archive.write(DLL, "CSessionDefaults.dll")
    with zipfile.ZipFile(patch) as archive:
        assert archive.testzip() is None and json.loads(archive.read("manifest.json")) == manifest
        replay = dict(before)
        for path in changed:
            replay[path] = archive.read(path)
        assert archive.read("CSessionDefaults.dll") == DLL.read_bytes()
    replayed = WORK / "replayed.vpk"
    write(replayed, replay)
    assert read(replayed) == after and sha(replayed) == sha(OUTPUT)
    restored = WORK / "rollback" / OUTPUT.name
    restored.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BASE, restored)
    restored_dll = restored.parent / DLL.name
    shutil.copyfile(OLD_DLL, restored_dll)
    assert sha(restored) == BASE_HASH and read(restored) == before and sha(restored_dll) == OLD_DLL_HASH
    records = []
    for label, path in (("baseline", BASE), ("modified", OUTPUT)):
        command = [sys.executable, "-X", "utf8", "tools/review_c_checkbox_commit.py", "probe", str(path)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0
        records.append({"label": label, "command": command, "cwd": str(ROOT), "stdout": result.stdout,
                        "stderr": result.stderr, "exit_status": result.returncode})
    save(WORK / "verification.json", {"status": "CHECKBOX_COMMIT_PATCH_AND_PAIR_ROLLBACK_PASSED",
         "scope": "Native x86 bridge fixtures and static resource verification; NOT live game clicks",
         "records": records, "native_build": build, "unchanged_members": len(after) - len(changed),
         "artifacts": {str(path): sha(path) for path in (BASE, OLD_DLL, OUTPUT, DLL, patch, replayed, restored, restored_dll)}})
    print("PASS 10 scoped checkboxes + native commit/readback tests; settings order unchanged")
    print(f"PASS ESC menu and exact FOV 165 -> 114 CFG delta; {len(after) - len(changed)} other members unchanged; VPK/DLL patch and pair rollback reopened")
    print("RECORD", WORK / "verification.json")


if __name__ == "__main__":
    main()
