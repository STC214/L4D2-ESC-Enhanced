"""Hash-guarded independent no-fade VPK installation; never replace base shaders."""

import argparse
import json
import shutil

import c_session_release as release
from build_flashlight_nofade_test import OUT, REPORT, RELATIVE, SOURCE_HASH
from vpk import read

SOURCE = OUT / "C_flashlight_nofade_TEST.vpk"
TARGET = release.GAME / "left4dead2/addons" / SOURCE.name
JOURNAL = REPORT / "deployment.json"
BACKUP = REPORT / "previous_test.vpk.bak"


def preflight():
    assert TARGET.resolve().is_relative_to(release.GAME.resolve()) and not TARGET.is_symlink()
    assert TARGET.parent.is_dir()
    report = json.loads((REPORT / "independent_verification.json").read_text(encoding="utf-8"))
    assert report["checked_blobs"] == report["D3DDisassemble_success_count"] == 2832
    payload = read(SOURCE)
    assert set(payload) == {"addoninfo.txt", RELATIVE}
    import hashlib
    assert hashlib.sha256(payload[RELATIVE]).hexdigest() == report["modified_sha256"]
    assert release.sha(release.GAME / "hl2" / RELATIVE) == SOURCE_HASH
    assert not (release.GAME / "left4dead2" / RELATIVE).exists(), "Existing loose override needs review first"
    return release.sha(SOURCE)


def load():
    data = json.loads(JOURNAL.read_text(encoding="utf-8"))
    assert data["target"] == str(TARGET) and data["backup"] == str(BACKUP)
    assert data["disabled"] == str(TARGET.with_suffix(".vpk.disabled"))
    return data


def verify():
    expected = preflight()
    record = load()
    assert record["after_sha256"] == expected
    if record["status"] == "ROLLED_BACK" and record["before_sha256"] is None:
        assert not TARGET.exists()
    else:
        assert release.sha(TARGET) == (record["before_sha256"] if record["status"] == "ROLLED_BACK" else expected)
    print("PASS independent shader-test installation hash; original hl2 shader unchanged; " + record["status"])


def main():
    global OUT, REPORT, SOURCE, TARGET, JOURNAL, BACKUP
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("nofade", "gain2x"), default="nofade")
    parser.add_argument("action", choices=("preflight", "deploy", "verify", "rollback-preview", "rollback"))
    args = parser.parse_args()
    action = args.action
    if args.variant == "gain2x":
        from build_flashlight_gain_test import OUT as gain_out, REPORT as gain_report
        OUT, REPORT = gain_out, gain_report
        SOURCE = OUT / "C_flashlight_nofade_TEST.vpk"
        TARGET = release.GAME / "left4dead2/addons" / SOURCE.name
        JOURNAL, BACKUP = REPORT / "deployment.json", REPORT / "previous_test.vpk.bak"
    digest = preflight()
    if action == "preflight":
        print("PASS VPK inventory, 2832 validated shader blobs, original shader hash, no loose override")
        return
    if action == "verify":
        verify()
        return
    if action == "deploy":
        release.stopped()
        if JOURNAL.exists():
            record = load()
            assert record["after_sha256"] == digest
            if record["status"] == "DEPLOYED_RUNTIME_PENDING":
                verify()
                return
            assert record["status"] in ("PREPARED", "ROLLED_BACK")
            assert release.snapshot(TARGET) in (record["before_sha256"], digest)
        else:
            before = release.snapshot(TARGET)
            if before is not None and before != digest:
                assert args.variant == "gain2x", "Unknown existing test package; do not overwrite"
                previous = json.loads((release.ROOT / "reports/flashlight_nofade_test/deployment.json").read_text(encoding="utf-8"))
                evidence = json.loads((REPORT / "independent_verification.json").read_text(encoding="utf-8"))
                assert previous["target"] == str(TARGET) and previous["status"] == "DEPLOYED_RUNTIME_PENDING"
                assert previous["after_sha256"] == before == evidence["baseline_test_vpk_sha256"]
            assert not BACKUP.exists()
            if before:
                shutil.copyfile(TARGET, BACKUP)
                assert release.sha(BACKUP) == before
            record = {"target": str(TARGET), "backup": str(BACKUP),
                      "disabled": str(TARGET.with_suffix(".vpk.disabled")), "before_sha256": before,
                      "after_sha256": digest, "status": "PREPARED",
                      "variant": args.variant,
                      "rollback_command": "python -X utf8 tools/deploy_flashlight_nofade_test.py --variant " + args.variant + " rollback"}
        c_before = {key: release.sha(release.safe_target(key)) for key in ("vpk", "helper")}
        record["C_pair_before"] = c_before
        release.save(JOURNAL, record)
        print("TARGET", TARGET.resolve())
        release.copy_verified(SOURCE, TARGET, digest)
        assert {key: release.sha(release.safe_target(key)) for key in c_before} == c_before
        record["status"] = "DEPLOYED_RUNTIME_PENDING"
        release.save(JOURNAL, record)
        verify()
        print("PASS C VPK and helper DLL untouched by shader-test deployment")
        return
    record = load()
    assert release.snapshot(TARGET) in (record["before_sha256"], record["after_sha256"])
    if record["before_sha256"]:
        assert release.sha(BACKUP) == record["before_sha256"]
        print("RESTORE", TARGET.resolve(), "FROM", BACKUP.resolve())
    else:
        disabled = TARGET.with_suffix(".vpk.disabled")
        if TARGET.exists():
            assert not disabled.exists()
        print("DISABLE BY RENAME", TARGET.resolve(), "TO", disabled.resolve())
    if action == "rollback-preview":
        print("PASS rollback preflight; no game changes")
        return
    release.stopped()
    if record["before_sha256"]:
        release.copy_verified(BACKUP, TARGET, record["before_sha256"])
    elif TARGET.exists():
        TARGET.rename(TARGET.with_suffix(".vpk.disabled"))
        assert not TARGET.exists()
    record["status"] = "ROLLED_BACK"
    release.save(JOURNAL, record)
    verify()


if __name__ == "__main__":
    main()
