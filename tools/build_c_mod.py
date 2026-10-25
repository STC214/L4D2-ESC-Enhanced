"""Package integrated C; optionally derive its pixel profile from video.txt.

Adaptation happens during packaging, not inside a running L4D2 process.
Source resources stay at their reviewed 1280x720 template values.
"""

import argparse
import difflib
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

from prepare_menu_patch import set_fields
from inspect_menu import blocks
from verify_c_mod import BASE, BASE_HASH, CFG, LED, MENU, NETWORK, ROOT, validate_files
from vpk import read, write
from hud_integration import HUD, PRE_HUD, merge as merge_hud
from kv_audit import parse, scalars
from audit_c import inspect as full_audit
from tumtara_integration import BEFORE, BUTTONS, MAIN_FILES, merge as merge_tumtara
from release_paths import OUTPUT


PATCH = ROOT / "reports/C_update_patch.zip"
DIFF = ROOT / "reports/C_update.patch"
RECORD = ROOT / "reports/C_verification.json"


def digest(content):
    return hashlib.sha256(content).hexdigest()


def video_resolution(text):
    nodes = parse(text)
    if len(nodes) == 1 and isinstance(nodes[0].value, list):
        nodes = nodes[0].value
    selected = [n for n in nodes if n.key.lower() in ("setting.defaultres", "setting.defaultresheight")]
    values = scalars(selected)
    if set(values) != {"setting.defaultres", "setting.defaultresheight"}:
        raise ValueError("video.txt needs setting.defaultres and setting.defaultresheight")
    if len(selected) != 2 or any(not re.fullmatch(r"\d+", v) for v in values.values()):
        raise ValueError("video.txt resolution must be an unambiguous integer pair")
    result = int(values["setting.defaultres"]), int(values["setting.defaultresheight"])
    validate_resolution(*result)
    return result


def validate_resolution(width, height):
    if not (640 <= width <= 15360 and 480 <= height <= 8640 and width / height >= 4 / 3 - 0.001):
        raise ValueError("Supported viewport: 640x480 or larger, aspect ratio >= 4:3")


def adapt_resource(text, changes):
    for name, start, end, block in reversed(blocks(text)):
        if name in changes:
            text = text[:start] + set_fields(block, changes[name]) + text[end:]
    return text


def prepare(width, height):
    validate_resolution(width, height)
    baseline = read(BASE)
    files = dict(baseline)
    for path in sorted((ROOT / "modified_c").rglob("*")):
        if path.is_file():
            files[path.relative_to(ROOT / "modified_c").as_posix()] = path.read_bytes()
    value = str(height - 100)
    text = files[MENU].decode("utf-8-sig")
    text = adapt_resource(text, {
        "Expanded_SldHeight": {"maxvalue": value},
        "Init_net_graphheight": {"minvalue": value, "maxvalue": value},
    })
    text = text.replace("1280x720 viewport", f"{width}x{height} viewport")
    text = text.replace("720p profile:", f"{height}p profile:")
    files[MENU] = text.encode("utf-8")
    text = files[NETWORK].decode("utf-8-sig")
    files[NETWORK] = adapt_resource(text, {"SldHeight": {"maxvalue": value}}).replace(
        "720p profile:", f"{height}p profile:"
    ).encode("utf-8")
    cfg = files[CFG].decode("utf-8").replace("1280x720", f"{width}x{height}")
    cfg = re.sub(r"(?m)^net_graphheight \d+$", "net_graphheight " + value, cfg)
    cfg = cfg.replace("Never reuse 620", "Never reuse this pixel value")
    files[CFG] = cfg.encode("utf-8")
    return merge_tumtara(merge_hud(files))


