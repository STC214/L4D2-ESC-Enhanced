"""Static VPK/resource verification, deliberately not a game-runtime test."""

import argparse
import hashlib
import json
from pathlib import Path

from inspect_menu import TOKEN, blocks, fields
from vpk import read


ROOT = Path(__file__).resolve().parents[1]
MENU = "resource/ui/l4d360ui/ingamemainmenu.res"
DEFAULTS = {
    "fog_enable": "0", "cl_ragdoll_maxcount": "0",
    "sv_disable_glow_survivors": "0", "sv_disable_glow_faritems": "0",
    "r_flashlightconstant": "1", "r_flashlightfar": "3000",
    "r_flashlightfov": "179",
}


def all_scalar_fields(text):
    """Collect original and edited token streams for syntax consistency checks."""
    tokens = [m[0] for m in TOKEN.finditer(text) if not m[0].startswith("//")]
    depth = 0
    for token in tokens:
        depth += (token == "{") - (token == "}")
        assert depth >= 0
    assert depth == 0
    return tokens


def coordinate(value, length, extent):
    if value.startswith("c"):
        return length / 2 + float(value[1:] or 0)
    if value.startswith("r"):
        return length - float(value[1:])
    return float(value)


def validate(text):
    all_scalar_fields(text)
    controls = blocks(text)
    names = [n for n, _, _, _ in controls]
    original = read(ROOT / "originals/B_2906960647.vpk")
    baseline = blocks(original[MENU].decode("utf-8-sig"))
    by_name = {n: fields(b) for n, _, _, b in controls}
    # The one existing duplicate decorative name remains hidden in both locations.
    assert len(names) - len(set(names)) == 1
    for name, _, _, block in baseline:
        assert name in by_name, name
        old, new = fields(block), by_name[name]
        if old.get("controlname") == "SliderControl":
            for key in ("controlname", "concommand", "minvalue", "maxvalue", "stepsize", "inversefill"):
                assert old.get(key) == new.get(key), (name, key)
        if old.get("controlname") == "L4D360HybridButton":
            assert old.get("command") == new.get("command"), name
    for command, value in DEFAULTS.items():
        control = by_name["Init_" + command]
        assert control["concommand"] == command
        assert control["minvalue"] == control["maxvalue"] == value
        assert control["visible"] == control["enabled"] == "1"
        assert control["ypos"] == "9999"
    assert by_name["InGameMainMenu"]["wide"] == "f0"
    assert by_name["InGameMainMenu"]["tall"] == "f0"
    visible = []
    slider_count = 0
    for name, _, _, block in controls:
        f = fields(block)
        if f.get("controlname") in ("SliderControl", "L4D360HybridButton", "DropDownMenu") and not name.startswith("Init_"):
            assert f.get("visible") == "1"
            assert float(f["tall"]) >= 15
            visible.append((name, f))
            slider_count += f["controlname"] == "SliderControl"
    for width in (640, 768, 853.3333333333, 1120, 2560):
        boxes = []
        for name, f in visible:
            w, h = float(f["wide"]), float(f["tall"])
            x = coordinate(f["xpos"], width, w)
            y = coordinate(f["ypos"], 480, h)
            assert 0 <= x and x + w <= width and 0 <= y and y + h <= 480, (width, name)
            for other, ox, oy, ow, oh in boxes:
                assert not (x < ox + ow and ox < x + w and y < oy + oh and oy < y + h), (width, name, other)
            boxes.append((name, x, y, w, h))
    # Flattened controls must preserve all source sliders' ranges/steps.
    commands = {fields(b).get("concommand") for _, _, _, b in controls if not fields(b).get("fieldname", "").startswith("Init_")}
    for filename in ("dropdowncrosshair.res", "dropdownnetgraph.res", "dropdownweathercontrol.res"):
        source = original["resource/ui/l4d360ui/" + filename].decode("utf-8-sig")
        for name, _, _, block in blocks(source):
            old = fields(block)
            if old.get("controlname") == "SliderControl":
                assert old["concommand"] in commands
                if "Expanded_" + name in by_name:
                    new = by_name["Expanded_" + name]
                    for key in ("concommand", "minvalue", "maxvalue", "stepsize", "inversefill"):
                        assert old.get(key) == new.get(key)
    print(f"PASS resource syntax; original control identities/actions/ranges preserved")
    print(f"PASS {slider_count} visible sliders; {len(visible) - slider_count} action/dropdown controls")
    print("PASS non-overlap and bounds at 4:3, 16:10, 16:9, 21:9, 48:9 (480-unit canvas)")
    print("PASS seven initializer values: " + json.dumps(DEFAULTS, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--modified", action="store_true")
    args = parser.parse_args()
    if args.path.suffix == ".res":
        validate(args.path.read_text(encoding="utf-8-sig"))
        return
    files = read(args.path)
    print("SHA256 " + hashlib.sha256(args.path.read_bytes()).hexdigest())
    print(f"PASS VPK header/tree/payload CRC: {len(files)} members")
    if args.modified:
        baseline = read(ROOT / "originals/B_2906960647.vpk")
        assert set(baseline).issubset(files)
        assert set(files) - set(baseline) == {"cfg/l4d2esc_defaults.cfg"}
        changed = [name for name in baseline if baseline[name] != files[name]]
        assert changed == [MENU], changed
        print("PASS all original members byte-identical except " + MENU)
        cfg = files["cfg/l4d2esc_defaults.cfg"].decode("utf-8")
        lines = [line.strip().split() for line in cfg.splitlines() if line.strip() and not line.lstrip().startswith("//")]
        assert dict(lines) == DEFAULTS and len(lines) == 7
        validate(files[MENU].decode("utf-8-sig"))
    else:
        text = files[MENU].decode("utf-8-sig")
        all_scalar_fields(text)
        print("BASELINE " + str(len(blocks(text))) + " top-level controls; original unmodified resource")
    print("NOT TESTED: L4D2 rendering, menu initialization timing, server cvar acceptance")


if __name__ == "__main__":
    main()
