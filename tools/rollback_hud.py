"""Restore C immediately before the HUD integration; no game installation edits."""

import hashlib
import shutil

from hud_integration import PRE_HUD, PRE_HUD_HASH, ROOT
from vpk import read


def main():
    assert hashlib.sha256(PRE_HUD.read_bytes()).hexdigest() == PRE_HUD_HASH
    target = ROOT / "dist/C_before_hud_restored.vpk"
    assert target.resolve().is_relative_to(ROOT) and target.resolve() != PRE_HUD.resolve()
    if target.exists():
        assert hashlib.sha256(target.read_bytes()).hexdigest() == PRE_HUD_HASH
    target.parent.mkdir(exist_ok=True)
    shutil.copyfile(PRE_HUD, target)
    assert target.read_bytes() == PRE_HUD.read_bytes()
    assert len(read(target)) == 76
    print("RESTORED " + str(target))
    print("PASS exact pre-HUD C SHA256 " + PRE_HUD_HASH)
    print("Game installation and persisted player cvars were not touched.")


if __name__ == "__main__":
    main()