def make_patch(files, width, height):
    baseline = read(BASE)
    changes = {name: content for name, content in files.items() if baseline.get(name) != content}
    diff = []
    for name, content in sorted(changes.items()):
        if name.endswith(".vtf"):
            continue
        old = baseline.get(name, b"").decode("utf-8-sig").splitlines()
        new = content.decode("utf-8-sig").splitlines()
        diff.extend(difflib.unified_diff(
            [s + "\n" for s in old], [s + "\n" for s in new],
            fromfile="a/" + name if name in baseline else "/dev/null", tofile="b/" + name,
        ))
    DIFF.write_text("".join(diff), encoding="utf-8", newline="\n")
    manifest = {
        "base_sha256": BASE_HASH, "result_sha256": digest(OUTPUT.read_bytes()),
        "width": width, "height": height,
        "changes": {name: {"before": digest(baseline[name]) if name in baseline else None,
                           "after": digest(content)} for name, content in changes.items()},
    }
    with zipfile.ZipFile(PATCH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        entries = {"manifest.json": (json.dumps(manifest, indent=2) + "\n").encode(),
                   "C_update.patch": DIFF.read_bytes()}
        entries.update({"payload/" + name: content for name, content in changes.items()})
        for name, content in sorted(entries.items()):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, content)


def apply_patch_bundle():
    assert digest(BASE.read_bytes()) == BASE_HASH
    files = read(BASE)
    with zipfile.ZipFile(PATCH) as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["base_sha256"] == BASE_HASH
        for name, hashes in manifest["changes"].items():
            assert (digest(files[name]) if name in files else None) == hashes["before"]
            content = archive.read("payload/" + name)
            assert digest(content) == hashes["after"]
            files[name] = content
        assert archive.read("C_update.patch") == DIFF.read_bytes()
    validate_files(files, manifest["width"], manifest["height"])
    target = ROOT / "dist/C_patch_replayed.vpk"
    write(target, files)
    assert digest(target.read_bytes()) == manifest["result_sha256"]
    assert target.read_bytes() == OUTPUT.read_bytes()
    print("PASS executable patch bundle recreates C byte-for-byte: " + str(target))


