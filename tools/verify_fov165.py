"""Verify and record the transition from first-ESC 150 to map-entry 165."""

import difflib
import json
import shutil
import subprocess
import sys
import zipfile

from c_session_release import BUNDLE, DLL, OUTPUT, ROOT, save, sha
from vpk import read


def main():
    directory = ROOT / "reports/fov165"
    directory.mkdir(parents=True, exist_ok=True)
    old = ROOT / "originals/C_before_fov165.vpk"
    old_dll = ROOT / "originals/CSessionDefaults_before_fov165.dll"
    assert sha(old) == "ae89ecc13d4d7946523229f68e0e9d51db93fa010df49e92f3b8caf0a46e4612"
    assert sha(old_dll) == "76b5ba43b582cc9322fb006176e37e8f352ba6b6c2fc4624ba634b6e9fc89bab"
    before, after = read(old), read(OUTPUT)
    cfg, menu = "cfg/l4d2esc_defaults.cfg", "resource/ui/l4d360ui/ingamemainmenu.res"
    assert before.keys() == after.keys()
    changed = {key for key in after if before[key] != after[key]}
    assert changed == {cfg, menu}
    assert before[cfg].replace(b"r_flashlightfov 53", b"r_flashlightfov 165") == after[cfg]
    assert before[menu].replace(b"first ESC is handled", b"map-entry default is handled") == after[menu]
    source = (ROOT / "native/c_session_defaults/plugin.cpp").read_text(encoding="utf-8")
    assert 'SetLocalInteger("r_flashlightfov", 165);' in source
    assert "FIRST_ESC" not in source and "WH_KEYBOARD" not in source and "first_escape" not in source
    assert b"FIRST_ESC" in old_dll.read_bytes() and b"FIRST_ESC" not in DLL.read_bytes()
    diff = directory / "defaults.patch"
    diff.write_text("".join("".join(difflib.unified_diff(
        before[key].decode("utf-8-sig").splitlines(True), after[key].decode("utf-8-sig").splitlines(True),
        fromfile="before/" + key, tofile="after/" + key)) for key in sorted(changed)), encoding="utf-8")
    assert diff.read_text(encoding="utf-8")
    probe = ("import sys; from pathlib import Path; sys.path.insert(0,'tools'); from vpk import read; "
             "t=read(sys.argv[1])['cfg/l4d2esc_defaults.cfg'].decode('utf-8'); "
             "print(next(x for x in t.splitlines() if x.startswith('r_flashlightfov '))); "
             "print('FIRST_ESC handler:', b'FIRST_ESC' in Path(sys.argv[2]).read_bytes())")
    records = []
    for label, vpk, dll in (("baseline", old, old_dll), ("modified", OUTPUT, DLL)):
        command = [sys.executable, "-X", "utf8", "-c", probe, str(vpk), str(dll)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0
        print(label, result.stdout, end="")
        records.append({"label": label, "command": command, "stdout": result.stdout,
                        "stderr": result.stderr, "exit_status": result.returncode})
    patch = directory / "patch.zip"
    with zipfile.ZipFile(patch, "w", zipfile.ZIP_DEFLATED) as archive:
        for key in sorted(changed):
            archive.writestr(key, after[key])
        archive.write(DLL, "bin/neko/plugins/CSessionDefaults.dll")
        archive.write(diff, "defaults.patch")
    with zipfile.ZipFile(patch) as archive:
        assert archive.testzip() is None
        assert all(archive.read(key) == after[key] for key in changed)
        assert archive.read("bin/neko/plugins/CSessionDefaults.dll") == DLL.read_bytes()
    rollback = ROOT / "dist/rollback_fov165"
    rollback.mkdir(parents=True, exist_ok=True)
    for source_path, name in ((old, OUTPUT.name), (old_dll, DLL.name)):
        target = rollback / name
        shutil.copyfile(source_path, target)
        assert sha(target) == sha(source_path)
    assert read(rollback / OUTPUT.name) == before
    build = json.loads((ROOT / "reports/c_session_plugin_build.json").read_text(encoding="utf-8"))
    assert build["helper_version"] == "1.2.3" and build["dll_sha256"] == sha(DLL)
    assert all(record["exit_status"] == 0 for record in build["records"])
    with zipfile.ZipFile(BUNDLE) as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["helper_version"] == "1.2.3"
        assert "first_escape" not in manifest
    sums = ROOT / "dist/SHA256SUMS.txt"
    sums.write_text("".join(f"{sha(path)}  {path.name}\n" for path in (BUNDLE, OUTPUT)), encoding="utf-8", newline="\n")
    assert sums.read_text(encoding="utf-8").splitlines() == [f"{sha(path)}  {path.name}" for path in (BUNDLE, OUTPUT)]
    save(directory / "verification.json", {
        "scope": "archive/static/native fixtures; game-runtime confirmation pending",
        "records": records, "native_build": build,
        "artifacts": {str(p.relative_to(ROOT)): sha(p) for p in (OUTPUT, DLL, BUNDLE, patch, diff, old, old_dll)},
        "unchanged_members": len(after) - len(changed), "rollback_copy": str(rollback),
        "rollback_command": "python -X utf8 tools/c_session_release.py rollback-game",
        "runtime_status": "PENDING_GAME_RESTART"})
    print("PASS map-entry 165, no first-ESC handler; exact two-member delta; bundle and rollback copies reopened")


if __name__ == "__main__":
    main()
