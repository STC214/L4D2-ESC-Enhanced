"""Integrate Workshop HUD 3230782214 without replacing C's crosshair.

All resource edits happen in memory while producing the VPK artifact.
The downloaded and extracted originals remain unchanged.
"""

import hashlib
from pathlib import Path

from inspect_menu import TOKEN, blocks, fields
from prepare_menu_patch import set_fields
from vpk import read
from audit_repairs import repair_donor


ROOT = Path(__file__).resolve().parents[1]
HUD = ROOT / "originals/HUD_3230782214.vpk"
HUD_HASH = "3d973dcf9101dc0d21dbd80eb116b7b368a69b8a8b669fb6a72b18dd8254a885"
PRE_HUD = ROOT / "originals/C_before_speed_display.vpk"
PRE_HUD_HASH = "89b3517b10a5e63a9abe9e98323c5d2b854c971ce1dc50fb58a2c12eedbca8c7"
LAYOUT = "scripts/hudlayout.res"
INCAP = "resource/ui/hud/localplayerpanel_incap.res"
TEAM_INCAP = "resource/ui/hud/teammatepanel_incap.res"
PICKUP = "resource/ui/hud/itempickup.res"
SPEED = {
    "ramka", "speedmeter", "arrow", "digits16", "digits13", "digits14", "digits15",
    "avg", "max", "digits12", "digits9", "digits10", "digits11", "digits8",
    "digits17", "digits18", "digits19",
}
EXCLUDED = {
    "addoninfo.txt", "materials/vgui/hud/altcrosshair.vmt",
    "materials/vgui/hud/altcrosshair.vtf", "materials/vgui/hud/xbox_reticle.vtf",
}


def remove_controls(text, names):
    removed = set()
    for name, start, end, _ in reversed(blocks(text)):
        if name in names:
            text = text[:start] + text[end:]
            removed.add(name)
    assert removed == set(names), (removed, names)
    return text


def transform_controls(text, transform):
    for name, start, end, block in reversed(blocks(text)):
        changed = transform(name, block)
        text = text[:start] + changed + text[end:]
    return text


def relocate_pickup(text):
    def move(name, block):
        f = fields(block)
        if name in SPEED:
            # Old speed-group min was (184,140), new min is (12,12).
            return set_fields(block, {"xpos": str(int(f["xpos"]) - 172),
                                      "ypos": str(int(f["ypos"]) - 128)})
        # Parent moves from y=180 to y=0. Preserve every non-speed global y.
        if "ypos" in f:
            return set_fields(block, {"ypos": str(int(f["ypos"]) + 180)})
        return block

    return transform_controls(text, move)


def remap_paths(text, aliases):
    edits = []
    for token in TOKEN.finditer(text):
        if token[0].startswith("//"):
            continue
        value = token[0].strip('"').replace("\\", "/").lower()
        if value in aliases:
            replacement = aliases[value]
            if token[0].startswith('"'):
                replacement = '"' + replacement + '"'
            edits.append((token.start(), token.end(), replacement))
    for start, end, replacement in reversed(edits):
        text = text[:start] + replacement + text[end:]
    return text


def donor_files(existing):
    assert hashlib.sha256(HUD.read_bytes()).hexdigest() == HUD_HASH
    original = read(HUD)
    selected = {name: content for name, content in original.items()
                if name not in EXCLUDED and Path(name).suffix.lower() not in (".pdn", ".tga")}
    aliases, renamed = {}, {}
    for name in selected:
        if name in existing:
            # Only the known unrelated material-name collisions are expected.
            assert name in ("materials/vgui/hud/hmm.vmt", "materials/vgui/hud/hmm.vtf"), name
            suffix = name.removeprefix("materials/vgui/")
            renamed[name] = "materials/vgui/c_hud3230782214/" + suffix
            old = name.removeprefix("materials/").rsplit(".", 1)[0]
            new = renamed[name].removeprefix("materials/").rsplit(".", 1)[0]
            aliases[old] = new
            aliases[old.removeprefix("vgui/")] = new.removeprefix("vgui/")
    result = {}
    for name, content in selected.items():
        if name.endswith((".res", ".vmt")):
            text = content.decode("utf-8-sig")
            if name == LAYOUT:
                text = remove_controls(text, {"CustomCrosshair", "HudCrosshair"})
            elif name == INCAP:
                text = remove_controls(text, {"CustomCrosshair"})
            elif name == TEAM_INCAP:
                # Donor has one surplus final closing brace; preserve every control.
                braces = [m[0] for m in TOKEN.finditer(text) if m[0] in ("{", "}")]
                assert braces.count("}") == braces.count("{") + 1
                last = text.rfind("}")
                text = text[:last] + text[last + 1:]
                blocks(text)
            if aliases:
                text = remap_paths(text, aliases)
            # Preserve original bytes when this resource did not need edits.
            if text != content.decode("utf-8-sig"):
                content = text.encode("utf-8")
        result[renamed.get(name, name)] = repair_donor(name, content)
    assert not (set(existing) & set(result)), set(existing) & set(result)
    return result


def merge(existing):
    result = dict(existing)
    result.update(donor_files(existing))
    return result


if __name__ == "__main__":
    current = read(PRE_HUD)
    imported = donor_files(current)
    print(f"HUD original: {len(read(HUD))} members; imported runtime resources: {len(imported)}")
    print("Crosshair controls removed: normal CustomCrosshair, HudCrosshair, incap CustomCrosshair")
    print("C crosshair resources remain byte-identical; hmm collisions namespaced")
    for name, _, _, block in blocks(imported[PICKUP].decode("utf-8-sig")):
        if name in SPEED:
            f = fields(block)
            print(name, f["xpos"], f["ypos"], f["wide"], f["tall"], f["image"])