def self_test():
    assert video_resolution('"VideoConfig" { "setting.defaultres" "1280" "setting.defaultresheight" "720" }') == (1280, 720)
    assert video_resolution('"setting.defaultresheight" "1440" "setting.defaultres" "2560"') == (2560, 1440)
    for invalid in ('"setting.defaultres" "1280"', '"setting.defaultres" "0" "setting.defaultresheight" "720"'):
        try:
            video_resolution(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("Malformed video config accepted")
    for width, height in ((640, 480), (1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)):
        validate_files(prepare(width, height), width, height)
        print(f"PASS build-time profile {width}x{height}; height={height - 100}")
    files = prepare(1280, 720)
    files[CFG] = files[CFG].replace(b"net_graphheight 620", b"net_graphheight 2160")
    try:
        validate_files(files, 1280, 720)
    except AssertionError:
        print("PASS negative regression: out-of-window graph height 2160 rejected for 720p")
    else:
        raise AssertionError("Unsafe graph height accepted")


def run_record(args, inputs):
    command = [sys.executable, "-X", "utf8", *args]
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    print(subprocess.list2cmdline(command))
    print(process.stdout, end="")
    if process.stderr:
        print(process.stderr, end="")
    assert process.returncode == 0
    return {"cwd": str(ROOT), "command": command,
            "inputs": {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in inputs},
            "stdout": process.stdout, "stderr": process.stderr, "exit_status": process.returncode}


def build(width, height, video=None):
    assert digest(BASE.read_bytes()) == BASE_HASH
    files = prepare(width, height)
    validate_files(files, width, height)
    preflight = full_audit(None, files)
    if preflight["errors"]:
        raise ValueError("Full audit preflight failed: " + json.dumps(preflight["errors"]))
    OUTPUT.parent.mkdir(exist_ok=True)
    PATCH.parent.mkdir(exist_ok=True)
    write(OUTPUT, files)
    make_patch(files, width, height)
    records = [
        run_record(["tools/verify_tumtara_merge.py", "--baseline"], [BEFORE]),
        run_record(["tools/verify_hud_integration.py", "--baseline"], [PRE_HUD]),
        run_record(["tools/verify_menu.py", str(BASE.relative_to(ROOT)), "--modified"], [BASE]),
        run_record(["tools/verify_c_mod.py", str(OUTPUT.relative_to(ROOT)), "--width", str(width), "--height", str(height)], [BASE, LED, OUTPUT]),
        run_record(["tools/build_c_mod.py", "--apply-patch"], [BASE, PATCH, DIFF, OUTPUT]),
        run_record(["tools/build_c_mod.py", "--self-test"], [BASE, LED]),
        run_record(["tools/rollback_c.py"], [BASE]),
        run_record(["tools/verify_menu.py", "dist/C_before_update_restored.vpk", "--modified"], [ROOT / "dist/C_before_update_restored.vpk"]),
        run_record(["tools/rollback_hud.py"], [PRE_HUD]),
        run_record(["tools/verify_tumtara_merge.py", "--width", str(width), "--height", str(height)], [BEFORE, BUTTONS, MAIN_FILES, OUTPUT]),
        run_record(["tools/rollback_tumtara.py"], [BEFORE]),
    ]
    artifacts = [BASE, LED, HUD, PRE_HUD, BEFORE, BUTTONS, MAIN_FILES, OUTPUT, PATCH, DIFF,
                 ROOT / "reports/C_tumtara_merge.patch", ROOT / "tools/rollback_hud.py",
                 ROOT / "tools/rollback_tumtara.py", ROOT / "dist/C_before_tumtara_restored.vpk"]
    report = {
        "release": {"filename": OUTPUT.name, "path": str(OUTPUT.relative_to(ROOT))},
        "profile": {"width": width, "height": height, "net_graphheight": height - 100,
                    "source": str(video) if video else "explicit profile (default: user-confirmed 1280x720)"},
        "scope": "Archive/resource checks and public SDK coordinate model, not L4D2 runtime tests",
        "artifacts": {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in artifacts},
        "records": records,
        "runtime_checks_remaining": ["actual text/font bounds", "flashlight FOV 200 rendering", "ESC initialization/editability", "cvar acceptance", "health panels and PlayerSpeed HUD rendering/refresh", "TUMTaRA popup placement/clicks and installed map availability"],
        "hud_integration": {"workshop_id": "3230782214", "crosshair": "excluded; existing C crosshair preserved", "speed_position": "donor-default; CItemPickupPanel y=180 and unchanged pickup resource", "diagnostic_cl_showpos": "not enabled"},
        "tumtara": {"buttons": "2256147202", "launcher_resource": "469986973", "maps_bundled": False,
                    "dependency": "Keep Workshop 469986973 installed; optional map launch buttons need their respective map packs"},
        "adaptation_limit": "Re-run with --video after resolution changes; reinstall updated VPK and restart game. No live in-engine adaptation.",
    }
    if video:
        report["video_config_sha256"] = digest(video.read_bytes())
    RECORD.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    saved = json.loads(RECORD.read_text(encoding="utf-8"))
    assert len(saved["records"]) == 11 and all(r["exit_status"] == 0 and not r["stderr"] for r in saved["records"])
    print("VERIFIED " + str(OUTPUT))
    print("SHA256 " + digest(OUTPUT.read_bytes()))
    print(f"PROFILE {width}x{height}: right-aligned network text; height={height - 100}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--video", type=Path, help="Read resolution from L4D2 video.txt; read-only")
    parser.add_argument("--apply-patch", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.apply_patch:
        apply_patch_bundle()
    elif args.self_test:
        self_test()
    else:
        if args.video:
            if args.width is not None or args.height is not None:
                parser.error("Use --video OR --width/--height, not both")
            width, height = video_resolution(args.video.read_text(encoding="utf-8-sig"))
        else:
            if (args.width is None) != (args.height is None):
                parser.error("Provide both --width and --height")
            width, height = (args.width, args.height) if args.width is not None else (1280, 720)
        build(width, height, args.video)


if __name__ == "__main__":
    main()
