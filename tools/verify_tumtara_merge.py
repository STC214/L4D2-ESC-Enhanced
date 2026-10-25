"""Verify exact task delta versus the latest delivered, audited C."""

import argparse
import difflib
import hashlib

from hud_integration import HUD, HUD_HASH, LAYOUT, PICKUP
from tumtara_integration import (
    BEFORE, BEFORE_HASH, MAIN, EXTRAS, FLYOUT, ROOT, checked, controls, validate,
)
from vpk import read
from release_paths import OUTPUT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args()
    before = checked(BEFORE, BEFORE_HASH)
    assert len(before) == 221 and FLYOUT not in before
    assert "BtnTUMTaRA" not in controls(before[MAIN])
    assert controls(before[LAYOUT])["CItemPickupPanel"]["ypos"] == "0"
    assert controls(before[PICKUP])["speedmeter"]["xpos"] == "37"
    print("PASS baseline: audited C, 221 members, no TUMTaRA entry/resource; speed relocated top-left")
    print("BASE SHA256 " + BEFORE_HASH)
    if args.baseline:
        return
    target = OUTPUT
    files = read(target)
    assert set(files) - set(before) == {FLYOUT}
    assert set(before) <= set(files)
    changed = {n for n in before if before[n] != files[n]}
    required = {MAIN, LAYOUT, PICKUP, "resource/ui/l4d360ui/ingamemainmenu.res", "cfg/l4d2esc_defaults.cfg"}
    if (args.width, args.height) == (1280, 720):
        assert changed == required, changed
    else:
        from verify_c_mod import CFG, MENU, NETWORK, validate_files
        assert required <= changed <= required | {CFG, MENU, NETWORK}, changed
        validate_files(files, args.width, args.height)
    assert files[EXTRAS] == before[EXTRAS]
    donor = checked(HUD, HUD_HASH)
    assert files[PICKUP] == donor[PICKUP]
    assert controls(files[LAYOUT])["CItemPickupPanel"] == controls(donor[LAYOUT])["CItemPickupPanel"]
    validate(files)
    diff = []
    for name in sorted(changed | {FLYOUT}):
        diff.extend(difflib.unified_diff(
            before.get(name, b"").decode("utf-8-sig").splitlines(keepends=True),
            files[name].decode("utf-8-sig").splitlines(keepends=True),
            fromfile="before/" + name if name in before else "/dev/null", tofile="after/" + name,
        ))
    patch = ROOT / "reports/C_tumtara_merge.patch"
    patch.write_text("".join(diff), encoding="utf-8", newline="\n")
    assert patch.read_text(encoding="utf-8") == "".join(diff).replace("\r\n", "\n")
    print(f"PASS exact delta: {len(changed)} existing text resources changed + 1 launcher added; all other {len(before) - len(changed)} members byte-identical")
    print("PASS donor default speedometer/number positions restored, repaired speed materials unchanged")
    print("PATCH " + str(patch))
    print("RESULT SHA256 " + hashlib.sha256(target.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
