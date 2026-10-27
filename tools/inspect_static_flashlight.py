"""Read Workshop 2931652155 inventory, scripts and MDL flashlight attachments."""

from collections import Counter
from pathlib import PurePosixPath
import struct

from c_session_release import ROOT, save, sha
from inspect_bright_flashlight import measure
from vpk import read


def string(data, at):
    assert 0 <= at < len(data)
    end = data.index(b"\0", at)
    return data[at:end].decode("utf-8", errors="replace")


def model_attachments(data):
    assert data[:4] == b"IDST" and struct.unpack_from("<I", data, 4)[0] == 49
    bone_count, bone_index = struct.unpack_from("<II", data, 156)
    count, index = struct.unpack_from("<II", data, 240)
    assert 0 <= bone_count < 512 and 0 <= count < 64
    result = []
    for i in range(count):
        at = index + i * 92
        name_index, flags, bone = struct.unpack_from("<IIi", data, at)
        name = string(data, at + name_index)
        assert 0 <= bone < bone_count
        b = bone_index + bone * 216
        bname, parent = struct.unpack_from("<Ii", data, b)
        matrix = struct.unpack_from("<12f", data, at + 12)
        result.append({"attachment": name, "bone_index": bone, "bone_name": string(data, b + bname),
                       "parent_bone_index": parent,
                       "bone_position": list(struct.unpack_from("<3f", data, b + 32)),
                       "attachment_translation": [matrix[3], matrix[7], matrix[11]],
                       "matrix3x4": list(matrix)})
    return result


def main():
    path = ROOT / "originals/APPROACH_2931652155.vpk"
    assert sha(path) == "ca8e3b0c5f64ac03e669f5e52dc44a5032a9dd61b8f0903b8ff555888401257e"
    files = read(path)
    directory = ROOT / "reports/static_flashlight_2931652155"
    directory.mkdir(parents=True, exist_ok=True)
    scripts = {p: b.decode("utf-8-sig") for p, b in files.items() if p.endswith(".nut")}
    for name, text in scripts.items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(files[name])
        assert target.read_bytes() == files[name]
    models = {p: model_attachments(b) for p, b in files.items() if p.endswith(".mdl")}
    texture = measure(files["materials/effects/flashlight001.vtf"])
    report = {"scope": "static package/MDL/script analysis; no script execution or in-game observation",
              "sha256": sha(path), "member_count": len(files),
              "types": dict(Counter(PurePosixPath(p).suffix for p in files)),
              "scripts": scripts, "model_attachments": models,
              "model_flashlight_literal_counts": {p: b.count(b"flashlight") for p, b in files.items() if p.endswith(".mdl")},
              "texture": texture, "shader_files": [p for p in files if p.endswith((".vcs", ".dll", ".hlsl", ".fxc"))],
              "changes_attenuation_cvars_in_scripts": any(s in text for text in scripts.values()
                  for s in ("r_flashlightconstant", "r_flashlightlinear", "r_flashlightquadratic", "r_flashlightfar")),
              "game_modified": False}
    save(directory / "analysis.json", report)
    print("MEMBERS", len(files), report["types"])
    print("SHADERS", report["shader_files"], "DISTANCE_CVARS", report["changes_attenuation_cvars_in_scripts"])
    print("TEXTURE_MEAN", texture["mean_luma_0_to_255_units"])
    for name, attachments in models.items():
        print(name, "attachments:", [a["attachment"] for a in attachments])
    print("REPORT", directory / "analysis.json")


if __name__ == "__main__":
    main()
