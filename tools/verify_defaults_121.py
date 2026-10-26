"""Focused regression evidence for weather bootstrap and ESC background 1.2.1."""

import difflib
import json
import shutil
import subprocess
import zipfile

from c_session_release import DLL, OUTPUT, ROOT, save, sha
from inspect_menu import blocks
from prepare_menu_patch import set_fields
from vpk import read


def main():
    report_dir = ROOT / "reports/defaults_121"
    report_dir.mkdir(parents=True, exist_ok=True)
    old_vpk = ROOT / "originals/C_before_weather_defaults_121.vpk"
    old_dll = ROOT / "originals/CSessionDefaults_before_weather_defaults_121.dll"
    assert sha(old_vpk) == "d8f074ef12d2a234b82289e96198fb32859450f2145c8ad21a68a4b4a91cd5d3"
    assert sha(old_dll) == "7929554eaed0a480938759d421ead8061ad094313efbf4667b4f6a1a8c8a46d8"
    before, after = read(old_vpk), read(OUTPUT)
    menu = "resource/ui/l4d360ui/ingamemainmenu.res"
    assert before.keys() == after.keys()
    changed = [key for key in after if before[key] != after[key]]
    assert changed == [menu], changed
    original = before[menu].decode("utf-8-sig")
    expected = original
    for name, start, end, block in blocks(original):
        if name == "PnlBackground_tweaks1":
            updated = set_fields(block, {"bgcolor_override": "0 0 0 232",
                                         "paintbackground": "1", "paintbackgroundtype": "1"})
            expected = original[:start] + updated + original[end:]
            break
    assert expected != original
    assert after[menu].decode("utf-8-sig") == expected
    cfg = after["cfg/l4d2esc_defaults.cfg"].decode("utf-8-sig")
    for name in ("r_RainParticleDensity", "r_SnowParticles", "fog_override",
                 "fog_enable", "cl_ragdoll_maxcount"):
        assert any(line.split()[:2] == [name, "0"] for line in cfg.splitlines()), name
    diff = "".join(difflib.unified_diff(original.splitlines(True), expected.splitlines(True),
                                       fromfile="before/" + menu, tofile="after/" + menu))
    patch = report_dir / "background.patch"
    patch.write_text(diff, encoding="utf-8")
    assert patch.read_text(encoding="utf-8") == diff
    records = []
    host = ROOT / "dist/c_session_helper/window_bootstrap_test.exe"
    for label, dll, status in (("baseline", old_dll, 1), ("modified", DLL, 0)):
        command = [str(host), str(dll), str(report_dir / label)]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        records.append({"label": label, "command": command, "stdout": result.stdout,
                        "stderr": result.stderr, "exit_status": result.returncode})
        print(label.upper(), result.stdout, "EXIT", result.returncode)
        assert result.returncode == status
    rollback_dir = ROOT / "dist/rollback_defaults_121"
    rollback_dir.mkdir(parents=True, exist_ok=True)
    for source, name in ((old_vpk, OUTPUT.name), (old_dll, DLL.name)):
        target = rollback_dir / name
        shutil.copyfile(source, target)
        assert sha(target) == sha(source)
    package = report_dir / "patch.zip"
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(menu, after[menu])
        archive.write(DLL, "bin/neko/plugins/CSessionDefaults.dll")
        archive.write(patch, "background.patch")
    with zipfile.ZipFile(package) as archive:
        assert archive.testzip() is None
        assert archive.read(menu) == after[menu]
        assert archive.read("bin/neko/plugins/CSessionDefaults.dll") == DLL.read_bytes()
    build = json.loads((ROOT / "reports/c_session_plugin_build.json").read_text(encoding="utf-8"))
    assert build["helper_version"] == "1.2.1"
    assert all(item["exit_status"] == 0 for item in build["records"])
    save(report_dir / "verification.json", {
        "scope": "exact VPK delta and real DLL fixture; not live game validation",
        "changed_vpk_members": changed, "unchanged_members": len(after) - 1,
        "artifacts": {str(p.relative_to(ROOT)): sha(p) for p in (OUTPUT, DLL, patch, package)},
        "records": records, "native_build": build,
        "rollback_command": "python -X utf8 tools/c_session_release.py rollback-game",
        "rollback_copy": str(rollback_dir), "runtime_status": "PENDING_GAME_RESTART"})
    print("PASS only ESC background changed; weather/corpses CFG zero; rollback copies reopened")
    print("RECORD", report_dir / "verification.json")


if __name__ == "__main__":
    main()
