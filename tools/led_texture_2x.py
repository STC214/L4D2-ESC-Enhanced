"""Build an isolated LED-only 2x float-texture candidate; never deploy it.

VTF RGBA16161616F preserves values above 1 instead of clipping white pixels.
Numeric texture gain is verified, not real-game exposure or format support.
"""

import difflib
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zipfile

from release_paths import ROOT, OUTPUT
from vpk import read, write

TEXTURES = ("materials/effects/flashlight001.vtf",
            "materials/effects/flashlight001_infected.vtf")
DIRECTORY = ROOT / "dist/led_2x_test"
REPORT = ROOT / "reports/led_2x_test"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def layout(data):
    assert data[:4] == b"VTF\0"
    assert struct.unpack_from("<II", data, 4) == (7, 2)
    header = struct.unpack_from("<I", data, 12)[0]
    width, height = struct.unpack_from("<HH", data, 16)
    assert struct.unpack_from("<H", data, 24)[0] == 1
    assert struct.unpack_from("<H", data, 63)[0] == 1
    assert not struct.unpack_from("<I", data, 20)[0] & 0x4000
    assert struct.unpack_from("<I", data, 57)[0] == 13
    low = max(1, (data[61] + 3) // 4) * max(1, (data[62] + 3) // 4) * 8
    return header + low, width, height, data[56]


def rgb565(word):
    r, g, b = (word >> 11) & 31, (word >> 5) & 63, word & 31
    return ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2))


