"""Deploy/restore only the LED candidate VPK; preserve the formal release pair."""

import argparse
import json
import shutil
import subprocess
import sys

import c_session_release as release
from led_texture_2x import DIRECTORY, REPORT, TEXTURES
from vpk import read

JOURNAL = REPORT / "deployment.json"
BACKUP = REPORT / "installed_before.vpk"
CANDIDATE = DIRECTORY / release.OUTPUT.name


def inputs():
    evidence = json.loads((REPORT / "verification.json").read_text(encoding="utf-8"))
    assert release.sha(CANDIDATE) == evidence["candidate_sha256"]
    baseline = DIRECTORY / "baseline.vpk.bak"
    assert release.sha(baseline) == evidence["baseline_sha256"]
    before, after = read(baseline), read(CANDIDATE)
    assert before.keys() == after.keys()
    assert {p for p in before if before[p] != after[p]} == set(TEXTURES)
    return evidence


def load():
    journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
    assert journal["game"] == str(release.GAME)
    assert journal["target"] == str(release.safe_target("vpk"))
    assert journal["backup"] == str(BACKUP)
    assert not BACKUP.is_symlink()
    assert release.sha(BACKUP) == journal["before_sha256"]
    assert release.sha(release.safe_target("helper")) == journal["helper_sha256"]
    return journal


def verify():
    journal = load()
    expected = journal["before_sha256"] if journal["status"] == "ROLLED_BACK" else journal["after_sha256"]
    assert release.sha(release.safe_target("vpk")) == expected
    print("PASS installed VPK hash verified; helper DLL unchanged; " + journal["status"])


def main():
    global DIRECTORY, REPORT, JOURNAL, BACKUP, CANDIDATE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("2x", "half", "glare", "mean190"), default="2x")
    parser.add_argument("action", choices=("inputs", "deploy", "verify", "rollback-preview", "rollback"))
    args = parser.parse_args()
    action = args.action
    if args.variant == "half":
        from led_half_test import DIRECTORY as half_directory, REPORT as half_report
        DIRECTORY, REPORT = half_directory, half_report
        JOURNAL, BACKUP = REPORT / "deployment.json", REPORT / "installed_before.vpk"
        CANDIDATE = DIRECTORY / release.OUTPUT.name
    elif args.variant == "glare":
        from led_glare_test import DIRECTORY as glare_directory, REPORT as glare_report
        DIRECTORY, REPORT = glare_directory, glare_report
        JOURNAL, BACKUP = REPORT / "deployment.json", REPORT / "installed_before.vpk"
        CANDIDATE = DIRECTORY / release.OUTPUT.name
    elif args.variant == "mean190":
        from led_mean190_test import DIRECTORY as mean_directory, REPORT as mean_report
        DIRECTORY, REPORT = mean_directory, mean_report
        JOURNAL, BACKUP = REPORT / "deployment.json", REPORT / "installed_before.vpk"
        CANDIDATE = DIRECTORY / release.OUTPUT.name
    if action == "inputs":
        inputs()
        print("PASS candidate CRC/hash and exact two-texture delta")
        return
    if action == "deploy":
        release.stopped()
        evidence = inputs()
        if JOURNAL.exists():
            journal = load()
            assert journal["after_sha256"] == evidence["candidate_sha256"]
            if journal["status"] == "DEPLOYED_RUNTIME_PENDING":
                verify()
                return
            assert journal["status"] in ("PREPARED", "ROLLED_BACK")
            assert release.sha(release.safe_target("vpk")) in (journal["before_sha256"], journal["after_sha256"])
        else:
            target = release.safe_target("vpk")
            if release.sha(target) == evidence["baseline_sha256"]:
                release.verify_installed()
            else:
                # Each experiment may follow only its recorded predecessor.
                # Trust only the exact previous journal/hashes, never arbitrary files.
                parents = {"half": "led_2x_test", "glare": "led_half_test", "mean190": "led_glare_test"}
                assert args.variant in parents
                parent_journal = release.ROOT / "reports" / parents[args.variant] / "deployment.json"
                previous = json.loads(parent_journal.read_text(encoding="utf-8"))
                assert previous["status"] == "DEPLOYED_RUNTIME_PENDING"
                assert previous["target"] == str(target) and previous["game"] == str(release.GAME)
                assert release.sha(target) == previous["after_sha256"]
                parent_evidence = json.loads((parent_journal.parent / "verification.json").read_text(encoding="utf-8"))
                assert parent_evidence["baseline_sha256"] == evidence["baseline_sha256"]
                assert release.sha(release.safe_target("helper")) == previous["helper_sha256"]
                print("PASS installed previous LED trial and unchanged helper match recorded hashes")
            assert not BACKUP.exists(), "Preserve existing backup before proceeding"
            shutil.copyfile(target, BACKUP)
            assert release.sha(BACKUP) == release.sha(target)
            journal = {"game": str(release.GAME), "target": str(target), "backup": str(BACKUP),
                       "before_sha256": release.sha(BACKUP), "after_sha256": release.sha(CANDIDATE),
                       "helper_sha256": release.sha(release.safe_target("helper")), "status": "PREPARED",
                       "rollback_command": "python -X utf8 tools/deploy_led_2x_test.py --variant " + args.variant + " rollback"}
        print("TARGET " + str(release.safe_target("vpk").resolve()))
        release.save(JOURNAL, journal)
        release.copy_verified(CANDIDATE, release.safe_target("vpk"), journal["after_sha256"])
        journal["status"] = "DEPLOYED_RUNTIME_PENDING"
        release.save(JOURNAL, journal)
        verify()
        return
    if action == "verify":
        verify()
        return
    journal = load()
    assert journal["status"] in ("PREPARED", "DEPLOYED_RUNTIME_PENDING", "ROLLED_BACK")
    target = release.safe_target("vpk")
    assert release.sha(target) in (journal["before_sha256"], journal["after_sha256"])
    print("RESTORE " + str(target.resolve()) + " FROM " + str(BACKUP.resolve()))
    if action == "rollback-preview":
        print("PASS backup/hash preflight; no game files changed")
        return
    release.stopped()
    release.copy_verified(BACKUP, target, journal["before_sha256"])
    journal["status"] = "ROLLED_BACK"
    release.save(JOURNAL, journal)
    verify()
    # Nested trials restore the preceding trial, not necessarily the formal C.
    if journal["before_sha256"] == release.sha(release.OUTPUT):
        release.verify_installed()


if __name__ == "__main__":
    main()
