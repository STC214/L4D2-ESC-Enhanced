"""Latest C menu layer, applied to the pinned session-defaults release.

The earlier build_c_mod.py remains a historical baseline builder. This layer
preserves every unrelated packaged byte and uses the existing helper for the
one-shot per-map ESC event; resource slider limits never implement that event.
"""

import argparse
from collections import defaultdict
import difflib
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import zipfile

from audit_c import inspect
from c_chat_layout import CHAT, LAYOUT, apply as apply_chat, validate as validate_chat
from inspect_menu import blocks, fields
from kv_audit import parse, scalars, walk
from prepare_menu_patch import set_fields
from release_paths import ROOT, OUTPUT, C_FILENAME
from tumtara_integration import validate as validate_tumtara
from verify_menu import coordinate
from vpk import read, write

BASE = ROOT / "originals/C_before_menu_consolidation.vpk"
BASE_HASH = "b6b4819c711728d5a647ca341f1c93aef480294171bc55b824e3f0bcb58dc650"
OLD_DLL = ROOT / "originals/CSessionDefaults_before_menu_consolidation.dll"
OLD_DLL_HASH = "1de98ccb2c430bb510ac33c1dca70948c1e4eff8c742b6038e93ed6f47dbf857"
DLL = ROOT / "dist/c_session_helper/CSessionDefaults.dll"
MENU = "resource/ui/l4d360ui/ingamemainmenu.res"
CFG = "cfg/l4d2esc_defaults.cfg"
AUDIO = "resource/ui/l4d360ui/audio.res"
SUBMENUS = tuple("resource/ui/l4d360ui/" + n for n in (
    "dropdowncrosshair.res", "dropdownnetgraph.res", "dropdownweathercontrol.res"))
CHANGED = {MENU, CFG, CHAT, LAYOUT, *SUBMENUS}
PATCH = ROOT / "reports/c_menu_consolidation/patch.zip"
DIFF = ROOT / "reports/c_menu_consolidation/menus.patch"
BUNDLE = ROOT / "dist/C_session_release.zip"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def baseline():
    assert sha(BASE.read_bytes()) == BASE_HASH
    assert sha(OLD_DLL.read_bytes()) == OLD_DLL_HASH
    return read(BASE)


def bindings(files):
    result = defaultdict(list)
    for path, data in files.items():
        if not path.endswith(".res"):
            continue
        for location, node in walk(parse(data.decode("utf-8-sig"))):
            if isinstance(node.value, list):
                props = scalars(node.value)
                command = props.get("concommand", "").strip().lower()
                if command:
                    result[command].append((path, node.key, props))
    return result


def labels(block, text):
    return re.sub(r'("labeltext"\s+")[^"\n]*(")',
                  lambda m: m[1] + text + m[2], block, flags=re.I)


def transform(files, width=1280, height=720):
    result = dict(files)
    duplicates = {c: refs for c, refs in bindings(files).items() if len(refs) > 1}
    assert len(duplicates) == 18, "Unexpected baseline menu bindings"
    removed = {"SldGameVolume", "SldMusicVolume", "GuangSheJiao",
               "thirdpersonshoulderoffset+", "DrpCrosshair", "DrpNetGraph",
               "FlmCrosshair", "FlmNetGraph", "WeatherControl"}
    text = files[MENU].decode("utf-8-sig")
    old = {n: fields(b) for n, _, _, b in blocks(text)}
    assert removed <= old.keys()
    sliders = [n for n, _, _, b in blocks(text)
               if fields(b).get("controlname") == "SliderControl" and n not in removed]
    rows = math.ceil(len(sliders) / 2)
    assert rows <= 24

    def target(name, direction):
        seen = set()
        while name in removed and name not in seen:
            seen.add(name)
            name = old[name].get(direction, "")
        return name if name in old and name not in removed else sliders[0]

    for name, start, end, block in reversed(blocks(text)):
        if name in removed:
            text = text[:start] + text[end:]
            continue
        props = fields(block)
        changes = {k: target(v, k) for k, v in props.items()
                   if k.startswith("nav") and v and (v in removed or v not in old)}
        if name in sliders:
            index = sliders.index(name)
            column, row = divmod(index, rows)
            column_names = sliders[column * rows:(column + 1) * rows]
            changes.update(xpos="c-92" if column == 0 else "r196",
                           ypos=str(14 + row * 19),
                           navup=column_names[(row - 1) % len(column_names)],
                           navdown=column_names[(row + 1) % len(column_names)])
        if name == "Flashlightfov":
            changes.update(minvalue="50", maxvalue="200", stepsize="1")
            block = labels(block, "手电光圈")
            block = block.replace("//光射角锁100", "// Adjustable; first ESC is handled by the companion helper.")
            block = block.replace("与“修复黑块”共用参数，保持一致的上限", "Merged flashlight cone range; no fixed initialization bound")
        if name == "c_thirdpersonshoulderheight-":
            changes.update(minvalue="-1000", maxvalue="1000")
            block = labels(block, "第三人称左右偏移")
        if name == "Expanded_SldHeight":
            changes["maxvalue"] = str(height - 100)
        if changes:
            block = set_fields(block, changes)
        text = text[:start] + block + text[end:]
    result[MENU] = text.encode("utf-8")
    for path in SUBMENUS:
        text = files[path].decode("utf-8-sig")
        for _, start, end, block in reversed(blocks(text)):
            if fields(block).get("concommand", "").lower() in duplicates:
                text = text[:start] + text[end:]
        result[path] = text.encode("utf-8")
    # Keep all previous defaults, including 53 until the first ESC event. The
    # new one-shot 150 command is intentionally not in this connection CFG.
    cfg = files[CFG].decode("utf-8")
    cfg = cfg.replace("1280x720", f"{width}x{height}")
    cfg = re.sub(r"(?m)^net_graphheight \d+$", "net_graphheight " + str(height - 100), cfg)
    cfg += "\n// Weather defaults; apply once on a new connection, never every ESC.\n"
    cfg += "r_RainParticleDensity 0\nr_SnowParticles 0\nfog_override 0\n"
    result[CFG] = cfg.encode("utf-8")
    return apply_chat(result)


