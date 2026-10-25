"""Read-only comparison of C and Workshop item 2256147202; no game/mod edits."""

import difflib
import hashlib
import json
from pathlib import Path

from kv_audit import parse, scalars
from vpk import read


ROOT = Path(__file__).resolve().parents[1]
# Historical pre-merge diagnosis must use its preserved input, not latest C.
C = ROOT / "originals/C_before_tumtara_merge.vpk"
TARGET = ROOT / "originals/TUMTARA_2256147202.vpk"
MAIN = "resource/ui/l4d360ui/mainmenu.res"
EXTRAS = "resource/ui/l4d360ui/extrasflyout.res"
OUT = ROOT / "reports/conflict_2256147202"


def sha(content):
    return hashlib.sha256(content).hexdigest()


def controls(content):
    text = content.decode("utf-8-sig")
    tree = parse(text)
    assert len(tree) == 1 and isinstance(tree[0].value, list)
    return {
        node.key.lower(): {"name": node.key, "line": text.count("\n", 0, node.start) + 1,
                           "fields": scalars(node.value)}
        for node in tree[0].value if isinstance(node.value, list)
    }


def main():
    c_hash, target_hash = sha(C.read_bytes()), sha(TARGET.read_bytes())
    c, target = read(C), read(TARGET)
    canonical_c = {n.lower(): n for n in c}
    canonical_target = {n.lower(): n for n in target}
    common = sorted(set(canonical_c) & set(canonical_target))
    runtime = [n for n in common if n.endswith(".res")]
    assert runtime == sorted((MAIN, EXTRAS))
    c_main, target_main = controls(c[MAIN]), controls(target[MAIN])
    c_extras, target_extras = controls(c[EXTRAS]), controls(target[EXTRAS])
    relevant = ("btntumtara", "flmtumtara", "btnconsole", "btnserverbrowser", "reload_ui")
    for name in relevant:
        assert name in target_main and name not in c_main
    menu_resource = target_main["flmtumtara"]["fields"]["resourcefile"]
    assert menu_resource.lower() not in canonical_c
    assert menu_resource.lower() not in canonical_target
    # Attribution only: these are C's preserved B-origin resources, not other installed addons.
    b = read(ROOT / "originals/B_2906960647.vpk")
    origin_matches = {name: c[name] == b[name] for name in runtime}
    assert all(origin_matches.values())
    OUT.mkdir(parents=True, exist_ok=True)
    collisions = []
    for name in common:
        old, new = c[canonical_c[name]], target[canonical_target[name]]
        row = {"path": name, "same_bytes": old == new,
               "C_size": len(old), "target_size": len(new), "C_sha256": sha(old), "target_sha256": sha(new),
               "kind": "runtime UI replacement" if name in runtime else "addon metadata"}
        if name in runtime:
            diff = "".join(difflib.unified_diff(
                old.decode("utf-8-sig").splitlines(keepends=True),
                new.decode("utf-8-sig").splitlines(keepends=True),
                fromfile="C/" + name, tofile="2256147202/" + name,
            ))
            path = OUT / (Path(name).name + ".diff")
            path.write_text(diff, encoding="utf-8", newline="\n")
            assert path.read_text(encoding="utf-8") == diff.replace("\r\n", "\n")
            row["diff"] = str(path.relative_to(ROOT))
        collisions.append(row)
    # Finite file-priority model, not observation of this user's engine search path.
    c_wins = dict(target)
    c_wins.update(c)
    target_wins = dict(c)
    target_wins.update(target)
    assert "btntumtara" not in controls(c_wins[MAIN])
    assert "btntumtara" in controls(target_wins[MAIN])
    assert c_wins[EXTRAS] == c[EXTRAS] and target_wins[EXTRAS] == target[EXTRAS]
    report = {
        "scope": "C versus 2256147202 only; no other installed addons, dependency archives, or game runtime inspected",
        "inputs": {str(C.relative_to(ROOT)): {"sha256": c_hash, "members": len(c)},
                   str(TARGET.relative_to(ROOT)): {"sha256": target_hash, "members": len(target)}},
        "collisions": collisions,
        "C_B_origin_bytes_identical": origin_matches,
        "target_main_entries": {name: target_main[name] for name in relevant},
        "entries_absent_from_C_main": list(relevant),
        "C_only_extras_entries": sorted(set(c_extras) - set(target_extras)),
        "target_only_extras_entries": sorted(set(target_extras) - set(c_extras)),
        "referenced_TUMTaRA_menu": {"path": menu_resource, "in_C": False, "in_target": False,
                                   "dependency_status": "not inspected (outside this pair-only check)"},
        "priority_model": {
            "C_wins_shared_paths": "TUMTaRA main button/flyout definition, console and main-menu server-browser entries disappear",
            "target_wins_shared_paths": "TUMTaRA entries exist; C main/extras customizations at those paths are replaced",
        },
        "conclusion": "Confirmed direct resource-path conflict; C taking precedence explains missing TUMTaRA buttons",
        "not_proven": ["actual installed C/target versions", "engine's actual winning search-path entries", "whether required TUMTaRA main files are installed"],
        "modification": "none; C and target VPK bytes unchanged",
    }
    path = OUT / "comparison.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8")) == report
    assert sha(C.read_bytes()) == c_hash and sha(TARGET.read_bytes()) == target_hash
    print("PASS both VPK inventories and all member CRCs")
    print(f"C members={len(c)}; target members={len(target)}")
    for row in collisions:
        print(row["kind"], row["path"], "same_bytes=" + str(row["same_bytes"]))
    for name in relevant:
        row = target_main[name]
        f = row["fields"]
        print(f"Target line {row['line']}: {row['name']}; command={f.get('command', '')}; resource={f.get('resourcefile', '')}; absent in C")
    print("PASS both shared UI files byte-identical to C's B-origin versions")
    print("PASS file-priority model: C wins -> no TUMTaRA button; target wins -> button present")
    print("Dependency menu referenced but absent in BOTH packages: " + menu_resource)
    print("C unchanged SHA256 " + c_hash)
    print("REPORT " + str(path))


if __name__ == "__main__":
    main()
