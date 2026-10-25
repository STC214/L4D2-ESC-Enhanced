"""Rebuild and run two complete clean static/regression review rounds.

Any failure stops the cycle for investigation, rather than masking it or
claiming in-game verification. Exact command outputs remain in the record.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from release_paths import OUTPUT


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "reports/full_review_verification.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, expected=0):
    command = [sys.executable, "-X", "utf8", *args]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    entry = {"cwd": str(ROOT), "command": command, "stdout": result.stdout,
             "stderr": result.stderr, "exit_status": result.returncode, "expected_exit_status": expected}
    print(f"exit={result.returncode} expected={expected} " + subprocess.list2cmdline(command))
    if result.returncode != expected:
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError("Review command failed")
    return entry


def main():
    report = {
        "scope": "Full packaged-member static audit + regression/negative tests; NOT in-game validation",
        "baseline": {"path": "originals/C_before_full_audit.vpk", "sha256": sha(ROOT / "originals/C_before_full_audit.vpk")},
        "task_baseline": {"path": "originals/C_before_session_defaults.vpk", "sha256": sha(ROOT / "originals/C_before_session_defaults.vpk")},
        "merge_baseline": {"path": "originals/C_before_tumtara_merge.vpk", "sha256": sha(ROOT / "originals/C_before_tumtara_merge.vpk")},
        "source_hashes": {str(path.relative_to(ROOT)): sha(path) for path in sorted((ROOT / "tools").glob("*.py"))},
        "native_source_hashes": {str(path.relative_to(ROOT)): sha(path) for path in sorted((ROOT / "native/c_session_defaults").glob("*")) if path.is_file()},
        "rounds": [], "clean_rounds": 0,
    }
    report["baseline_audit"] = run([
        "tools/audit_c.py", "originals/C_before_full_audit.vpk",
        "--report", "reports/full_audit_baseline.json",
    ], expected=1)
    try:
        report["filename_baseline"] = run(["tools/verify_release_name.py", "--baseline"])
        for number in (1, 2):
            records = [
                run(["tools/c_session_release.py", "baseline"]),
                run(["tools/build_c_session_plugin.py"]),
                run(["tools/build_c_mod.py", "--width", "1280", "--height", "720"]),
                run(["tools/c_session_release.py", "package"]),
                run(["tools/c_session_release.py", "rollback-copy"]),
                run(["tools/review_c_session_deployment.py"]),
                run(["tools/test_c_session_deploy.py", "--report", f"reports/c_session_audit/deploy_clean_{number}.json"]),
                run(["tools/package_c_session_audit.py"]),
                run(["tools/verify_evolved_design.py"]),
                run(["tools/verify_evolved_minimap.py", "--tests"]),
                run(["tools/audit_c.py", "--report", f"reports/full_audit_clean_{number}.json"]),
                run(["tools/test_c.py"]),
                run(["tools/verify_c_mod.py", str(OUTPUT.relative_to(ROOT)), "--width", "1280", "--height", "720"]),
                run(["tools/build_c_mod.py", "--apply-patch"]),
                run(["tools/rollback_audit.py"]),
                run(["tools/verify_tumtara_merge.py"]),
                run(["tools/rollback_tumtara.py"]),
                run(["tools/verify_release_name.py"]),
                run(["tools/rollback_release_name.py"]),
            ]
            audit = json.loads((ROOT / f"reports/full_audit_clean_{number}.json").read_text(encoding="utf-8"))
            if audit["errors"] or audit["sha256"] != sha(OUTPUT):
                raise RuntimeError("Audit artifact identity mismatch")
            report["rounds"].append({"round": number, "sha256": sha(OUTPUT), "helper_sha256": sha(ROOT / "dist/c_session_helper/CSessionDefaults.dll"), "errors": 0, "records": records})
            report["clean_rounds"] += 1
            print(f"CLEAN FULL ROUND {number}/2 sha256={sha(OUTPUT)}")
        if len({r["sha256"] for r in report["rounds"]}) != 1:
            raise RuntimeError("Rebuild is not deterministic")
        if len({r["helper_sha256"] for r in report["rounds"]}) != 1:
            raise RuntimeError("Helper rebuild is not deterministic")
        current_sources = {str(path.relative_to(ROOT)): sha(path) for path in sorted((ROOT / "tools").glob("*.py"))}
        if current_sources != report["source_hashes"]:
            raise RuntimeError("Review source changed during clean rounds")
        native_sources = {str(path.relative_to(ROOT)): sha(path) for path in sorted((ROOT / "native/c_session_defaults").glob("*")) if path.is_file()}
        if native_sources != report["native_source_hashes"]:
            raise RuntimeError("Native source changed during clean rounds")
        artifacts = (OUTPUT, ROOT / "reports/C_update_patch.zip", ROOT / "reports/C_update.patch",
                     ROOT / "reports/C_tumtara_merge.patch", ROOT / "reports/C_verification.json",
                     ROOT / "tools/rollback_release_name.py",
                     ROOT / "dist/rollback_before_fixed_filename/C_fullscreen_esc.vpk",
                     ROOT / "dist/C_session_release.zip", ROOT / "dist/c_session_helper/CSessionDefaults.dll",
                     ROOT / "reports/c_session_plugin_build.json", ROOT / "tools/c_session_release.py",
                     ROOT / "reports/c_session_audit/fix_bundle.zip", ROOT / "reports/c_session_audit/fixes.patch",
                     ROOT / "reports/c_session_audit/patch_verification.json")
        report["artifacts"] = {str(path.relative_to(ROOT)): sha(path) for path in artifacts}
        report["status"] = "two clean complete static/regression review rounds"
        report["remaining_checks"] = [
            f"{len(audit['external_game_resource_references'])} resource references depend on base game files not present in this project",
            "L4D2 loading/rendering and live speed/health refresh",
            "L4N launch-thread timer delivery, actual room transitions and online cvar acceptance",
            "TUMTaRA engine popup placement/clicks; Workshop 469986973 maps and optional map packs remain separate",
        ]
    except Exception as exc:
        report["status"] = "failed"
        report["failure"] = str(exc)
        raise
    finally:
        RECORD.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        saved = json.loads(RECORD.read_text(encoding="utf-8"))
        if saved != report:
            raise RuntimeError("Review record re-open mismatch")
    print("PASS two complete clean rounds; deterministic VPK; patch replay and rollback verified")
    print("RECORD " + str(RECORD))


if __name__ == "__main__":
    main()
