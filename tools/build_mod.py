"""Reproducible VPK packaging, patch replay and exact verification records."""

import argparse
import difflib
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from vpk import read, write


ROOT = Path(__file__).resolve().parents[1]
MENU = "resource/ui/l4d360ui/ingamemainmenu.res"
ORIGINAL = ROOT / "originals/B_2906960647.vpk"
OUTPUT = ROOT / "dist/B_fullscreen_esc.vpk"
REPORTS = ROOT / "reports"
PATCH = REPORTS / "B_fullscreen.patch"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_patch():
    """Replay the saved unified diff against original members in memory."""
    original = read(ORIGINAL)
    modified = read(OUTPUT)
    lines = PATCH.read_text(encoding="utf-8").splitlines(keepends=True)
    i = 0
    replayed = dict(original)
    while i < len(lines):
        assert lines[i].startswith("--- ")
        before = lines[i][4:].strip()
        after = lines[i + 1][4:].strip()
        assert lines[i + 1].startswith("+++ ")
        key = after.removeprefix("b/")
        assert before == "a/" + key or before == "/dev/null"
        source = original.get(key, b"").decode("utf-8-sig").splitlines(keepends=True)
        source = [line.rstrip("\r\n") + "\n" for line in source]
        result = []
        cursor = 0
        i += 2
        while i < len(lines) and lines[i].startswith("@@"):
            match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", lines[i])
            assert match
            start = max(0, int(match[1]) - 1)
            assert start >= cursor
            result.extend(source[cursor:start])
            cursor = start
            removed = added = 0
            i += 1
            while i < len(lines) and not lines[i].startswith(("@@", "--- ")):
                line = lines[i]
                if line[0] in " -":
                    assert source[cursor] == line[1:], (key, cursor)
                    cursor += 1
                    removed += 1
                if line[0] in " +":
                    result.append(line[1:])
                    added += 1
                assert line[0] in " +-"
                i += 1
            assert removed == int(match[2] or 1)
            assert added == int(match[4] or 1)
        result.extend(source[cursor:])
        replayed[key] = "".join(result).encode("utf-8")
    assert replayed == modified
    print("PASS saved unified patch replay reconstructs every modified VPK member exactly")


def command_record(args, inputs):
    command = [sys.executable, "-X", "utf8", *args]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    record = {
        "cwd": str(ROOT), "command": command,
        "inputs": {str(path.relative_to(ROOT)): sha(path) for path in inputs},
        "stdout": result.stdout, "stderr": result.stderr, "exit_status": result.returncode,
    }
    print(subprocess.list2cmdline(command))
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    assert result.returncode == 0, record
    return record


def build():
    assert sha(ORIGINAL) == "dc6efecc83d1de19483ff46fbc964f1549d59852eb156599b21bc72d48f6108e"
    assert sha(ROOT / "originals/A_3467154613.vpk") == "ac76f4baf11f7a944a3e9fcaa330cb1fbe9321e29bd99778b1a9df500afeb29c"
    baseline = read(ORIGINAL)
    files = dict(baseline)
    for path in sorted((ROOT / "modified").rglob("*")):
        if path.is_file():
            files[path.relative_to(ROOT / "modified").as_posix()] = path.read_bytes()
    OUTPUT.parent.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    write(OUTPUT, files)
    assert read(OUTPUT) == files
    patch = []
    for name in sorted(files):
        if files[name] != baseline.get(name):
            old = baseline.get(name, b"").decode("utf-8-sig").splitlines()
            new = files[name].decode("utf-8-sig").splitlines()
            patch.extend(difflib.unified_diff(
                [line + "\n" for line in old], [line + "\n" for line in new],
                fromfile="a/" + name if name in baseline else "/dev/null", tofile="b/" + name,
            ))
    PATCH.write_text("".join(patch), encoding="utf-8", newline="\n")
    verify_patch()
    records = [
        command_record(["tools/verify_menu.py", "originals/A_3467154613.vpk"], [ROOT / "originals/A_3467154613.vpk"]),
        command_record(["tools/verify_menu.py", "originals/B_2906960647.vpk"], [ORIGINAL]),
        command_record(["tools/verify_menu.py", "dist/B_fullscreen_esc.vpk", "--modified"], [ORIGINAL, OUTPUT]),
        command_record(["tools/build_mod.py", "--verify-patch"], [ORIGINAL, OUTPUT, PATCH]),
        command_record(["tools/rollback.py"], [ORIGINAL]),
        command_record(["tools/verify_menu.py", "dist/B_original_restored.vpk"], [ROOT / "dist/B_original_restored.vpk"]),
    ]
    report = {
        "scope": "Static resource/archive verification, not in-game execution",
        "artifacts": {str(p.relative_to(ROOT)): sha(p) for p in (ORIGINAL, OUTPUT, PATCH, ROOT / "tools/rollback.py")},
        "records": records,
        "runtime_checks_remaining": ["rendering/fonts", "ESC initializer trigger and editability", "server cvar acceptance", "flyout interactions", "mode-specific button visibility"],
    }
    target = REPORTS / "verification.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    reopened = json.loads(target.read_text(encoding="utf-8"))
    assert len(reopened["records"]) == 6
    assert all(r["exit_status"] == 0 for r in reopened["records"])
    assert all(not r["stderr"] for r in reopened["records"])
    print("VERIFIED " + str(OUTPUT))
    print("SHA256 " + sha(OUTPUT))
    print("RECORD " + str(target))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-patch", action="store_true")
    args = parser.parse_args()
    if args.verify_patch:
        verify_patch()
    else:
        build()
