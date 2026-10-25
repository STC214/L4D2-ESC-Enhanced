"""Surgical TUMTaRA launcher merge; maps remain a separate Workshop dependency."""

import hashlib
from pathlib import Path

from inspect_menu import blocks
from kv_audit import parse, scalars
from prepare_menu_patch import set_fields
from vpk import read


ROOT = Path(__file__).resolve().parents[1]
BEFORE = ROOT / "originals/C_before_tumtara_merge.vpk"
BEFORE_HASH = "5eb9113d019b750f00827128bbfb1bcd331feae7e05e23a8dcfa036270a06e0e"
BUTTONS = ROOT / "originals/TUMTARA_2256147202.vpk"
BUTTONS_HASH = "023174c1784458a15489b985d621073361d959258566fce2f4d2ceb81b9fdf40"
MAIN_FILES = ROOT / "originals/TUMTARAMAIN_469986973.vpk"
MAIN_FILES_HASH = "d23e5738e0258896f91ef05425b671b107f06d67bf50a49eb6353c18985a0e32"
MAIN = "resource/ui/l4d360ui/mainmenu.res"
EXTRAS = "resource/ui/l4d360ui/extrasflyout.res"
FLYOUT = "resource/ui/l4d360ui/more/flmtumtara.res"
ADDED = {"RELOAD_UI", "BtnTUMTaRA", "BtnConsole", "Btnserverbrowser", "FlmTUMTaRA"}
NAV = {"BtnStatsAndAchievements": "BtnTUMTaRA", "BtnOptions": "BtnConsole",
       "BtnAddons": "Btnserverbrowser"}


def checked(path, expected):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, path
    return read(path)


def controls(data):
    tree = parse(data.decode("utf-8-sig"))
    assert len(tree) == 1 and isinstance(tree[0].value, list)
    return {n.key: scalars(n.value) for n in tree[0].value if isinstance(n.value, list)}


def launcher_resource():
    # Only UI is imported; never silently bundle 151 MB of maps/scripts/assets.
    return checked(MAIN_FILES, MAIN_FILES_HASH)[FLYOUT]


def merge_main(data):
    text = data.decode("utf-8-sig")
    assert not ADDED.intersection(controls(data))
    for name, start, end, block in reversed(blocks(text)):
        if name in NAV:
            text = text[:start] + set_fields(block, {"navright": NAV[name]}) + text[end:]
    donor = checked(BUTTONS, BUTTONS_HASH)[MAIN].decode("utf-8-sig")
    additions = []
    for name, _, _, block in blocks(donor):
        if name not in ADDED:
            continue
        if name == "FlmTUMTaRA":
            # Preserve donor-relative opening offsets, but give the container real
            # bounds matching its background; scale with the proportional menu.
            block = set_fields(block, {"wide": "400", "tall": "290",
                                       "proportionaltoparent": "1",
                                       "initialfocus": "tum_l4d2_1",
                                       "resourcefile": FLYOUT})
        elif name == "BtnTUMTaRA":
            block = set_fields(block, {"command": "FlmTUMTaRA"})
        additions.append(block)
    assert len(additions) == len(ADDED)
    end = text.rfind("}")
    return (text[:end] + "\n// Integrated TUMTaRA launcher; C controls retained.\n" +
            "\n".join(additions) + "\n" + text[end:]).encode("utf-8")


def merge(files):
    assert FLYOUT not in files
    result = dict(files)
    result[MAIN] = merge_main(files[MAIN])
    result[FLYOUT] = launcher_resource()
    return result


def validate(files):
    before = checked(BEFORE, BEFORE_HASH)
    old, new = controls(before[MAIN]), controls(files[MAIN])
    assert set(new) == set(old) | ADDED
    # Compare exact old control blocks, including conditions/nested game modes.
    old_blocks = {n: b for n, _, _, b in blocks(before[MAIN].decode("utf-8-sig"))}
    new_blocks = {n: b for n, _, _, b in blocks(files[MAIN].decode("utf-8-sig"))}
    for name, block in old_blocks.items():
        expected = set_fields(block, {"navright": NAV[name]}) if name in NAV else block
        assert new_blocks[name] == expected, name
    donor_controls = controls(checked(BUTTONS, BUTTONS_HASH)[MAIN])
    for name in ADDED:
        expected = dict(donor_controls[name])
        if name == "FlmTUMTaRA":
            expected.update(wide="400", tall="290", proportionaltoparent="1",
                            initialfocus="tum_l4d2_1", resourcefile=FLYOUT)
        elif name == "BtnTUMTaRA":
            expected["command"] = "FlmTUMTaRA"
        assert new[name] == expected, (name, "added control fields changed")
    assert files[EXTRAS] == before[EXTRAS], "C toolbox must remain byte-identical"
    assert new["BtnTUMTaRA"]["command"] == new["FlmTUMTaRA"]["fieldname"]
    assert new["FlmTUMTaRA"]["resourcefile"] == FLYOUT
    assert files[FLYOUT] == launcher_resource()
    menu = controls(files[FLYOUT])
    assert menu["PnlBackground"]["wide"] == "400"
    assert menu["PnlBackground"]["tall"] == "290"
    assert new["FlmTUMTaRA"]["wide"] == "400" and new["FlmTUMTaRA"]["tall"] == "290"
    for name in ADDED:
        for key, value in new[name].items():
            if key.startswith("nav") and value:
                assert value in new, (name, key, value)
    # Finite donor-relative anchor model: both button-origin and right-edge
    # variants fit a 640x480 logical viewport. Actual engine placement pending.
    button, popup = new["BtnTUMTaRA"], new["FlmTUMTaRA"]
    for edge in (0, int(button["wide"])):
        x = int(button["xpos"]) + edge + int(popup["xpos"])
        y = int(button["ypos"]) + int(popup["ypos"])
        assert 0 <= x and x + int(popup["wide"]) <= 640
        assert 0 <= y and y + int(popup["tall"]) <= 480
    for name, f in menu.items():
        if f.get("controlname") in ("Label", "L4D360HybridButton"):
            x, y, w, h = (int(f[k]) for k in ("xpos", "ypos", "wide", "tall"))
            assert 0 <= x and x + w <= 400 and 0 <= y and y + h <= 290, name
    assert menu["tum_l4d2_1"]["command"] == "#con_enable 1;map tumtara"
    assert menu["tum_l4d1_1"]["command"] == "#con_enable 1;map tumtara_l4d1"
    print("PASS TUMTaRA button -> FlyoutMenu -> packaged real launcher resource; C toolbox preserved")
    print("PASS C original main-menu blocks retained; only 3 right-navigation fields added")
    print("NOT TESTED: engine flyout placement/clicks; maps require Workshop 469986973; optional map buttons require their own maps")


if __name__ == "__main__":
    original = checked(BEFORE, BEFORE_HASH)
    merged = merge(original)
    validate(merged)
    print("PASS in-memory merge; only mainmenu.res replaced and one launcher resource added")
