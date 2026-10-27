"""Verify the menu-only switch restoration, stable grouping, patch and rollback."""

import argparse
import difflib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from c_binary_switches import SWITCHES
from c_menu_consolidation import MENU, validate
from c_session_release import GAME, DLL, ROOT, OUTPUT, TARGETS, save, sha
from inspect_menu import blocks, fields
from vpk import read, write

BASE = ROOT / "originals/C_before_switch_event_fix.vpk"
BASE_HASH = "143f48cc557ee9031e12742966e772aeac13fff7bd7674cdcfc163a08855f0e9"
HELPER_HASH = "6dd4c6b297f22cc4264590588bc08dea3cd8e6d6f37d935bce6086810420c908"
WORK = ROOT / "reports/c_switch_events"


def probe(path):
    nodes = {name: fields(b) for name, _, _, b in blocks(read(path)[MENU].decode("utf-8-sig"))
             if fields(b).get("concommand", "").lower() in SWITCHES}
    order = sorted(nodes, key=lambda name: (nodes[name]["xpos"] == "r196", int(nodes[name]["ypos"])))
    print(json.dumps({"sha256": sha(path), "binary_options": [
        {"cvar": nodes[name]["concommand"], "control": nodes[name]["controlname"],
         "min": nodes[name]["minvalue"], "max": nodes[name]["maxvalue"]} for name in order]}, ensure_ascii=False))


def verify():
    WORK.mkdir(parents=True, exist_ok=True)
    if not BASE.exists():
        installed = GAME / TARGETS["vpk"]
        assert sha(installed) == BASE_HASH
        shutil.copyfile(installed, BASE)
    assert sha(BASE) == BASE_HASH
    before, after = read(BASE), read(OUTPUT)
    assert set(before) == set(after) and {name for name in before if before[name] != after[name]} == {MENU}
    assert sha(DLL) == HELPER_HASH, "Menu-only task must not change the helper"
    validate(after)
    old_nodes = {name: fields(b) for name, _, _, b in blocks(before[MENU].decode("utf-8-sig"))
                 if fields(b).get("concommand")}
    new_nodes = {name: fields(b) for name, _, _, b in blocks(after[MENU].decode("utf-8-sig"))
                 if fields(b).get("concommand")}
    assert set(old_nodes) == set(new_nodes)
    old_order = sorted(old_nodes, key=lambda name: (old_nodes[name]["xpos"] == "r196", int(old_nodes[name]["ypos"])))
    binary = [name for name in old_order if old_nodes[name]["concommand"].lower() in SWITCHES]
    other = [name for name in old_order if name not in binary]
    new_order = sorted(new_nodes, key=lambda name: (new_nodes[name]["xpos"] == "r196", int(new_nodes[name]["ypos"])))
    assert len(binary) == 10 and new_order == binary + other
    for name, props in new_nodes.items():
        old = old_nodes[name]
        for key in ("concommand", "minvalue", "maxvalue"):
            assert props[key] == old[key]
        if name in binary:
            assert old["controlname"] == "CvarToggleCheckButton" and props["controlname"] == "SliderControl"
            assert props["stepsize"] == "1"
    diff = "".join(difflib.unified_diff(before[MENU].decode("utf-8-sig").splitlines(True),
                                      after[MENU].decode("utf-8-sig").splitlines(True),
                                      fromfile="before/" + MENU, tofile="after/" + MENU))
    (WORK / "menu.patch").write_text(diff, encoding="utf-8", newline="\n")
    patch = WORK / "patch.zip"
    manifest = {"baseline_sha256": BASE_HASH, "result_sha256": sha(OUTPUT), "changed": [MENU]}
    with zipfile.ZipFile(patch, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("menu.patch", diff)
        archive.writestr(MENU, after[MENU])
    with zipfile.ZipFile(patch) as archive:
        assert archive.testzip() is None and json.loads(archive.read("manifest.json")) == manifest
        replay = dict(before)
        replay[MENU] = archive.read(MENU)
    replayed = WORK / "replayed.vpk"
    write(replayed, replay)
    assert read(replayed) == after and sha(replayed) == sha(OUTPUT)
    restored = WORK / "rollback" / OUTPUT.name
    restored.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BASE, restored)
    assert sha(restored) == BASE_HASH and read(restored) == before
    records = []
    for label, path in (("baseline", BASE), ("modified", OUTPUT)):
        command = [sys.executable, "-X", "utf8", "tools/review_c_switch_fix.py", "probe", "--vpk", str(path)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0
        records.append({"label": label, "command": command, "cwd": str(ROOT), "stdout": result.stdout,
                        "stderr": result.stderr, "exit_status": result.returncode})
    save(WORK / "verification.json", {"status": "MENU_ONLY_PATCH_REPLAY_AND_ROLLBACK_PASSED",
         "scope": "Static native control restoration and layout; not live game clicks",
         "records": records, "unchanged_members": len(after) - 1, "helper_sha256": sha(DLL),
         "binary_order": [new_nodes[name]["concommand"] for name in binary],
         "other_order": [new_nodes[name]["concommand"] for name in other],
         "artifacts": {str(path): sha(path) for path in (BASE, OUTPUT, patch, replayed, restored)}})
    print("PASS only ESC resource changed; all 10 direct-setter 0/1 controls restored and grouped first")
    print("PASS binary and nonbinary relative order preserved; patch replay and original rollback reopened")
    print("RECORD", WORK / "verification.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("probe", "verify"))
    parser.add_argument("--vpk", type=Path)
    args = parser.parse_args()
    if args.action == "probe":
        probe(args.vpk)
    else:
        verify()


if __name__ == "__main__":
    main()
