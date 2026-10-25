"""Recover the exact pre-filename-change artifact without changing current C."""

import hashlib
import shutil

from release_paths import ROOT, OUTPUT
from vpk import read


BASE = ROOT / "originals/C_before_fixed_filename.vpk"
BASE_HASH = "97fa1e054d0676042b9da149b421e645aad493160db98b7f04668a2503e463da"


def main():
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_HASH
    target = ROOT / "dist/rollback_before_fixed_filename/C_fullscreen_esc.vpk"
    assert target.resolve().is_relative_to(ROOT) and target.resolve() not in (BASE.resolve(), OUTPUT.resolve())
    if target.exists():
        assert hashlib.sha256(target.read_bytes()).hexdigest() == BASE_HASH
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BASE, target)
    assert target.read_bytes() == BASE.read_bytes() and len(read(target)) == 222
    print("RESTORED " + str(target))
    print("PASS original release name/content SHA256 " + BASE_HASH)
    print("PASS current named C and game files untouched")


if __name__ == "__main__":
    main()
