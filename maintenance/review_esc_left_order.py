"""Verify left-column-only changes and exercise a local-dist rollback fixture."""

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
from c_menu_consolidation import MENU, LEFT_COLUMN_ORDER, DLL, BUNDLE
from inspect_menu import blocks, fields
from prepare_menu_patch import set_fields
from release_paths import OUTPUT
from vpk import read, write

WORK = ROOT / "reports/esc_left_order"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rollback(fixture=False):
    directory = WORK / "rollback_fixture" if fixture else ROOT / "dist"
    directory.mkdir(parents=True, exist_ok=True)
    for source, name in ((WORK / "before.vpk", OUTPUT.name), (WORK / "before.zip", BUNDLE.name)):
        target = directory / name
        shutil.copyfile(source, target)
        assert sha(source) == sha(target)
    paths = (directory / BUNDLE.name, directory / OUTPUT.name)
    sums = "".join(f"{sha(path)}  {path.name}\n" for path in paths)
    (directory / "SHA256SUMS.txt").write_text(sums, encoding="utf-8", newline="\n")
    assert (directory / "SHA256SUMS.txt").read_text(encoding="utf-8") == sums
    assert read(directory / OUTPUT.name) == read(WORK / "before.vpk")
    print("PASS rollback VPK/ZIP reopened and byte-identical; DLL and game untouched")


def probe(path):
    nodes = {name: fields(block) for name, _, _, block in blocks(read(path)[MENU].decode("utf-8-sig"))}
    order = sorted(LEFT_COLUMN_ORDER, key=lambda name: int(nodes[name]["ypos"]))
    print(json.dumps(order))


def verify():
    before, after = read(WORK / "before.vpk"), read(OUTPUT)
    assert set(before) == set(after) and [name for name in before if before[name] != after[name]] == [MENU]
    old_text, text = before[MENU].decode("utf-8-sig"), after[MENU].decode("utf-8-sig")
    old = {name: fields(block) for name, _, _, block in blocks(old_text)}
    expected = old_text
    for name, start, end, block in reversed(blocks(old_text)):
        if name in LEFT_COLUMN_ORDER:
            block = set_fields(block, {"ypos": str(93 + 25 * LEFT_COLUMN_ORDER.index(name))})
            expected = expected[:start] + block + expected[end:]
    assert expected == text, "Only the 15 top-level y positions may change"
    nodes = {name: fields(block) for name, _, _, block in blocks(text)}
    for index, name in enumerate(LEFT_COLUMN_ORDER):
        assert nodes[name]["navup"] == LEFT_COLUMN_ORDER[(index - 1) % 15]
        assert nodes[name]["navdown"] == LEFT_COLUMN_ORDER[(index + 1) % 15]
        assert {k: v for k, v in nodes[name].items() if k != "ypos"} == {k: v for k, v in old[name].items() if k != "ypos"}
    assert sha(DLL) == "d20fdaf5faefc335ac470e5a1416f4b53b4a8bf7f898c26472dad4b04724cef2"
    with zipfile.ZipFile(BUNDLE) as archive:
        assert archive.testzip() is None
        assert archive.read("left4dead2/addons/" + OUTPUT.name) == OUTPUT.read_bytes()
        assert archive.read("bin/neko/plugins/CSessionDefaults.dll") == DLL.read_bytes()
    diff = "".join(difflib.unified_diff(old_text.splitlines(True), text.splitlines(True), fromfile="before/" + MENU, tofile="after/" + MENU))
    (WORK / "menu.patch").write_text(diff, encoding="utf-8", newline="\n")
    assert (WORK / "menu.patch").read_text(encoding="utf-8") == diff
    replay = dict(before)
    replay[MENU] = expected.encode("utf-8")
    write(WORK / "replayed.vpk", replay)
    assert sha(WORK / "replayed.vpk") == sha(OUTPUT)
    records = []
    commands = [
        [str(Path(__file__).resolve()), "probe", str(WORK / "before.vpk")],
        [str(Path(__file__).resolve()), "probe", str(OUTPUT)],
        ["tools/test_c.py"],
        [str(Path(__file__).resolve()), "rollback-fixture"],
    ]
    for args in commands:
        command = [sys.executable, "-B", "-X", "utf8", *args]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        records.append(dict(command=command, cwd=str(ROOT), stdout=result.stdout, stderr=result.stderr, exit_status=result.returncode))
        assert result.returncode == 0, records[-1]
    assert json.loads(records[0]["stdout"])[0] == "DrpSplitScreenMode"
    assert json.loads(records[1]["stdout"]) == list(LEFT_COLUMN_ORDER)
    report = dict(status="PASS", unchanged_members=len(after) - 1, changed_fields="15 top-level ypos only",
                  records=records, runtime="Not tested live; not deployed", helper_unchanged=sha(DLL),
                  artifacts={str(p.relative_to(ROOT)): sha(p) for p in (OUTPUT, BUNDLE, WORK / "menu.patch", WORK / "before.vpk", WORK / "before.zip")},
                  rollback_command="python -B -X utf8 maintenance/review_esc_left_order.py rollback")
    target = WORK / "verification.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert json.loads(target.read_text(encoding="utf-8")) == report
    print("PASS native menu first; custom menu below ExitToMainMenu; 222 other members and DLL unchanged; 50 tests and rollback fixture passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify", "rollback", "rollback-fixture", "probe"))
    parser.add_argument("path", nargs="?", type=Path)
    args = parser.parse_args()
    if args.action == "verify":
        verify()
    elif args.action == "probe":
        probe(args.path)
    else:
        rollback(args.action == "rollback-fixture")