def validate(files, width=None, height=None):
    before = baseline()
    assert set(files) == set(before), "HUD/LED/TUMTaRA inventory changed"
    assert {p for p in before if before[p] != files[p]} == CHANGED
    profile = re.search(r"Profile: (\d+)x(\d+)\.", files[CFG].decode("utf-8"))
    assert profile, "Missing resolution profile"
    actual_width, actual_height = map(int, profile.groups())
    if width is not None or height is not None:
        assert (width, height) == (actual_width, actual_height)
    from build_c_mod import validate_resolution
    validate_resolution(actual_width, actual_height)
    expected = transform(before, actual_width, actual_height)
    assert files == expected, "Unexpected payload or missing consolidation change"
    validate_chat(files)
    duplicates = {c: refs for c, refs in bindings(files).items() if len(refs) > 1}
    assert not duplicates, duplicates
    assert set(bindings(before)) == set(bindings(files)), "A distinct setting was lost"
    nodes = {n: (fields(b), b) for n, _, _, b in blocks(files[MENU].decode("utf-8-sig"))}
    fov, block = nodes["Flashlightfov"]
    assert "手电光圈" in block and "修复黑块" not in files[MENU].decode("utf-8-sig")
    assert fov["minvalue"] == "50" and fov["maxvalue"] == "200"
    assert not any(n.startswith("Init_") for n in nodes)
    offset = nodes["c_thirdpersonshoulderheight-"][0]
    assert (offset["minvalue"], offset["maxvalue"]) == ("-1000", "1000")
    cfg = dict(line.split() for line in files[CFG].decode("utf-8").splitlines()
               if line.strip() and not line.lstrip().startswith("//"))
    for command in ("r_RainParticleDensity", "r_SnowParticles", "fog_override", "fog_enable"):
        assert cfg[command] == "0"
    for command in ("r_rainparticledensity", "r_snowparticles", "fog_override", "fog_enable"):
        props = bindings(files)[command][0][2]
        assert float(props["minvalue"]) == 0
    assert files[AUDIO] == before[AUDIO], "Keep audio menu usable before joining a map"
    for width in (640, 768, 480 * 16 / 9, 1120):
        rectangles = []
        for name, (props, _) in nodes.items():
            if props.get("controlname") not in ("SliderControl", "L4D360HybridButton", "DropDownMenu"):
                continue
            w, h = float(props["wide"]), float(props["tall"])
            x, y = coordinate(props["xpos"], width, w), float(props["ypos"])
            assert 0 <= x <= width - w and 0 <= y <= 480 - h, name
            for ox, oy, ow, oh in rectangles:
                assert not (x < ox + ow and ox < x + w and y < oy + oh and oy < y + h), name
            rectangles.append((x, y, w, h))
    # Removed controls must not leave a keyboard/controller navigation target.
    removed_names = {"SldGameVolume", "SldMusicVolume", "GuangSheJiao", "thirdpersonshoulderoffset+",
                     "DrpCrosshair", "DrpNetGraph", "FlmCrosshair", "FlmNetGraph", "WeatherControl"}
    for _, node in walk(parse(files[MENU].decode("utf-8-sig"))):
        if isinstance(node.value, str) and node.key.lower().startswith("nav"):
            assert node.value not in removed_names
            assert not node.value or node.value in nodes, (node.key, node.value)
    validate_tumtara(files)
    audit = inspect(None, files)
    assert not audit["errors"], audit["errors"]
    print(f"PASS {len(files)} CRC members; {len(bindings(files))} distinct bindings; zero duplicate writers")
    print("PASS unified FOV 50..200; camera offset -1000..1000; weather minima/defaults all 0")
    print("PASS audio settings retained; layout/navigation checked; unrelated HUD/LED/TUMTaRA bytes unchanged")
    return audit


