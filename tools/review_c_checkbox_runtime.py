"""Capture the latest real-game helper session without starting or controlling it."""

import argparse
from collections import Counter

from c_session_release import GAME, ROOT, TARGETS, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="reports/c_checkbox_bridge/runtime_latest.json")
    args = parser.parse_args()
    source = GAME / "CSessionDefaults.log"
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    starts = [index for index, line in enumerate(lines) if "WAIT_WINDOW:" in line]
    latest = lines[starts[-1]:] if starts else lines
    checkbox = [line for line in latest if "CHECKBOX_" in line]
    outcomes = Counter(line.split("] ", 1)[-1].split(":", 1)[0] for line in checkbox)
    report = {"scope": "Read-only real game log, latest session; not a new automated gameplay run",
              "source": str(source), "log_sha256": sha(source), "records": latest,
              "checkbox_records": checkbox, "outcomes": dict(outcomes),
              "installed_artifacts": {str(GAME / relative): sha(GAME / relative) for relative in TARGETS.values()}}
    target = ROOT / args.report
    assert target.resolve().is_relative_to((ROOT / "reports").resolve())
    if target.exists() and target.name == "runtime_before_deferred.json":
        print("KEEP immutable before-fix evidence", target)
        return
    save(target, report)
    print("LATEST_SESSION", dict(outcomes))
    print("RECORD", target)


if __name__ == "__main__":
    main()
