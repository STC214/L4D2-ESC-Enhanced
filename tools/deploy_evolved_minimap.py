"""Deploy the reviewed 1.2.5 map/navigation profile using existing L4N.

No game launch, DLL execution, loader replacement, or C modification.
Rollback is preview-only unless explicitly requested with --rollback-confirmed.
"""

import argparse
import datetime
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

from release_paths import ROOT, OUTPUT


GAME = Path(r"E:\SteamLibrary\steamapps\common\Left 4 Dead 2")
STUDY = ROOT / "research/workshop_3785109042"
SOURCE = STUDY / "unpacked"
RULES = ROOT / "docs/evolved-adaptation-rules.v1.json"
PROFILE = ROOT / "modified_evolved/Evolved/config.txt"
WORK = ROOT / "reports/evolved_deploy_125"
BUNDLE = ROOT / "dist/Evolved_1.2.5_地图导航默认开启.zip"
PLAN = WORK / "plan.json"
JOURNAL = WORK / "transaction.json"
CFG = "Evolved/config.txt"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(path):
    return {"exists": path.is_file(), "sha256": sha(path.read_bytes()) if path.is_file() else None}


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temp = path.with_suffix(path.suffix + ".pending")
    with temp.open("wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    assert json.loads(path.read_text(encoding="utf-8")) == obj


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def safe_target(name):
    assert not Path(name).is_absolute() and ":" not in name and ".." not in Path(name).parts
    target = GAME / name
    assert target.resolve().is_relative_to(GAME.resolve())
    for path in (target, *target.parents):
        if path.exists():
            assert not (getattr(path.lstat(), "st_file_attributes", 0) & 0x400), path
        if path == GAME:
            break
    assert not target.is_dir(), target
    return target


def require_game_closed():
    result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq left4dead2.exe", "/FO", "CSV", "/NH"],
                            capture_output=True, text=True, errors="replace", check=True)
    assert '"left4dead2.exe"' not in result.stdout.lower(), "Exit L4D2 before deploying or restoring"


def active_settings(raw):
    text = raw.decode("utf-8-sig")
    values = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith(("#", ";", "//")):
            continue
        assert "=" in line, "Unknown config line; preserve for review"
        key, value = line.split("=", 1)
        key = key.strip()
        assert key not in values, "Duplicate active setting: " + key
        values[key] = value.strip()
    return values


def config_payload(before):
    wanted = active_settings(PROFILE.read_bytes())
    assert wanted["NoHmdMinimapEnabled"] == wanted["NoHmdWorldNavigationEnabled"] == "true"
    if before is None:
        return PROFILE.read_bytes()
    existing = active_settings(before)
    newline = "\r\n" if b"\r\n" in before else "\n"
    text = before.decode("utf-8-sig")
    for key, value in wanted.items():
        if key in existing:
            text, count = re.subn(r"(?m)^(\s*" + re.escape(key) + r"\s*=)[^\r\n]*", r"\g<1>" + value, text)
            assert count == 1
        else:
            if text and not text.endswith(("\r", "\n")):
                text += newline
            text += key + "=" + value + newline
    raw = (b"\xef\xbb\xbf" if before.startswith(b"\xef\xbb\xbf") else b"") + text.encode("utf-8")
    result = active_settings(raw)
    assert all(result[k] == v for k, v in wanted.items())
    assert all(result[k] == v for k, v in existing.items() if k not in wanted)
    return raw


def prepare():
    assert GAME.is_dir() and (GAME / "left4dead2.exe").is_file()
    assert (GAME / "bin/left4neko.dll").is_file()
    rules = load(RULES)
    extraction = load(STUDY / "extraction_verification.json")
    assert sha((STUDY / "3785109042.vpk").read_bytes()) == rules["profile"]["package_sha256"]
    expected = {row["path"]: row["sha256"] for row in extraction["members"]}
    files = {}
    for name in rules["install_files"]:
        raw = (SOURCE / name).read_bytes()
        assert sha(raw) == expected[name], name
        files[name] = raw
    config = safe_target(CFG)
    old = config.read_bytes() if config.is_file() else None
    # A second config may override values; stop rather than guess precedence.
    assert not (GAME / "Evolved/config2.txt").exists(), "Existing config2.txt needs precedence review"
    files[CFG] = config_payload(old)
    assert not (set(files) & set(rules["protected_paths"]))
    records = []
    for name, raw in sorted(files.items()):
        current = snapshot(safe_target(name))
        if name != CFG and current["exists"]:
            assert current["sha256"] == sha(raw), "Existing different file needs review: " + name
        records.append({"path": name, "before": current, "after_sha256": sha(raw),
                        "operation": "noop" if current["sha256"] == sha(raw) else "replace" if current["exists"] else "add"})
    protected = {name: snapshot(safe_target(name)) for name in rules["protected_paths"]}
    assert protected["left4dead2/addons/" + OUTPUT.name] == snapshot(OUTPUT), "Installed C differs from reviewed project C"
    BUNDLE.parent.mkdir(exist_ok=True)
    manifest = {name: sha(raw) for name, raw in sorted(files.items())}
    with zipfile.ZipFile(BUNDLE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, raw)
        archive.writestr("deployment_manifest.json", json.dumps(manifest, indent=2).encode())
    with zipfile.ZipFile(BUNDLE) as archive:
        assert archive.testzip() is None
        assert all(sha(archive.read(name)) == value for name, value in manifest.items())
    diff = "".join(difflib.unified_diff((old or b"").decode("utf-8-sig").splitlines(True),
                                      files[CFG].decode("utf-8-sig").splitlines(True),
                                      fromfile="game/" + CFG if old else "/dev/null", tofile="game/" + CFG))
    WORK.mkdir(parents=True, exist_ok=True)
    patch = WORK / "config.patch"
    patch.write_text(diff, encoding="utf-8", newline="\n")
    assert patch.read_text(encoding="utf-8") == diff.replace("\r\n", "\n")
    plan = {"game_root": str(GAME), "bundle_sha256": sha(BUNDLE.read_bytes()),
            "profile_sha256": sha(PROFILE.read_bytes()), "records": records, "protected": protected,
            "loader": "existing L4N; both winmm proxies excluded", "runtime_status": "NOT_TESTED"}
    save(PLAN, plan)
    print(f"PREPARED {len(records)} files: {BUNDLE}")
    for row in records:
        print(row["operation"], row["path"])
    print("DEFAULTS NoHmdMinimapEnabled=true; NoHmdWorldNavigationEnabled=true")
    print("MENU existing settings: 小地图导航 / 实景导航箭头; console evo_config")


