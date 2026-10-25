"""Independent finite checks for HUD integration, not an L4D2 renderer."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from hud_integration import (
    EXCLUDED, HUD, HUD_HASH, INCAP, LAYOUT, PICKUP, PRE_HUD,
    PRE_HUD_HASH, ROOT, SPEED, TEAM_INCAP, donor_files,
)
from inspect_menu import blocks, fields
from vpk import read
from proxy_model import speed_samples
from tumtara_integration import MAIN, FLYOUT, validate as validate_tumtara


def index(content):
    return {name: fields(block) for name, _, _, block in blocks(content.decode("utf-8-sig"))}


def validate_baseline():
    assert hashlib.sha256(PRE_HUD.read_bytes()).hexdigest() == PRE_HUD_HASH
    baseline = read(PRE_HUD)
    assert len(baseline) == 76
    assert LAYOUT not in baseline and PICKUP not in baseline
    assert b"cl_showpos" not in baseline["cfg/l4d2esc_defaults.cfg"]
    print("PASS pre-HUD C: 76 CRC-verified members; no donor HUD/speedometer")
    print("SHA256 " + PRE_HUD_HASH)


def validate(files, width=1280, height=720):
    before = read(PRE_HUD)
    assert hashlib.sha256(PRE_HUD.read_bytes()).hexdigest() == PRE_HUD_HASH
    assert hashlib.sha256(HUD.read_bytes()).hexdigest() == HUD_HASH
    donor = read(HUD)
    imported = donor_files(before)
    has_tumtara = FLYOUT in files
    assert set(files) - set(before) == set(imported) | ({FLYOUT} if has_tumtara else set())
    if has_tumtara:
        validate_tumtara(files)
    for name in before:
        if has_tumtara and name == MAIN:
            continue  # Exact old control-block preservation checked above.
        if height == 720 or name not in (
            "resource/ui/l4d360ui/ingamemainmenu.res",
            "resource/ui/l4d360ui/dropdownnetgraph.res", "cfg/l4d2esc_defaults.cfg",
        ):
            if name == "resource/ui/l4d360ui/ingamemainmenu.res":
                normalized, count = re.subn(
                    rb'("fieldName"\s+")c_thirdpersonshoulderheight-(")',
                    rb'\1c_thirdpersonshoulderheight\2', files[name],
                )
                assert count == 1 and normalized == before[name], name
            else:
                assert files[name] == before[name], name
    for name, content in imported.items():
        assert files[name] == content, name
        if name.endswith(".res"):
            try:
                blocks(content.decode("utf-8-sig"))
            except AssertionError as exc:
                raise AssertionError("Unbalanced HUD resource: " + name) from exc
    last = donor[TEAM_INCAP].rfind(b"}")
    fixed_brace = donor[TEAM_INCAP][:last] + donor[TEAM_INCAP][last + 1:]
    old_team, new_team = index(fixed_brace), index(files[TEAM_INCAP])
    assert set(old_team) == set(new_team)
    for name, old in old_team.items():
        expected = dict(old)
        if name == "DownSign":
            expected["fieldname"] = "DownSign"
        assert new_team[name] == expected
    for name in EXCLUDED:
        if name in before:
            assert files[name] == before[name]
        else:
            assert name not in files
    assert not any(name.endswith((".pdn", ".tga")) for name in set(files) - set(before))
    layout, old_layout = index(files[LAYOUT]), index(donor[LAYOUT])
    assert set(layout) == set(old_layout) - {"CustomCrosshair", "HudCrosshair"}
    assert layout["CItemPickupPanel"]["ypos"] == "180"
    assert layout["CItemPickupPanel"]["xpos"] == "0"
    assert layout["CItemPickupPanel"]["wide"] == layout["CItemPickupPanel"]["tall"] == "f0"
    for name, old in old_layout.items():
        if name in ("CustomCrosshair", "HudCrosshair"):
            continue
        expected = dict(old)
        assert layout[name] == expected, name
    assert set(index(files[INCAP])) == set(index(donor[INCAP])) - {"CustomCrosshair"}
    for name, old in index(donor[INCAP]).items():
        if name != "CustomCrosshair":
            expected = dict(old)
            if name == "DownSign":
                expected["fieldname"] = "DownSign"
            assert index(files[INCAP])[name] == expected
    for content in (files[LAYOUT], files[INCAP]):
        assert b"CustomCrosshair" not in content and b"gfx\\vgui\\defaultweapon" not in content
    old_pickup, pickup = index(donor[PICKUP]), index(files[PICKUP])
    assert set(pickup) == set(old_pickup)
    for name, old in old_pickup.items():
        expected = dict(old)
        if name in SPEED:
            x, y, w, h = (int(pickup[name][key]) for key in ("xpos", "ypos", "wide", "tall"))
            assert 184 <= x and x + w <= 310 and 140 <= y and y + h <= 284
            material = "materials/vgui/" + pickup[name]["image"] + ".vmt"
            assert material in files, material
        assert pickup[name] == expected, name
    assert files[PICKUP] == donor[PICKUP]
    assert b"PlayerSpeed" in files["materials/vgui/hud/arrow.vmt"]
    for number in (8, 17, 18, 19):
        material = files[f"materials/vgui/hud/digits_{number}.vmt"]
        assert b"PlayerSpeed" in material and b'"$frame"' in material
    assert all(row["pass"] for row in speed_samples(files))
    for panel in ("localplayerpanel", "localplayerpanel_incap", "teammatepanel", "teammatepanel_incap"):
        controls = index(files[f"resource/ui/hud/{panel}.res"])
        assert "Health" in controls and controls["Health"]["controlname"] == "HealthPanel"
    assert b"cl_showpos" not in files["cfg/l4d2esc_defaults.cfg"]
    assert b"Init_cl_showpos" not in files["resource/ui/l4d360ui/ingamemainmenu.res"]
    print(f"PASS HUD integration: {len(imported)} imported runtime resources; {len(files)} total members")
    print("PASS donor crosshair controls/textures excluded; all C crosshair/material collisions preserved")
    print("PASS 17 speed controls at donor-default positions; parent y=180; pickup resource byte-identical")
    print("PASS native PlayerSpeed source; repaired integer speed frames pass finite proxy model")
    print("PASS normal/incap player and teammate health panels; timers/other HUD controls retained")
    print("PASS no cl_showpos diagnostic overlay and no movement-parameter changes")
    print("NOT TESTED: in-game HUD loading, PlayerSpeed binding/visual refresh, health animations, mode interactions")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", nargs="?", type=Path)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args()
    if args.baseline:
        validate_baseline()
    elif args.archive:
        validate(read(args.archive), args.width, args.height)
    else:
        before = read(PRE_HUD)
        validate(before | donor_files(before))


if __name__ == "__main__":
    main()
