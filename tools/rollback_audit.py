"""Restore the exact C delivered before the full-audit repair cycle."""

import hashlib
import shutil
from pathlib import Path

from vpk import read


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "originals/C_before_full_audit.vpk"
EXPECTED = "75cf4ab83a8656587799555f1678b210c6300f586a1d243cd08e2d76b06256c3"


def main():
    if hashlib.sha256(BASE.read_bytes()).hexdigest() != EXPECTED:
        raise ValueError("Audit baseline hash mismatch")
    target = ROOT / "dist/C_before_audit_restored.vpk"
    if not target.resolve().is_relative_to(ROOT) or target.resolve() == BASE.resolve():
        raise ValueError("Invalid rollback path")
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != EXPECTED:
        raise ValueError("Keep existing unrelated output")
    target.parent.mkdir(exist_ok=True)
    shutil.copyfile(BASE, target)
    if target.read_bytes() != BASE.read_bytes() or len(read(target)) != 221:
        raise ValueError("Rollback verification failed")
    print("RESTORED " + str(target))
    print("PASS exact pre-audit C SHA256 " + EXPECTED)
    print("Game installation and personal configuration unchanged.")


if __name__ == "__main__":
    main()
