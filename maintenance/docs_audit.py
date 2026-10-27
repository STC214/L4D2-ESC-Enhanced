"""Read/snapshot, propose apply_patch-only documentation moves, and check local links."""

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import subprocess
import zipfile
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/docs_archive"
ROOT_ARCHIVES = ("ANALYSIS.md", "C_CHAT_BOTTOM_RIGHT.md", "C_HUD_INTEGRATION.md",
    "C_MENU_CONSOLIDATION.md", "C_README.md", "C_SESSION_AUDIT.md", "C_SESSION_DEFAULTS.md",
    "C_TUMTARA_INTEGRATION.md", "FULL_AUDIT_REPORT.md", "TUMTARA_CONFLICT.md")
MOVES = {name: "docs/archive/" + name for name in ROOT_ARCHIVES}
MOVES["README.md"] = "docs/archive/README_B_TO_C_HISTORY.md"
for name in ("C开关修复与排列.md", "FLASHLIGHT_GAIN2X_TEST.md", "FLASHLIGHT_NOFADE_TEST.md"):
    MOVES["docs/" + name] = "docs/archive/" + name
for name in ("使用方法与研究记录.md", "本机游戏适配方案.md", "部署结果与地图导航入口.md"):
    MOVES["research/workshop_3785109042/" + name] = "docs/archive/evolved/" + name
LINK = re.compile(r"(!?\[[^\]\n]*\]\()([^\s)]+)(\))")


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def documents():
    paths = set(ROOT.glob("*.md")) | set((ROOT / "docs").rglob("*.md"))
    paths |= set((ROOT / "research").glob("*/*.md"))
    return sorted(path for path in paths if path.is_file())


