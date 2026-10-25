"""Restore the preserved pre-update C; no game-folder or config edits."""

import hashlib
import shutil
from pathlib import Path

from verify_c_mod import BASE, BASE_HASH, ROOT
from vpk import read


def main():
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_HASH
    target = ROOT / "dist/C_before_update_restored.vpk"
    assert target.resolve().is_relative_to(ROOT) and target.resolve() != BASE.resolve()
    if target.exists():
        assert hashlib.sha256(target.read_bytes()).hexdigest() == BASE_HASH
    target.parent.mkdir(exist_ok=True)
    shutil.copyfile(BASE, target)
    assert target.read_bytes() == BASE.read_bytes()
    assert len(read(target)) == 74
    print("RESTORED " + str(target))
    print("PASS exact pre-update C SHA256 " + BASE_HASH)
    print("Game files and persisted player cvars were not touched.")


if __name__ == "__main__":
    main()
