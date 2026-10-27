"""Reverse-gain LED experiment: original DXT5 format, RGB endpoints at half.

This is a diagnostic candidate, not a claim that lower RGB gives more light.
All alpha blocks, color selectors, VTF headers and texture geometry stay intact.
"""

import json
import shutil
import struct
import zipfile

from led_texture_2x import TEXTURES, layout, decode_bc3
from release_paths import ROOT, OUTPUT
from c_session_release import save, sha
from vpk import read, write

DIRECTORY = ROOT / "dist/led_half_test"
REPORT = ROOT / "reports/led_half_test"


def half565(value):
    return (((value >> 11) // 2) << 11) | ((((value >> 5) & 63) // 2) << 5) | ((value & 31) // 2)


def transform(data):
    assert struct.unpack_from("<I", data, 52)[0] == 15
    offset, width, height, mips = layout(data)
    output = bytearray(data)
    measurements = []
    for level in reversed(range(mips)):
        w, h = max(1, width >> level), max(1, height >> level)
        size = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 16
        for block in range(offset, offset + size, 16):
            c0, c1 = struct.unpack_from("<HH", data, block + 8)
            struct.pack_into("<HH", output, block + 8, half565(c0), half565(c1))
            assert output[block:block + 8] == data[block:block + 8]
            assert output[block + 12:block + 16] == data[block + 12:block + 16]
        before = decode_bc3(data[offset:offset + size], w, h)
        after = decode_bc3(output[offset:offset + size], w, h)
        before_sum = after_sum = 0
        for old, new in zip(before, after):
            assert old[3] == new[3]
            assert all(b <= a for a, b in zip(old[:3], new[:3]))
            before_sum += sum(old[:3])
            after_sum += sum(new[:3])
        gain = after_sum / before_sum if before_sum else None
        assert gain is None or 0.40 < gain < 0.51
        measurements.append({"mip": level, "rgb_sum_gain": gain})
        offset += size
    assert offset == len(data)
    start = layout(data)[0]
    assert output[:start] == data[:start]  # Header and low-res thumbnail unchanged.
    return bytes(output), measurements


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    baseline = DIRECTORY / "baseline.vpk.bak"
    if baseline.exists():
        assert sha(baseline) == sha(OUTPUT)
    else:
        shutil.copyfile(OUTPUT, baseline)
    before = read(baseline)
    after = dict(before)
    measurements = {}
    for name in TEXTURES:
        after[name], measurements[name] = transform(before[name])
    candidate = DIRECTORY / OUTPUT.name
    write(candidate, after)
    reopened = read(candidate)
    assert reopened == after
    assert {p for p in before if before[p] != after[p]} == set(TEXTURES)
    from audit_c import inspect
    assert not inspect(candidate)["errors"]
    patch = REPORT / "patch.zip"
    with zipfile.ZipFile(patch, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in TEXTURES:
            archive.writestr(name, after[name])
    replay = dict(before)
    with zipfile.ZipFile(patch) as archive:
        assert archive.testzip() is None
        replay.update({name: archive.read(name) for name in archive.namelist()})
    target = REPORT / "replayed.vpk"
    write(target, replay)
    assert target.read_bytes() == candidate.read_bytes()
    restored = DIRECTORY / "restored" / OUTPUT.name
    restored.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(baseline, restored)
    assert sha(restored) == sha(baseline) and read(restored) == before
    save(REPORT / "verification.json", {
        "scope": "DXT5 reverse-gain diagnostic; live brightness pending",
        "candidate_sha256": sha(candidate), "baseline_sha256": sha(baseline),
        "measurements": measurements, "format": "original DXT5 unchanged",
        "unchanged_members": len(before) - 2, "changed_members": list(TEXTURES),
        "patch": str(patch), "restored_baseline": str(restored)})
    print("PASS DXT5 half-RGB endpoints; alpha/selectors/header/thumbnail unchanged")
    print("PASS only two LED members changed; complete archive audit, patch replay and rollback copy")
    print("CANDIDATE", candidate)


if __name__ == "__main__":
    main()
