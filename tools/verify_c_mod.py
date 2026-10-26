"""Validate C's continuation against the preserved C package and source layout."""

import argparse
import hashlib
from pathlib import Path

from inspect_menu import blocks, fields
from verify_menu import all_scalar_fields, coordinate
from vpk import read
from hud_integration import PRE_HUD, donor_files
from verify_hud_integration import validate as validate_hud
from tumtara_integration import MAIN, FLYOUT, validate as validate_tumtara
from c_session_policy import validate as validate_session


ROOT = Path(__file__).resolve().parents[1]
MENU = "resource/ui/l4d360ui/ingamemainmenu.res"
NETWORK = "resource/ui/l4d360ui/dropdownnetgraph.res"
CFG = "cfg/l4d2esc_defaults.cfg"
BASE = ROOT / "originals/C_before_network_defaults.vpk"
LED = ROOT / "originals/LED_638169501.vpk"
BASE_HASH = "ba3f39a3115e9cda4bf32213277095de52435198e41c6dc55d18f0eadd6797bf"
LED_HASH = "a605fdbc5b2c6594f6e6c5a933dfc43399b64cd22cf75586dffa60a44c1ef3ce"
TEXTURES = {"materials/effects/flashlight001.vtf", "materials/effects/flashlight001_infected.vtf"}


def defaults(height):
    assert 480 <= height <= 8640
    return {
        "fog_enable": "0", "cl_ragdoll_maxcount": "0",
        "sv_disable_glow_survivors": "0", "sv_disable_glow_faritems": "0",
        "r_flashlightconstant": "1", "r_flashlightfar": "3000", "r_flashlightfov": "53",
        "net_graph": "1", "net_graphpos": "1", "net_graphheight": str(height - 100),
        "net_graphproportionalfont": "0", "net_graphtext": "1",
    }


def controls(text):
    all_scalar_fields(text)
    return {n: fields(b) for n, _, _, b in blocks(text)}


def validate_menu(text, height):
    new = controls(text)
    old = controls(read(BASE)[MENU].decode("utf-8-sig"))
    for name, original in old.items():
        if name.startswith("Init_"):
            continue
        assert name in new, name
        current = new[name]
        for key, value in original.items():
            if name == "c_thirdpersonshoulderheight-" and key == "fieldname":
                assert current[key] == "c_thirdpersonshoulderheight-"
            elif name == "Flashlightfov" and key == "maxvalue":
                assert current[key] == "200"
            elif name == "Flashlightfov" and key == "minvalue":
                assert current[key] == "50"
            elif name == "Expanded_SldHeight" and key == "maxvalue":
                assert current[key] == str(height - 100)
            elif name == "Init_r_flashlightfov" and key in ("minvalue", "maxvalue"):
                assert current[key] == "200"
            else:
                assert current.get(key) == value, (name, key, value, current.get(key))
    assert not any(name.startswith("Init_") for name in new)
    assert len(new) == len(old) - 7
    # Existing layout is unchanged; independently check visible controls' bounds.
    for width in (640, 768, 480 * 16 / 9, 1120):
        boxes = []
        for name, f in new.items():
            if f.get("controlname") not in ("SliderControl", "L4D360HybridButton", "DropDownMenu") or name.startswith("Init_"):
                continue
            w, h = float(f["wide"]), float(f["tall"])
            x, y = coordinate(f["xpos"], width, w), float(f["ypos"])
            assert 0 <= x <= width - w and 0 <= y <= 480 - h
            for ox, oy, ow, oh in boxes:
                assert not (x < ox + ow and ox < x + w and y < oy + oh and oy < y + h)
            boxes.append((x, y, w, h))
    print("PASS existing C menu geometry/actions/unrelated parameters preserved")
    print("PASS shared flashlight FOV native default = 53; both sliders accept 53")
    print(f"PASS no ESC initializers; session CFG has {len(defaults(height))} defaults; graph height={height - 100}")


def validate_files(files, width, height):
    if "手电光圈".encode() in files.get(MENU, b""):
        from c_menu_consolidation import validate
        validate(files, width, height)
        return
    validate_session(files, width, height)
    baseline, dependency = read(BASE), read(LED)
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_HASH
    assert hashlib.sha256(LED.read_bytes()).hexdigest() == LED_HASH
    assert set(files) - set(baseline) == TEXTURES | set(donor_files(read(PRE_HUD))) | {FLYOUT}
    assert set(baseline) <= set(files)
    assert {n for n in baseline if baseline[n] != files[n]} == {MENU, NETWORK, CFG, MAIN}
    validate_tumtara(files)
    for name in TEXTURES:
        assert files[name] == dependency[name]
        assert files[name][:4] == b"VTF\0"
    old, new = controls(baseline[NETWORK].decode("utf-8-sig")), controls(files[NETWORK].decode("utf-8-sig"))
    for name in old:
        for key, value in old[name].items():
            expected = str(height - 100) if name == "SldHeight" and key == "maxvalue" else value
            assert new[name].get(key) == expected, (name, key)
    cfg = files[CFG].decode("utf-8")
    lines = [line.strip().split() for line in cfg.splitlines() if line.strip() and not line.lstrip().startswith("//")]
    assert dict(lines) == defaults(height) and len(lines) == len(defaults(height))
    validate_menu(files[MENU].decode("utf-8-sig"), height)
    assert width >= 640 and width / height >= 4 / 3 - 0.001
    # Finite model from Valve's public SDK, NOT L4D2 runtime evidence.
    # Text-only mode has no graph art above the text. H - 29 - max(3*font, height).
    for font_tall in range(10, 33):
        effective = max(3 * font_tall, height - 100)
        top = height - 29 - effective
        assert top >= 16 and top + 4 * font_tall < height
    assert height - 100 < height - 29
    print("PASS graph height cap in both menu entries; SDK text-top model leaves 71 px (fonts 10..32)")
    print("PASS two LED texture payloads byte-identical to required Workshop item; no gameplay-resource conflicts")
    validate_hud(files, width, height)
    print(f"PASS {len(files)} CRC-verified members; only 4 early-C members changed, LED/HUD/TUMTaRA UI added")
    print("NOT TESTED: L4D2 rendering/cvar acceptance, actual font/text extent, ESC initialization timing")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--menu-only", action="store_true")
    args = parser.parse_args()
    if args.menu_only:
        validate_menu(args.path.read_text(encoding="utf-8-sig"), args.height)
    else:
        validate_files(read(args.path), args.width, args.height)
        print("SHA256 " + hashlib.sha256(args.path.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
