"""Full member audit independent of the merge generator and its golden outputs."""

import argparse
import ast
import hashlib
import json
import struct
from pathlib import Path, PurePosixPath

from kv_audit import parse, scalars, walk
from vpk import read
from proxy_model import speed_samples
from release_paths import OUTPUT


ROOT = Path(__file__).resolve().parents[1]


def inspect(archive, files=None):
    files = read(archive) if files is None else files
    errors, external, textures, parsed = [], [], {}, {}
    names = {name.lower(): name for name in files}
    if len(names) != len(files):
        errors.append({"file": str(archive), "issue": "case-insensitive member collision"})
    for name, data in files.items():
        parts = PurePosixPath(name)
        if parts.is_absolute() or ".." in parts.parts or "\\" in name:
            errors.append({"file": name, "issue": "invalid member path"})
        if name.endswith((".res", ".vmt")) or name == "addoninfo.txt":
            try:
                tree = parse(data.decode("utf-8-sig"))
                if len(tree) != 1 or not isinstance(tree[0].value, list):
                    raise ValueError("Resource must have exactly one root object")
                parsed[name] = tree
            except (ValueError, UnicodeError) as exc:
                errors.append({"file": name, "issue": "keyvalues", "detail": str(exc)})
        elif name.endswith(".vtf"):
            try:
                if len(data) < 64 or data[:4] != b"VTF\0":
                    raise ValueError("invalid VTF header")
                major, minor, header_size = struct.unpack_from("<III", data, 4)
                width, height = struct.unpack_from("<HH", data, 16)
                frames = struct.unpack_from("<H", data, 24)[0]
                image_format = struct.unpack_from("<I", data, 52)[0]
                mips = data[56]
                if major != 7 or not width or not height or not frames or not mips or not 64 <= header_size < len(data):
                    raise ValueError("invalid VTF dimensions/version/frames/header bounds")
                textures[name] = {"version": f"{major}.{minor}", "width": width, "height": height,
                                  "frames": frames, "format": image_format, "mips": mips}
                bytes_per_pixel = {0: 4, 1: 4, 2: 3, 3: 3, 4: 2, 5: 1, 6: 2,
                                   7: 1, 8: 1, 9: 3, 10: 3, 11: 4, 12: 4, 16: 4}
                block_bytes = {13: 8, 14: 16, 15: 16, 20: 8}
                low_format = struct.unpack_from("<I", data, 57)[0]
                low_w, low_h = data[61], data[62]
                def image_bytes(w, h, fmt):
                    if fmt in block_bytes:
                        return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * block_bytes[fmt]
                    if fmt in bytes_per_pixel:
                        return w * h * bytes_per_pixel[fmt]
                    raise ValueError(f"Uncovered VTF format {fmt}")
                if minor <= 2:
                    low_size = image_bytes(low_w, low_h, low_format) if low_w and low_h else 0
                    depth = struct.unpack_from("<H", data, 63)[0] if minor >= 2 else 1
                    flags = struct.unpack_from("<I", data, 20)[0]
                    if flags & 0x4000:
                        raise ValueError("Uncovered cubemap texture")
                    required = sum(image_bytes(max(1, width >> level), max(1, height >> level), image_format)
                                   * max(1, depth >> level) * frames for level in range(mips))
                    if header_size + low_size + required > len(data):
                        raise ValueError("Truncated VTF mip/frame payload")
            except (ValueError, struct.error) as exc:
                errors.append({"file": name, "issue": "texture-header", "detail": str(exc)})
    for name, tree in parsed.items():
        for location, node in walk(tree):
            if not isinstance(node.value, list):
                continue
            props = scalars(node.value)
            if name.endswith(".vmt"):
                values = [n.value for n in node.value if n.key.lower() == "$basetexture" and isinstance(n.value, str)]
                if len(set(values)) > 1:
                    errors.append({"file": name, "location": location, "issue": "conflicting-base-textures", "values": values})
            else:
                children = [(n, scalars(n.value)) for n in node.value if isinstance(n.value, list)]
                fields = {}
                for child, f in children:
                    if any(c.upper() in ("[$X360]", "[!$WIN32]") for c in child.conditions):
                        continue
                    if "controlname" not in f or not f.get("fieldname"):
                        continue
                    field = f["fieldname"].lower()
                    if field in fields:
                        old = fields[field]
                        # Legacy disabled duplicate ornaments are reported separately from active controls.
                        if f.get("visible", "1") != "0" or old[1].get("visible", "1") != "0":
                            errors.append({"file": name, "location": location,
                                           "issue": "duplicate-active-fieldname", "field": field,
                                           "blocks": [old[0].key, child.key]})
                    fields[field] = child, f
            for child in node.value:
                if not isinstance(child.value, str):
                    continue
                key = child.key.lower()
                path = child.value.replace("\\", "/").lower()
                target = None
                if name.endswith(".vmt") and key in ("$basetexture", "$detail", "$bumpmap", "$basetexture2"):
                    if not path.startswith(("_rt_", "env_cubemap")):
                        target = "materials/" + path.removeprefix("materials/")
                        if not target.endswith(".vtf"):
                            target += ".vtf"
                elif name.endswith(".res") and key == "image" and path and not path.startswith("#"):
                    if path.startswith("../vgui/"):
                        path = path.removeprefix("../")
                    elif not path.startswith("vgui/"):
                        path = "vgui/" + path
                    target = "materials/" + path + ".vmt"
                if target and target not in names:
                    external.append({"file": name, "location": location + "/" + child.key, "target": target})
    for path in sorted((ROOT / "tools").glob("*.py")):
        try:
            ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except SyntaxError as exc:
            errors.append({"file": str(path.relative_to(ROOT)), "issue": "python-syntax", "detail": str(exc)})
    speed_rows = speed_samples(files)
    for row in speed_rows:
        if not row["pass"]:
            errors.append({"file": "materials/vgui/hud/digits_*.vmt", "issue": "speed-frame-model", **row})
    return {
        "artifact": str(archive.resolve()) if archive else "in-memory preflight",
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest() if archive else None,
        "members": len(files), "parsed_keyvalues": len(parsed), "vtf_headers": len(textures),
        "errors": errors, "external_game_resource_references": external, "textures": textures,
        "finite_speed_model": speed_rows,
        "runtime_unverified": ["L4D2 load/render", "live speed/health updates", "menu initialization", "server cvar acceptance"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", nargs="?", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=ROOT / "reports/full_audit.json")
    args = parser.parse_args()
    report = inspect(args.archive)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    reopened = json.loads(args.report.read_text(encoding="utf-8"))
    assert reopened == report
    print(f"AUDIT members={report['members']} parsed={report['parsed_keyvalues']} textures={report['vtf_headers']}")
    for issue in report["errors"]:
        print(json.dumps(issue, ensure_ascii=False))
    print(f"ERRORS {len(report['errors'])}; external/base-game references {len(report['external_game_resource_references'])}")
    print("REPORT " + str(args.report.resolve()))
    raise SystemExit(bool(report["errors"]))


if __name__ == "__main__":
    main()
