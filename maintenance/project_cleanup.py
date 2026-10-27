"""Plan project-only generated-file cleanup; apply requires the approved plan digest."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/project_cleanup"
PLAN = OUT / "plan.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked(path):
    absolute = path.resolve(strict=True)
    assert absolute != ROOT and absolute.is_relative_to(ROOT), str(absolute)
    assert not path.is_symlink() and not path.is_junction(), "Linked cleanup target: " + str(path)
    return absolute


def inventory(path):
    checked(path)
    if path.is_file():
        stat = path.stat()
        return [{"path": str(path.relative_to(ROOT)), "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}]
    rows = []
    for child in sorted(path.iterdir()):
        rows.extend(inventory(child))
    return rows


def tracked():
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    return {name.decode("utf-8").replace("\\", "/").casefold() for name in result.stdout.split(b"\0") if name}


def protected():
    keep = set()
    for relative in ("reports/c_current_review/verification.json", "reports/c_checkbox_bridge/verification.json"):
        record = ROOT / relative
        data = json.loads(record.read_text(encoding="utf-8"))
        for value in (*data.get("artifacts", {}), *data.get("baseline_inputs", {})):
            path = Path(value)
            path = path if path.is_absolute() else ROOT / path
            if path.is_file() and path.resolve().is_relative_to(ROOT):
                keep.add(path.resolve())
        keep.add(record.resolve())
    journal = ROOT / "reports/c_session_deploy/transaction.json"
    data = json.loads(journal.read_text(encoding="utf-8"))
    keep.add(journal.resolve())
    for entry in data["files"].values():
        backup = ROOT / entry["backup"]
        assert sha(backup) == entry["before_sha256"]
        keep.add(backup.resolve())
    # All pinned build inputs and committed source/research are preserved.
    return keep, data["generation"]


def make_plan():
    keep, generation = protected()
    committed = tracked()
    candidates = {}

    def add(path, reason):
        if not path.exists():
            return
        absolute = checked(path)
        rows = inventory(path)
        if any((ROOT / row["path"]).resolve() in keep or row["path"].replace("\\", "/").casefold() in committed
               for row in rows):
            return
        candidates[absolute] = {"path": str(absolute), "reason": reason, "files": rows,
                                "bytes": sum(row["bytes"] for row in rows), "directory": path.is_dir()}

    dist = ROOT / "dist"
    for path in dist.iterdir():
        if path.is_file():
            add(path, "旧版恢复副本或历史成品；受保护/已跟踪的当前成品自动排除")
        elif path.name == "history" or path.name.endswith("_test") or path.name.startswith("rollback_"):
            add(path, "历史试验包或重复回滚副本；最新审查引用的副本自动排除")
    for path in (dist / "c_session_helper").iterdir():
        if path.suffix.lower() in (".obj", ".lib", ".exp", ".pdb", ".ilk"):
            add(path, "可重新编译的中间文件；保留 DLL 和测试程序")
    for relative in ("reports/window_bootstrap", "reports/window_bootstrap_desktop"):
        folder = ROOT / relative
        if folder.exists():
            for path in folder.iterdir():
                add(path, "窗口回调测试临时目录；字面输出已保留在最新审查报告")
    old_reports = ("led_2x_test", "led_half_test", "led_glare_test", "led_mean190_test",
                   "flashlight_nofade_test", "flashlight_gain2x_test", "flashlight_gain_research")
    for name in old_reports:
        folder = ROOT / "reports" / name
        if folder.exists():
            for path in folder.rglob("*"):
                if path.is_file() and path.suffix.lower() in (".vpk", ".dll", ".zip", ".png", ".jpg", ".vcs", ".exe", ".obj"):
                    add(path, "历史手电试验的大体积生成文件；JSON/文本研究记录保留")
    transactions = ROOT / "reports/c_session_deploy/transactions"
    generations = sorted((path for path in transactions.iterdir() if path.is_dir()),
                         key=lambda path: path.stat().st_mtime_ns, reverse=True)
    retained = {path.name for path in generations[:3]} | {generation}
    for path in generations:
        if path.name not in retained:
            add(path, "超出最近三份的历史部署事务备份")
    # Cache traversal never enters Git, virtual environments or linked folders.
    for parent, dirs, files in os.walk(ROOT, followlinks=False):
        for name in list(dirs):
            path = Path(parent) / name
            if path.is_symlink() or path.is_junction() or name in (".git", ".venv", "venv"):
                dirs.remove(name)
            elif name in ("__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"):
                add(path, "解释器或测试工具缓存")
                dirs.remove(name)
    # Remove nested duplicates: an approved parent already covers its children.
    selected = []
    for path, entry in sorted(candidates.items(), key=lambda item: len(item[0].parts)):
        if not any(path.is_relative_to(Path(previous["path"])) for previous in selected):
            selected.append(entry)
    report = {"root": str(ROOT), "entries": sorted(selected, key=lambda item: item["path"]),
              "total_files": sum(len(item["files"]) for item in selected),
              "total_bytes": sum(item["bytes"] for item in selected),
              "retained_transaction_generations": sorted(retained),
              "protected_hashes": {str(path): sha(path) for path in sorted(keep)},
              "preserved": ["Git/source/docs/assets/research", "all originals build baselines", "current release and evidence",
                            "latest three deployment backups", "game directory (not touched)"]}
    OUT.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 待确认的项目清理清单", "", f"根目录：`{ROOT}`", "",
             f"共 {report['total_files']} 个文件，约 {report['total_bytes'] / 1024**3:.3f} GiB。", "",
             "保留源码、原始基线、最新成品/验证记录及最近三份部署备份；不碰游戏目录。", "",
             "| 绝对路径 | MiB | 原因 |", "|---|---:|---|"]
    for entry in report["entries"]:
        lines.append(f"| `{entry['path']}` | {entry['bytes'] / 1024**2:.2f} | {entry['reason']} |")
        print(f"{entry['bytes'] / 1024**2:9.2f} MiB  {entry['path']}")
    (OUT / "plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"TOTAL {report['total_files']} files, {report['total_bytes'] / 1024**3:.3f} GiB")
    print("PLAN", PLAN)
    print("APPROVAL_DIGEST", sha(PLAN))
    print("DRY RUN ONLY: no cleanup targets deleted")


def apply_plan(digest):
    assert sha(PLAN) == digest, "Approved plan changed"
    report = json.loads(PLAN.read_text(encoding="utf-8"))
    assert report["root"] == str(ROOT)
    current_tracked = tracked()
    for filename, expected in report["protected_hashes"].items():
        assert sha(Path(filename)) == expected, "Protected artifact changed"
    # Validate EVERY target before the first removal; refuse links and new files.
    for entry in report["entries"]:
        path = checked(Path(entry["path"]))
        assert inventory(path) == entry["files"], "Target changed since approval: " + str(path)
        assert all(row["path"].replace("\\", "/").casefold() not in current_tracked for row in entry["files"])
    deleted = []
    for entry in report["entries"]:
        path = checked(Path(entry["path"]))
        if entry["directory"]:
            shutil.rmtree(path)
        else:
            path.unlink()
        assert not path.exists()
        deleted.append(entry["path"])
    for filename, expected in report["protected_hashes"].items():
        assert sha(Path(filename)) == expected
    (OUT / "result.json").write_text(json.dumps({"approved_plan_sha256": digest, "deleted": deleted,
        "files": report["total_files"], "bytes": report["total_bytes"], "protected_hashes_verified": True},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("CLEANED", report["total_files"], "files; protected artifacts unchanged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "apply"))
    parser.add_argument("--approved-plan-sha256")
    args = parser.parse_args()
    if args.action == "plan":
        make_plan()
    else:
        assert args.approved_plan_sha256, "Explicit approved plan digest required"
        apply_plan(args.approved_plan_sha256)
