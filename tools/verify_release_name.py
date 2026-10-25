"""Verify permanent filename and unchanged bytes for this naming-only release."""

import argparse
import hashlib

from release_paths import ROOT, OUTPUT, C_FILENAME
from rollback_release_name import BASE, BASE_HASH
from vpk import read


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_HASH
    baseline = read(BASE)
    assert len(baseline) == 222
    print("PASS baseline preserved: " + str(BASE))
    print("BASE SHA256 " + BASE_HASH)
    if args.baseline:
        return
    assert C_FILENAME == "【00】C_ESC_LED_血条和速度_TUMTaRA.vpk"
    assert OUTPUT.parent == ROOT / "dist" and OUTPUT.name == C_FILENAME
    assert OUTPUT.read_bytes() == BASE.read_bytes()
    assert read(OUTPUT) == baseline
    print("PASS permanent release path: " + str(OUTPUT))
    print("PASS 222 members and archive bytes unchanged; no gameplay resource edits")
    print("RESULT SHA256 " + hashlib.sha256(OUTPUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