def snapshot():
    REPORT.mkdir(parents=True, exist_ok=True)
    output = REPORT / "before.json"
    assert not output.exists(), "Keep original snapshot; do not overwrite it"
    data = {path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8-sig") for path in documents()}
    output.write_text(json.dumps({"root": str(ROOT), "documents": data,
        "hashes": {name: digest(body) for name, body in data.items()}}, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, body in data.items():
        headings = re.findall(r"^#{1,3} .+", body, re.M)
        print(name, len(body), "chars;", " / ".join(headings[:5]))
    print("SNAPSHOT", output)


def rebase(body, source, destination):
    mapping = {key: value for key, value in MOVES.items() if key != "README.md"}
    def replace(match):
        value = match[2]
        url = urlsplit(value)
        if url.scheme or value.startswith(("#", "//")):
            return match[0]
        target = (ROOT / source).parent / unquote(url.path)
        target = target.resolve()
        if not target.is_relative_to(ROOT):
            return match[0]
        relative = target.relative_to(ROOT).as_posix()
        renamed = ROOT / mapping.get(relative, relative)
        href = Path(os.path.relpath(renamed, (ROOT / destination).parent)).as_posix()
        if url.query:
            href += "?" + url.query
        if url.fragment:
            href += "#" + url.fragment
        return match[1] + href + match[3]
    return LINK.sub(replace, body)


def migrated(body, source, destination):
    body = rebase(body, source, destination)
    current = Path(os.path.relpath(ROOT / "docs/C使用说明.md", (ROOT / destination).parent)).as_posix()
    index = Path(os.path.relpath(ROOT / "docs/INDEX.md", (ROOT / destination).parent)).as_posix()
    note = (f"\n> **历史归档，不是当前安装教程。** 原路径：`{source}`。文中的“当前/最新/本轮”均指当时阶段；"
            f"旧默认值、布局、哈希和回退命令不代表 C 1.3.1。当前使用见 [C 使用说明]({current})，"
            f"完整分类见 [文档索引]({index})。代码块与反引号中的项目路径仍按项目根目录解释；"
            "部分历史试验包/恢复副本已清理，原始输入与核心审查证据保留。\n")
    if source.startswith("research/"):
        note += "\n> 原研究数据目录仍为 `research/workshop_3785109042/`，下文未带目录的证据文件名与 `unpacked/` 均指该原目录；文档归档没有重新部署 Evolved。\n"
    first, separator, rest = body.partition("\n")
    return first + separator + note + "\n" + rest


def proposed():
    data = json.loads((REPORT / "before.json").read_text(encoding="utf-8"))["documents"]
    parts = ["*** Begin Patch\n"]
    for source, body in data.items():
        destination = MOVES.get(source, source)
        after = migrated(body, source, destination) if source in MOVES else rebase(body, source, destination)
        if after == body:
            continue
        assert (ROOT / source).read_text(encoding="utf-8-sig") == body, "Original changed: " + source
        if source != destination:
            assert not (ROOT / destination).exists(), "Archive collision: " + destination
        parts.append("*** Update File: " + source + "\n")
        if source != destination:
            parts.append("*** Move to: " + destination + "\n")
        diff = list(difflib.unified_diff(body.splitlines(True), after.splitlines(True), n=3))
        parts.extend("@@\n" if line.startswith("@@") else line for line in diff[2:])
        if not parts[-1].endswith("\n"):
            parts.append("\n")
    parts.append("*** End Patch\n")
    print(json.dumps({"patch": "".join(parts)}, ensure_ascii=False))


def verify_moves():
    data = json.loads((REPORT / "before.json").read_text(encoding="utf-8"))["documents"]
    for source, destination in MOVES.items():
        if source != "README.md":
            assert not (ROOT / source).exists(), source
        elif (ROOT / source).exists():
            assert (ROOT / source).read_text(encoding="utf-8-sig") != data[source], "New README was not separated from history"
        assert (ROOT / destination).read_text(encoding="utf-8-sig") == migrated(data[source], source, destination), destination
    print("PASS", len(MOVES), "single-file moves; archived bodies retained with only banners/link rebasing")


def check():
    errors, links = [], 0
    for path in documents():
        relative = path.relative_to(ROOT).as_posix()
        if not relative.startswith("docs/") and relative not in ("README.md", "AGENTS.md"):
            errors.append("Business document outside docs: " + relative)
        body = path.read_text(encoding="utf-8-sig")
        if relative.startswith("docs/archive/") and "历史归档" not in body:
            errors.append("Missing archive notice: " + relative)
        if body.count("```") % 2:
            errors.append("Unbalanced code fence: " + relative)
        for match in LINK.finditer(body):
            url = urlsplit(match[2])
            if url.scheme or match[2].startswith(("#", "//")):
                continue
            target = (path.parent / unquote(url.path)).resolve()
            links += 1
            if not target.is_relative_to(ROOT) or not target.exists():
                errors.append(relative + " -> " + match[2])
    result = {"scope": "Managed Markdown placement, archive labels, local file links and code fences; external URLs not fetched",
              "documents": len(documents()), "local_links": links, "errors": errors}
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert not errors


def facts():
    # Compare documentation's key constants with actual packaged resources;
    # this is a read-only documentation check, not a fresh game-runtime audit.
    sys.path.insert(0, str(ROOT / "tools"))
    from vpk import read
    from c_binary_switches import CONTROL, SWITCHES
    from inspect_menu import blocks, fields
    from release_paths import OUTPUT, C_FILENAME
    files = read(OUTPUT)
    cfg = files["cfg/l4d2esc_defaults.cfg"].decode("utf-8-sig")
    settings = {}
    for line in cfg.splitlines():
        values = line.strip().split()
        if len(values) == 2 and not line.lstrip().startswith("//"):
            settings[values[0].lower()] = values[1]
    expected = {"r_rainparticledensity": "0", "r_snowparticles": "0", "fog_override": "0", "fog_enable": "0",
                "cl_ragdoll_maxcount": "0", "sv_disable_glow_survivors": "0", "sv_disable_glow_faritems": "0",
                "r_flashlightconstant": "1", "r_flashlightfar": "3000", "r_flashlightfov": "165",
                "net_graphheight": "620", "net_graphpos": "1"}
    assert all(settings.get(name) == value for name, value in expected.items())
    nodes = [fields(block) for _, _, _, block in blocks(files["resource/ui/l4d360ui/ingamemainmenu.res"].decode("utf-8-sig"))]
    switches = [item for item in nodes if item.get("controlname") == CONTROL]
    assert len(switches) == 10 and {item["cvar_name"].lower() for item in switches} == set(SWITCHES)
    cone = next(item for item in nodes if item.get("concommand") == "r_flashlightfov")
    assert (cone["minvalue"], cone["maxvalue"]) == ("50", "200")
    assert len(files) == 223 and "shaders/fxc/flashlight_ps30.vcs" in files
    with zipfile.ZipFile(ROOT / "dist/C_session_release.zip") as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["helper_version"] == "1.3.1"
        assert archive.read("left4dead2/addons/" + C_FILENAME) == OUTPUT.read_bytes()
        assert archive.read("bin/neko/plugins/CSessionDefaults.dll") == (ROOT / "dist/c_session_helper/CSessionDefaults.dll").read_bytes()
    current = (ROOT / "README.md").read_text(encoding="utf-8")
    for required in ("1.3.1", C_FILENAME, "CSessionDefaults.dll", "165", "620", "1280×720", "L4N", "docs/INDEX.md"):
        assert required in current, required
    for obsolete in ("# B 全屏 ESC 菜单修改版", "dist/B_fullscreen_esc.vpk", "## 历史更新与开发记录"):
        assert obsolete not in current, obsolete
    result = {"scope": "Documentation constants versus current VPK/ZIP; not live game rendering",
              "version": manifest["helper_version"], "members": len(files), "checkboxes": len(switches),
              "defaults": expected, "fov_range": [50, 200],
              "vpk_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
              "zip_sha256": hashlib.sha256((ROOT / "dist/C_session_release.zip").read_bytes()).hexdigest(), "status": "PASS"}
    (REPORT / "facts.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS docs match package: 1.3.1, 223 members, 10 scoped checkboxes, defaults/FOV/network profile, pair ZIP")


def patch_record():
    before = json.loads((REPORT / "before.json").read_text(encoding="utf-8"))["documents"]
    after = {path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8-sig") for path in documents()}
    patch = []
    for name in sorted(set(before) | set(after)):
        old, new = before.get(name, ""), after.get(name, "")
        if old == new:
            continue
        for line in difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                        fromfile="a/" + name if name in before else "/dev/null",
                                        tofile="b/" + name if name in after else "/dev/null"):
            patch.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
    output = REPORT / "docs.patch"
    output.write_text("".join(patch), encoding="utf-8", newline="\n")
    command = ["git", "apply", "--check", "--reverse", str(output)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    record = {"command": command, "cwd": str(ROOT), "stdout": result.stdout, "stderr": result.stderr,
              "exit_status": result.returncode, "patch_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
              "rollback_command": "git apply --reverse reports/docs_archive/docs.patch",
              "scope": "Markdown-only reverse patch preflight, not applied to workspace",
              "documents_after": {name: digest(body) for name, body in after.items()}}
    (REPORT / "rollback_check.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result.stdout + result.stderr, end="")
    assert result.returncode == 0
    print("PASS documentation reverse patch preflight; original text snapshot and document hashes preserved")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("snapshot", "propose", "verify-moves", "check", "facts", "patch"))
    action = parser.parse_args().action
    {"snapshot": snapshot, "propose": proposed, "verify-moves": verify_moves,
     "check": check, "facts": facts, "patch": patch_record}[action]()
