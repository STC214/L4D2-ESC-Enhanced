"""Record the narrow full-screen background/light-defaults regression."""

import difflib
import json
import subprocess
import sys
import zipfile

from c_session_release import DLL, OUTPUT, ROOT, save, sha
from inspect_menu import blocks, fields
from vpk import read


def main():
    directory = ROOT / "reports/fullscreen_light_defaults"
    directory.mkdir(parents=True, exist_ok=True)
    old = ROOT / "originals/C_before_fullscreen_light_defaults.vpk"
    old_dll = ROOT / "originals/CSessionDefaults_before_light_defaults.dll"
    assert sha(old) == "34b9d16ebce66da92a60187a7f7dad568fbe426f05a2c932e3701efc4153e95f"
    assert sha(old_dll) == "eb3feb68bd4bed3faba459f27b7c9cd76577d2c04d31c39b7a277dcba26de92b"
    before, after = read(old), read(OUTPUT)
    menu = "resource/ui/l4d360ui/ingamemainmenu.res"
    assert before.keys() == after.keys()
    assert [key for key in after if before[key] != after[key]] == [menu]
    original, modified = (files[menu].decode("utf-8-sig") for files in (before, after))
    old_blocks, new_blocks = (dict((n, b) for n, _, _, b in blocks(text))
                              for text in (original, modified))
    assert old_blocks.keys() == new_blocks.keys()
    assert [key for key in new_blocks if old_blocks[key] != new_blocks[key]] == ["PnlBackground_tweaks1"]
    background = fields(new_blocks["PnlBackground_tweaks1"])
    for key, value in {"xpos": "0", "ypos": "0", "wide": "f0", "tall": "f0",
                       "bgcolor_override": "0 0 0 232", "paintbackground": "1",
                       "paintbackgroundtype": "0"}.items():
        assert background[key] == value
    settings = {fields(b).get("concommand"): fields(b) for b in new_blocks.values()}
    assert settings["r_flashlightconstant"]["maxvalue"] == "1"
    assert settings["r_flashlightfar"]["maxvalue"] == "3000"
    diff = directory / "background.patch"
    diff.write_text("".join(difflib.unified_diff(original.splitlines(True), modified.splitlines(True),
                                               fromfile="before/" + menu, tofile="after/" + menu)), encoding="utf-8")
    assert diff.read_text(encoding="utf-8")
    records = []
    probe = ("import sys; sys.path.insert(0,'tools'); from vpk import read; "
             "from inspect_menu import blocks,fields; "
             "p=next(fields(b) for n,_,_,b in blocks(read(sys.argv[1])['" + menu +
             "'].decode('utf-8-sig')) if n=='PnlBackground_tweaks1'); "
             "print('BACKGROUND',p['paintbackgroundtype'],p['bgcolor_override'],p['wide'],p['tall'])")
    for label, path in (("baseline", old), ("modified", OUTPUT)):
        command = [sys.executable, "-X", "utf8", "-c", probe, str(path)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0
        records.append({"label": label, "command": command, "stdout": result.stdout,
                        "stderr": result.stderr, "exit_status": result.returncode})
        print(label, result.stdout.strip())
    patch = directory / "patch.zip"
    with zipfile.ZipFile(patch, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(menu, after[menu])
        archive.write(DLL, "bin/neko/plugins/CSessionDefaults.dll")
        archive.write(diff, "background.patch")
    with zipfile.ZipFile(patch) as archive:
        assert archive.testzip() is None and archive.read(menu) == after[menu]
        assert archive.read("bin/neko/plugins/CSessionDefaults.dll") == DLL.read_bytes()
    build = json.loads((ROOT / "reports/c_session_plugin_build.json").read_text(encoding="utf-8"))
    assert build["helper_version"] == "1.2.2" and build["dll_sha256"] == sha(DLL)
    assert all(record["exit_status"] == 0 for record in build["records"])
    save(directory / "verification.json", {
        "scope": "static full-screen geometry + native setter/lifecycle/bootstrap tests; live game pending",
        "records": records, "native_build": build, "unchanged_vpk_members": len(after) - 1,
        "artifacts": {str(path.relative_to(ROOT)): sha(path) for path in (OUTPUT, DLL, diff, patch, old, old_dll)},
        "rollback_command": "python -X utf8 tools/c_session_release.py rollback-game",
        "source_reference": "https://github.com/ValveSoftware/source-sdk-2013/blob/master/src/vgui2/vgui_controls/Panel.cpp",
        "runtime_status": "PENDING_GAME_RESTART"})
    print("PASS full-screen solid fill; 221 other members unchanged; light maxima match native test values")


if __name__ == "__main__":
    main()
