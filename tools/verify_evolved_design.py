"""Validate design-document consistency, not installer implementation/runtime."""

import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/L4D2Evolved_自动适配流程与EXE实现规范.md"
RULES = ROOT / "docs/evolved-adaptation-rules.v1.json"
STUDY = ROOT / "research/workshop_3785109042"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rules = json.loads(RULES.read_text(encoding="utf-8"))
    spec = SPEC.read_text(encoding="utf-8")
    package = json.loads((STUDY / "extraction_verification.json").read_text(encoding="utf-8"))
    assert rules["schema_version"] == 1
    assert rules["status"] == "design_reference_not_an_implemented_rule_engine"
    assert rules["profile"]["package_sha256"] == sha(STUDY / "3785109042.vpk") == package["sha256"]
    install = set(rules["install_files"])
    skip = {row["path"] for row in rules["skip_package_files"]}
    assert len(install) == len(rules["install_files"]) == 12
    assert len(skip) == len(rules["skip_package_files"]) == 3
    assert not install & skip
    assert install | skip == {row["path"] for row in package["members"]}
    assert not install & set(rules["protected_paths"])
    ids = [row["id"] for row in rules["rules"]]
    assert ids == [f"R{i:02d}" for i in range(1, 17)]
    assert all(f"| {rule} |" in spec for rule in ids)
    assert len(set(rules["states"])) == len(rules["states"])
    assert all(state in spec for state in rules["states"])
    sample = (STUDY / "unpacked/Evolved/config.sample").read_text(encoding="utf-8-sig")
    sample_keys = {line.strip().lstrip("#").split("=", 1)[0] for line in sample.splitlines() if "=" in line}
    assert all(row["key"] in sample_keys for row in rules["config_proposals"])
    assert not rules["profile"]["first_run_config_creation_validated"]
    assert rules["execution_defaults"]["dry_run"]
    assert rules["acceptance"]["static_success_does_not_imply_runtime_success"]
    for source in rules["profile"]["evidence"]:
        assert (ROOT / source).is_file(), source
    for target in re.findall(r"\]\(([^)]+)\)", spec):
        if "://" not in target and not target.startswith("#"):
            assert (SPEC.parent / target.split("#")[0]).resolve().is_file(), target
    cases = re.findall(r"\| (T\d{2}) \|", spec)
    assert cases == [f"T{i:02d}" for i in range(1, 22)]
    inputs = [SPEC, RULES, ROOT / "README.md", STUDY / "extraction_verification.json"]
    output = "PASS design consistency: 16 rules, 21 specified scenarios, 12 install candidates + 3 skips, 6 supported sample keys; local links valid"
    report = {"scope": "document/data consistency only; no installer or game runtime tests",
              "command": [sys.executable, "-X", "utf8", "tools/verify_evolved_design.py"],
              "cwd": str(ROOT), "exit_status": 0, "stdout": output + "\n", "stderr": "",
              "inputs": {str(p.relative_to(ROOT)): sha(p) for p in inputs},
              "package_sha256": rules["profile"]["package_sha256"],
              "game_write_operations": 0, "exe_implemented": False}
    target = ROOT / "reports/evolved_design_verification.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert json.loads(target.read_text(encoding="utf-8")) == report
    print(output)


if __name__ == "__main__":
    main()