def package():
    validate(read(OUTPUT))
    build = json.loads((ROOT / "reports/c_session_plugin_build.json").read_text(encoding="utf-8"))
    assert sha(DLL.read_bytes()) == build["dll_sha256"]
    payload = {"left4dead2/addons/" + C_FILENAME: OUTPUT.read_bytes(),
               "bin/neko/plugins/CSessionDefaults.dll": DLL.read_bytes()}
    manifest = {"runtime_status": "NOT_TESTED", "helper_version": "1.1.0",
                "chat_layout": "bottom-right; right margin 17 and bottom HUD clearance 80 VGUI units",
                "engine_sha256": build["engine_profile_sha256"],
                "first_escape": "once per playable map; FOV 150, not enforced afterwards",
                "files": {p: sha(b) for p, b in payload.items()}}
    payload["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    with zipfile.ZipFile(BUNDLE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, data in sorted(payload.items()):
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    with zipfile.ZipFile(BUNDLE) as archive:
        assert archive.testzip() is None
        assert {p: archive.read(p) for p in archive.namelist()} == payload
    print("PASS two-part install bundle reopened: " + str(BUNDLE))


def build(width=1280, height=720):
    from build_c_mod import validate_resolution
    validate_resolution(width, height)
    before = baseline()
    files = transform(before, width, height)
    validate(files)
    write(OUTPUT, files)
    assert read(OUTPUT) == files
    PATCH.parent.mkdir(parents=True, exist_ok=True)
    diff = "".join("".join(difflib.unified_diff(
        before[p].decode("utf-8-sig").splitlines(keepends=True),
        files[p].decode("utf-8-sig").splitlines(keepends=True),
        fromfile="a/" + p, tofile="b/" + p)) for p in sorted(CHANGED))
    DIFF.write_text(diff, encoding="utf-8", newline="\n")
    manifest = {"base_sha256": BASE_HASH, "result_sha256": sha(OUTPUT.read_bytes()),
                "width": width, "height": height,
                "helper_before": OLD_DLL_HASH, "helper_after": sha(DLL.read_bytes()),
                "changes": {p: {"before": sha(before[p]), "after": sha(files[p])} for p in sorted(CHANGED)}}
    with zipfile.ZipFile(PATCH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr("menus.patch", DIFF.read_bytes())
        archive.writestr("CSessionDefaults.dll", DLL.read_bytes())
        for path in sorted(CHANGED):
            archive.writestr("payload/" + path, files[path])
    package()
    print("RESULT SHA256 " + sha(OUTPUT.read_bytes()))


def replay():
    files = baseline()
    with zipfile.ZipFile(PATCH) as archive:
        assert archive.testzip() is None
        meta = json.loads(archive.read("manifest.json"))
        assert meta["base_sha256"] == BASE_HASH
        assert sha(archive.read("CSessionDefaults.dll")) == meta["helper_after"] == sha(DLL.read_bytes())
        assert archive.read("menus.patch") == DIFF.read_bytes()
        for path, hashes in meta["changes"].items():
            assert sha(files[path]) == hashes["before"]
            files[path] = archive.read("payload/" + path)
            assert sha(files[path]) == hashes["after"]
    validate(files)
    target = ROOT / "reports/c_menu_consolidation/replayed.vpk"
    write(target, files)
    assert sha(target.read_bytes()) == meta["result_sha256"]
    assert target.read_bytes() == OUTPUT.read_bytes()
    print("PASS patch replay equals published VPK; helper payload equals published DLL")


def rollback_copy():
    baseline()
    directory = ROOT / "dist/rollback_menu_consolidation"
    directory.mkdir(parents=True, exist_ok=True)
    for source, name in ((BASE, C_FILENAME), (OLD_DLL, "CSessionDefaults.dll")):
        target = directory / name
        shutil.copyfile(source, target)
        assert target.read_bytes() == source.read_bytes()
    assert read(directory / C_FILENAME) == baseline()
    print("PASS original VPK/DLL restored to verified rollback copies: " + str(directory))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("baseline", "build", "verify", "replay", "rollback-copy"))
    args = parser.parse_args()
    if args.action == "baseline":
        old = bindings(baseline())
        print("BASELINE duplicate groups=" + str(sum(len(v) > 1 for v in old.values())))
        print("BASELINE FOV default 53; no first-ESC handler in helper 1.0.1")
        print("BASE SHA256 " + BASE_HASH)
    elif args.action == "build":
        build()
    elif args.action == "verify":
        validate(read(OUTPUT))
    elif args.action == "replay":
        replay()
    else:
        rollback_copy()


if __name__ == "__main__":
    main()
