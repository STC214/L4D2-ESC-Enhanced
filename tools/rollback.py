"""Restore a byte-exact original B VPK inside the project (no game changes)."""

import argparse
import hashlib
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "dc6efecc83d1de19483ff46fbc964f1549d59852eb156599b21bc72d48f6108e"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist/B_original_restored.vpk")
    args = parser.parse_args()
    source = ROOT / "originals/B_2906960647.vpk"
    target = args.output.resolve()
    assert target.is_relative_to(ROOT) and target != source.resolve()
    assert target.suffix.lower() == ".vpk"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == EXPECTED
    if target.exists():
        assert hashlib.sha256(target.read_bytes()).hexdigest() == EXPECTED, "Keep existing non-original output"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    assert target.read_bytes() == source.read_bytes()
    print("RESTORED " + str(target))
    print("PASS byte-exact original B SHA256 " + EXPECTED)
    print("Game installation and saved cvars were not touched.")


if __name__ == "__main__":
    main()
