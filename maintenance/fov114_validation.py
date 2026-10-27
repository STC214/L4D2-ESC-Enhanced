"""Verify the isolated FOV default change; rollback restores local dist only."""

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from release_paths import OUTPUT
from vpk import read

WORK = ROOT / "reports/fov114"
TARGETS = {
    "before.vpk": OUTPUT,
    "before.dll": ROOT / "dist/c_session_helper/CSessionDefaults.dll",
    "before.zip": ROOT / "dist/C_session_release.zip",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rollback(targets):
    for name, target in targets.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORK / name, target)
        assert sha(target) == sha(WORK / name)
    print("PASS rollback copies match preserved VPK/DLL/ZIP")


def verify():
    before, after = read(WORK / "before.vpk"), read(OUTPUT)
    cfg = "cfg/l4d2esc_defaults.cfg"
    assert set(before) == set(after)
    changed = [name for name in before if before[name] != after[name]]
    assert changed == [cfg], changed
    assert before[cfg].replace(b"r_flashlightfov 165", b"r_flashlightfov 114") == after[cfg]
    patch = "".join(difflib.unified_diff(
        before[cfg].decode().splitlines(True), after[cfg].decode().splitlines(True),
        fromfile="before/" + cfg, tofile="after/" + cfg))
    (WORK / "defaults.patch").write_text(patch, encoding="utf-8")
    assert (WORK / "defaults.patch").read_text(encoding="utf-8") == patch
    records = []
    probe = (
        "import sys; sys.path.insert(0,'tools'); from pathlib import Path; from vpk import read; "
        "print(next(s for s in read(Path(sys.argv[1]))['cfg/l4d2esc_defaults.cfg'].decode().splitlines() "
        "if s.startswith('r_flashlightfov ')))"
    )
    for label, path, expected in (("baseline", WORK / "before.vpk", "165"),
                                  ("modified", OUTPUT, "114")):
        command = [sys.executable, "-B", "-X", "utf8", "-c", probe, str(path)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        records.append(dict(label=label, command=command, inputs=str(path), stdout=result.stdout,
                            stderr=result.stderr, exit_status=result.returncode))
        assert result.returncode == 0 and result.stdout.strip() == "r_flashlightfov " + expected
    build = json.loads((ROOT / "reports/c_session_plugin_build.json").read_text(encoding="utf-8"))
    assert build["dll_sha256"] == sha(TARGETS["before.dll"])
    assert all(item["exit_status"] == 0 for item in build["records"])
    assert any("FOV 114" in item["stdout"] for item in build["records"])
    with zipfile.ZipFile(TARGETS["before.zip"]) as archive:
        assert archive.testzip() is None
        assert archive.read("left4dead2/addons/" + OUTPUT.name) == OUTPUT.read_bytes()
        assert archive.read("bin/neko/plugins/CSessionDefaults.dll") == TARGETS["before.dll"].read_bytes()
        assert "114 once" in json.loads(archive.read("manifest.json"))["flashlight_cone"]
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "rollback-fixture"]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    records.append(dict(command=command, stdout=result.stdout, stderr=result.stderr, exit_status=result.returncode))
    assert result.returncode == 0
    report = dict(status="PASS", changed_members=changed, unchanged_members=len(after) - 1,
                  records=records, native_build=build, runtime="Not tested in game; not deployed",
                  artifacts={str(p.relative_to(ROOT)): sha(p) for p in [*TARGETS.values(), WORK / "defaults.patch"]},
                  baseline={name: sha(WORK / name) for name in TARGETS},
                  rollback_command="python -B -X utf8 maintenance/fov114_validation.py rollback")
    (WORK / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert json.loads((WORK / "verification.json").read_text(encoding="utf-8")) == report
    print("PASS only FOV default 165 -> 114; other 222 VPK members identical; native tests, ZIP and rollback verified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify", "rollback", "rollback-fixture"))
    action = parser.parse_args().action
    if action == "verify":
        verify()
    else:
        rollback(TARGETS if action == "rollback" else {name: WORK / "rollback_fixture" / name for name in TARGETS})
