"""Two clean current-release audit rounds with literal subprocess evidence."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from c_menu_consolidation import BASE, OLD_DLL, DLL, PATCH, DIFF, BUNDLE
from c_chat_layout import BASE as CHAT_BASE
from release_paths import ROOT, OUTPUT, C_FILENAME

RECORD = ROOT / "reports/c_current_review/verification.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    paths = list((ROOT / "tools").glob("*.py")) + list((ROOT / "native/c_session_defaults").glob("*"))
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths) if p.is_file()}


def game_snapshot():
    game = Path(r"E:\SteamLibrary\steamapps\common\Left 4 Dead 2")
    paths = (game / "left4dead2/addons" / C_FILENAME, game / "bin/neko/plugins/CSessionDefaults.dll")
    return {str(p): sha(p) if p.exists() else None for p in paths}


def run(arguments):
    command = [sys.executable, "-X", "utf8", *arguments]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    print(f"exit={result.returncode} " + subprocess.list2cmdline(command), flush=True)
    return {"cwd": str(ROOT), "command": command, "stdout": result.stdout,
            "stderr": result.stderr, "exit_status": result.returncode}


def main():
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    report = {"scope": "Complete packaged-member static audit, native unit/real DLL ABI test, regression and file-transaction fixtures; NOT live L4D2",
              "baseline_inputs": {str(p.relative_to(ROOT)): sha(p) for p in (BASE, OLD_DLL, CHAT_BASE)},
              "source_hashes": sources(), "game_before": game_snapshot(),
              "baseline_records": [], "rounds": [], "clean_rounds": 0}
    try:
        for command in (["tools/c_menu_consolidation.py", "baseline"],
                        ["tools/c_chat_layout.py", "baseline"],
                        ["tools/audit_c.py", str(CHAT_BASE), "--report", "reports/c_chat_bottom_right/baseline_audit.json"]):
            entry = run(command)
            report["baseline_records"].append(entry)
            assert entry["exit_status"] == 0, entry
        for number in (1, 2):
            round_ = {"round": number, "records": []}
            report["rounds"].append(round_)
            commands = [
                ["tools/build_c_session_plugin.py"],
                ["tools/build_c_mod.py", "--width", "1280", "--height", "720"],
                ["tools/verify_fov165.py"],
                ["tools/c_chat_layout.py", "verify"],
                ["tools/test_c.py"],
                ["tools/test_c_session_deploy.py", "--report", f"reports/c_chat_bottom_right/deploy_{number}.json"],
                ["tools/audit_c.py", str(OUTPUT), "--report", f"reports/c_chat_bottom_right/audit_{number}.json"],
                ["tools/verify_c_mod.py", str(OUTPUT)],
                ["tools/verify_hud_integration.py", str(OUTPUT)],
                ["tools/verify_tumtara_merge.py"],
                ["tools/verify_release_name.py"],
                ["tools/c_session_release.py", "package"],
                ["tools/build_c_mod.py", "--apply-patch"],
                ["tools/c_menu_consolidation.py", "rollback-copy"],
                ["tools/c_chat_layout.py", "rollback-copy"],
            ]
            for command in commands:
                entry = run(command)
                round_["records"].append(entry)
                if entry["exit_status"]:
                    print(entry["stdout"] + entry["stderr"])
                    raise RuntimeError("Audit failed; see exact record")
            audit = json.loads((ROOT / f"reports/c_chat_bottom_right/audit_{number}.json").read_text(encoding="utf-8"))
            assert not audit["errors"] and audit["sha256"] == sha(OUTPUT)
            round_.update(vpk_sha256=sha(OUTPUT), helper_sha256=sha(DLL), bundle_sha256=sha(BUNDLE), errors=0)
            report["clean_rounds"] += 1
            print(f"CLEAN FULL ROUND {number}/2", flush=True)
        for field in ("vpk_sha256", "helper_sha256", "bundle_sha256"):
            assert len({r[field] for r in report["rounds"]}) == 1, field
        assert sources() == report["source_hashes"], "Sources changed during clean rounds"
        report["game_after"] = game_snapshot()
        assert report["game_after"] == report["game_before"], "Unexpected live-game file change"
        restored = ROOT / "dist/rollback_menu_consolidation"
        artifacts = (OUTPUT, DLL, BUNDLE, PATCH, DIFF, BASE, OLD_DLL,
                     ROOT / "reports/c_menu_consolidation/replayed.vpk",
                     restored / C_FILENAME, restored / "CSessionDefaults.dll", CHAT_BASE,
                     ROOT / "reports/c_chat_bottom_right/chat.patch",
                     ROOT / "dist/rollback_chat_bottom_right" / C_FILENAME)
        report["artifacts"] = {str(p.relative_to(ROOT)): sha(p) for p in artifacts}
        diff = subprocess.run(["git", "diff", "--", "native/c_session_defaults", "tools", "README.md", "C_README.md", "C_SESSION_DEFAULTS.md"],
                              cwd=ROOT, capture_output=True, check=True)
        (RECORD.parent / "tracked_source_changes.patch").write_bytes(diff.stdout)
        report["status"] = "TWO_CLEAN_STATIC_REGRESSION_ROUNDS"
        report["runtime_pending"] = [
            "L4N game-window message pump and D3D bootstrap in the real game",
            "Map entry/reload initializes FOV 165; manual values persist without ESC-triggered reset",
            "Actual server acceptance of weather/light CVars and real UI text/rendering",
            "Chat history/input real engine layout and HUD clearance; default Evo-map separation in-game",
        ]
    except BaseException as exc:
        report["status"] = "FAILED"
        report["error"] = str(exc)
        raise
    finally:
        RECORD.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        assert json.loads(RECORD.read_text(encoding="utf-8")) == report
    print("PASS two clean rounds; deterministic VPK/DLL/install bundle; patch and rollback reopened")
    print("RECORD " + str(RECORD))


if __name__ == "__main__":
    main()
