"""Record literal integrated-deployment commands, hashes and rollback preflight."""

import argparse
import subprocess
import sys

import c_session_release as r
import deploy_c_integrated as integration

RECORD = integration.WORK / "verification.json"


def snapshot():
    return {str(path): r.snapshot(path) for path in integration.targets().values()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deploy", action="store_true", help="Install before verification; game must be stopped")
    args = parser.parse_args()
    report = {"scope": "File deployment and rollback preflight; NOT live game rendering",
              "inputs": {str(p): r.sha(p) for p in r.SOURCES.values()},
              "game_before": snapshot(), "records": [], "status": "STARTED"}
    try:
        actions = (["deploy"] if args.deploy else []) + ["verify", "rollback-preview"]
        for action in actions:
            command = [sys.executable, "-X", "utf8", "tools/deploy_c_integrated.py", action]
            result = subprocess.run(command, cwd=r.ROOT, capture_output=True, text=True, encoding="utf-8")
            report["records"].append({"cwd": str(r.ROOT), "command": command,
                                      "stdout": result.stdout, "stderr": result.stderr,
                                      "exit_status": result.returncode})
            print(f"exit={result.returncode} " + subprocess.list2cmdline(command), flush=True)
            print(result.stdout, end="", flush=True)
            if result.returncode:
                raise RuntimeError(result.stderr or "Deployment verification failed")
        report["game_after"] = snapshot()
        report["transaction"] = str(integration.JOURNAL)
        report["status"] = "FILES_VERIFIED_RUNTIME_PENDING"
    except BaseException as exc:
        report["status"] = "FAILED"
        report["error"] = str(exc)
        raise
    finally:
        r.save(RECORD, report)
    print("RECORD " + str(RECORD))


if __name__ == "__main__":
    main()