def verify():
    plan = load(PLAN)
    assert plan["game_root"] == str(GAME)
    assert sha(BUNDLE.read_bytes()) == plan["bundle_sha256"]
    for row in plan["records"]:
        assert snapshot(safe_target(row["path"])) == {"exists": True, "sha256": row["after_sha256"]}, row["path"]
    for name, before in plan["protected"].items():
        assert snapshot(safe_target(name)) == before, name
    values = active_settings(safe_target(CFG).read_bytes())
    assert values["NoHmdMinimapEnabled"] == values["NoHmdWorldNavigationEnabled"] == "true"
    print("PASS 13 deployed files reopened and hash-verified; 8 explicit profile settings")
    print("PASS original game EXE/L4N/renderers/player binds/C unchanged")
    print("RUNTIME_PENDING: game was not launched; menu rendering/nav mesh availability untested")
    return plan


def apply():
    require_game_closed()
    plan = load(PLAN)
    if JOURNAL.exists():
        previous = load(JOURNAL)
        assert previous["state"] == "FILES_VERIFIED", "Review unfinished transaction before continuing"
        verify()
        print("NOOP completed transaction already matches")
        return
    assert sha(BUNDLE.read_bytes()) == plan["bundle_sha256"]
    for name, before in plan["protected"].items():
        assert snapshot(safe_target(name)) == before, name
    for row in plan["records"]:
        assert snapshot(safe_target(row["path"])) == row["before"], "Changed since planning: " + row["path"]
    journal = {"game_root": str(GAME), "plan_sha256": sha(PLAN.read_bytes()), "state": "BACKED_UP",
               "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "records": []}
    for row in plan["records"]:
        item = dict(row, state="PLANNED")
        if row["before"]["exists"] and row["operation"] != "noop":
            backup = WORK / "backups" / row["path"]
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(safe_target(row["path"]), backup)
            assert sha(backup.read_bytes()) == row["before"]["sha256"]
            item["backup"] = str(backup.relative_to(ROOT))
        journal["records"].append(item)
    save(JOURNAL, journal)
    with zipfile.ZipFile(BUNDLE) as archive:
        for row in journal["records"]:
            if row["operation"] == "noop":
                row["state"] = "NOOP"
                save(JOURNAL, journal)
                continue
            target = safe_target(row["path"])
            assert snapshot(target) == row["before"]
            row["state"] = "INTENT"
            journal["state"] = "APPLYING"
            save(JOURNAL, journal)
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_name(target.name + ".evo125-staging")
            assert not temp.exists()
            raw = archive.read(row["path"])
            assert sha(raw) == row["after_sha256"]
            with temp.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, target)
            assert sha(target.read_bytes()) == row["after_sha256"]
            row["state"] = "COMMITTED"
            save(JOURNAL, journal)
    verify()
    journal["state"] = "FILES_VERIFIED"
    save(JOURNAL, journal)
    print("DEPLOYED " + str(GAME))


def rollback(confirmed=False):
    journal = load(JOURNAL)
    assert journal["game_root"] == str(GAME)
    assert journal["plan_sha256"] == sha(PLAN.read_bytes())
    for row in reversed(journal["records"]):
        if row["operation"] == "noop" or row["state"] == "PLANNED":
            continue
        target = safe_target(row["path"])
        current = snapshot(target)
        if current == row["before"]:
            continue
        assert current["sha256"] == row["after_sha256"], "Later edits preserved; conflict: " + str(target)
        if row["before"]["exists"]:
            assert sha((ROOT / row["backup"]).read_bytes()) == row["before"]["sha256"]
        print("RESTORE" if row["before"]["exists"] else "REMOVE_ADDED", str(target))
    if not confirmed:
        print("PASS rollback input/hash/backup checks; PREVIEW ONLY; no deletion or restoration performed")
        return
    require_game_closed()
    for row in reversed(journal["records"]):
        if row["operation"] == "noop" or row["state"] == "PLANNED":
            continue
        target = safe_target(row["path"])
        if snapshot(target) == row["before"]:
            continue
        assert snapshot(target)["sha256"] == row["after_sha256"]
        if row["before"]["exists"]:
            shutil.copy2(ROOT / row["backup"], target)
        else:
            target.unlink()
        assert snapshot(target) == row["before"]
    journal["state"] = "ROLLED_BACK"
    save(JOURNAL, journal)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "apply", "verify", "rollback-check", "rollback-confirmed"))
    args = parser.parse_args()
    if args.mode == "prepare":
        assert not JOURNAL.exists(), "Do not overwrite an existing transaction plan"
        prepare()
    elif args.mode == "apply":
        apply()
    elif args.mode == "verify":
        verify()
    else:
        rollback(args.mode == "rollback-confirmed")


if __name__ == "__main__":
    main()