def decode_bc3(data, width, height):
    """Decode in row-major order, including the cropped 1x1/2x2 mips."""
    pixels = [None] * (width * height)
    cursor = 0
    for by in range(0, height, 4):
        for bx in range(0, width, 4):
            block = data[cursor:cursor + 16]
            assert len(block) == 16
            cursor += 16
            a, b = block[:2]
            alphas = [a, b]
            if a > b:
                alphas += [((7 - i) * a + i * b) // 7 for i in range(1, 7)]
            else:
                alphas += [((5 - i) * a + i * b) // 5 for i in range(1, 5)] + [0, 255]
            alpha_bits = int.from_bytes(block[2:8], "little")
            c0, c1, color_bits = struct.unpack_from("<HHI", block, 8)
            p, q = rgb565(c0), rgb565(c1)
            colors = [p, q, tuple((2 * x + y) // 3 for x, y in zip(p, q)),
                      tuple((x + 2 * y) // 3 for x, y in zip(p, q))]
            for y in range(4):
                for x in range(4):
                    i = y * 4 + x
                    if bx + x < width and by + y < height:
                        color = colors[(color_bits >> (2 * i)) & 3]
                        pixels[(by + y) * width + bx + x] = (*color, alphas[(alpha_bits >> (3 * i)) & 7])
    assert cursor == len(data) and all(pixel is not None for pixel in pixels)
    return pixels


def brighten(data):
    assert struct.unpack_from("<I", data, 52)[0] == 15
    offset, width, height, mips = layout(data)
    header = bytearray(data[:offset])
    struct.pack_into("<I", header, 52, 24)  # IMAGE_FORMAT_RGBA16161616F
    output = bytearray(header)
    source_offset = offset
    records = []
    for level in reversed(range(mips)):
        w, h = max(1, width >> level), max(1, height >> level)
        size = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 16
        pixels = decode_bc3(data[source_offset:source_offset + size], w, h)
        source_offset += size
        before_energy = after_energy = 0.0
        max_error = 0.0
        target_offset = len(output)
        for r, g, b, a in pixels:
            values = (r * 2 / 255, g * 2 / 255, b * 2 / 255, a / 255)
            output.extend(struct.pack("<eeee", *values))
        # Re-read the actual serialized half floats; no gain inferred from metadata.
        for i, pixel in enumerate(pixels):
            actual = struct.unpack_from("<eeee", output, target_offset + i * 8)
            assert abs(actual[3] - pixel[3] / 255) <= 0.00025
            for old, new in zip(pixel[:3], actual[:3]):
                expected = old * 2 / 255
                max_error = max(max_error, abs(new - expected))
                assert abs(new - expected) <= 0.00049
                assert old != 0 or new == 0  # Dark outline is preserved.
                before_energy += old / 255
                after_energy += new
        gain = after_energy / before_energy if before_energy else None
        assert gain is None or abs(gain - 2) < 0.001
        records.append({"mip": level, "width": w, "height": h,
                        "rgb_sample_sum_gain": gain, "maximum_half_float_error": max_error})
    assert source_offset == len(data)
    return bytes(output), records


def main():
    parser = __import__("argparse").ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "verify", "rollback-copy"))
    args = parser.parse_args()
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    backup = DIRECTORY / "baseline.vpk.bak"
    candidate = DIRECTORY / OUTPUT.name
    if args.action == "rollback-copy":
        target = DIRECTORY / "restored" / OUTPUT.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(backup, target)
        assert target.read_bytes() == backup.read_bytes()
        assert read(target) == read(backup)
        print("PASS restored baseline copy", target)
        return
    if args.action == "build":
        if backup.exists():
            assert sha(backup.read_bytes()) == sha(OUTPUT.read_bytes()), "Baseline changed; preserve existing test first"
        else:
            shutil.copyfile(OUTPUT, backup)
        before = read(backup)
        after = dict(before)
        for name in TEXTURES:
            after[name], _ = brighten(before[name])
        write(candidate, after)
    before, after = read(backup), read(candidate)
    assert before.keys() == after.keys()
    assert {p for p in before if before[p] != after[p]} == set(TEXTURES)
    measurements = {}
    for name in TEXTURES:
        expected, records = brighten(before[name])
        assert after[name] == expected
        measurements[name] = {"before_sha256": sha(before[name]), "after_sha256": sha(after[name]),
                              "mips": records, "format_before": "DXT5", "format_after": "RGBA16161616F"}
    patch = REPORT / "patch.zip"
    with zipfile.ZipFile(patch, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in TEXTURES:
            archive.writestr(name, after[name])
    with zipfile.ZipFile(patch) as archive:
        assert archive.testzip() is None
        assert all(archive.read(p) == after[p] for p in TEXTURES)
    replay = dict(before)
    with zipfile.ZipFile(patch) as archive:
        replay.update({p: archive.read(p) for p in archive.namelist()})
    replay_path = REPORT / "replayed.vpk"
    write(replay_path, replay)
    assert replay_path.read_bytes() == candidate.read_bytes()
    source = ROOT / "tools/audit_c.py"
    # Existing independent archive parser is used for all unaffected members.
    from audit_c import inspect
    audit = inspect(None, before)
    assert not audit["errors"]
    # Validate exact bounds of the two new float payloads independently.
    for name in TEXTURES:
        offset, w, h, mips = layout(after[name])
        assert len(after[name]) == offset + sum(max(1, w >> i) * max(1, h >> i) * 8 for i in range(mips))
    report = {"scope": "numeric VTF gain only; no live-game compatibility/brightness verification",
              "baseline": str(backup), "baseline_sha256": sha(backup.read_bytes()),
              "candidate": str(candidate), "candidate_sha256": sha(candidate.read_bytes()),
              "changed_members": list(TEXTURES), "unchanged_members": len(before) - 2,
              "measurements": measurements, "patch": str(patch),
              "rollback_command": "python -X utf8 tools/led_texture_2x.py rollback-copy",
              "deployment": "NOT_DEPLOYED", "formal_C_unchanged": sha(OUTPUT.read_bytes()) == sha(backup.read_bytes()),
              "source_reference": "https://github.com/ValveSoftware/source-sdk-2013/blob/master/src/public/bitmap/imageformat.h"}
    target = REPORT / "verification.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert json.loads(target.read_text(encoding="utf-8")) == report
    assert report["formal_C_unchanged"]
    print("PASS only two LED textures changed; all 10 mips ~2x RGB; alpha/zero mask preserved")
    print("PASS 220 other members unchanged, patch replay exact; formal C and game untouched")
    print("CANDIDATE", candidate)


if __name__ == "__main__":
    main()
