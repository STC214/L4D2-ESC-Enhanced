"""Restore pre-merge C into dist; never touch game files or current C."""

import hashlib
import shutil

from tumtara_integration import BEFORE, BEFORE_HASH, ROOT, checked
from vpk import read


def main():
    checked(BEFORE, BEFORE_HASH)
    target = ROOT / "dist/C_before_tumtara_restored.vpk"
    assert target.resolve().is_relative_to(ROOT) and target.resolve() != BEFORE.resolve()
    if target.exists():
        assert hashlib.sha256(target.read_bytes()).hexdigest() == BEFORE_HASH
    target.parent.mkdir(exist_ok=True)
    shutil.copyfile(BEFORE, target)
    assert target.read_bytes() == BEFORE.read_bytes() and len(read(target)) == 221
    print("RESTORED " + str(target))
    print("PASS exact pre-merge C SHA256 " + BEFORE_HASH)
    print("PASS pre-merge main menu and top-left speed layout restored; current C/game files untouched")


if __name__ == "__main__":
    main()
