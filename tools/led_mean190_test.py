"""Target ~190/255 decoded mean luminance using only ordinary DXT5 LED textures.

The Glare white plateau is already saturated. A centered texture-only expansion
raises its spatial mean while preserving a black circular surround. No CVar,
FOV, shader, DLL or model is changed. Measure AFTER BC3 encoding, not before.
"""

import io
import shutil
import struct
import zipfile

from PIL import Image, ImageStat

from c_session_release import ROOT, OUTPUT, save, sha
from led_texture_2x import TEXTURES, layout, decode_bc3
from vpk import read, write

DIRECTORY = ROOT / "dist/led_mean190_test"
REPORT = ROOT / "reports/led_mean190_test"
TARGET_MEAN = 190.0


def encode(image, fmt):
    stream = io.BytesIO()
    image.save(stream, format="DDS", pixel_format=fmt)
    data = stream.getvalue()
    assert data[:4] == b"DDS " and data[84:88] == fmt.encode("ascii")
    block_size = 16 if fmt == "DXT5" else 8
    expected = max(1, (image.width + 3) // 4) * max(1, (image.height + 3) // 4) * block_size
    assert len(data) == expected + 128
    return data[128:]


def mean(image):
    r, g, b = ImageStat.Stat(image).mean[:3]
    return .2126 * r + .7152 * g + .0722 * b


def build_texture(source):
    offset, w, h, mips = layout(source)
    assert (w, h, mips) == (512, 512, 1)
    assert struct.unpack_from("<I", source, 52)[0] == 15
    assert len(source) == offset + w * h
    original = Image.frombytes("RGBA", (w, h), source[offset:], "bcn", 3)
    baseline_mean = mean(original)
    assert baseline_mean < TARGET_MEAN
    best = None
    low, high = 1.0, 1.16
    for _ in range(19):
        scale = (low + high) / 2
        cx, cy = (w - 1) / 2, (h - 1) / 2
        expanded = original.transform((w, h), Image.Transform.AFFINE,
                                      (1 / scale, 0, cx - cx / scale, 0, 1 / scale, cy - cy / scale),
                                      resample=Image.Resampling.BILINEAR)
        compressed = encode(expanded, "DXT5")
        decoded = Image.frombytes("RGBA", (w, h), compressed, "bcn", 3)
        value = mean(decoded)
        if best is None or abs(value - TARGET_MEAN) < abs(best[0] - TARGET_MEAN):
            best = (value, scale, compressed, decoded)
        if value < TARGET_MEAN:
            low = scale
        else:
            high = scale
    value, scale, compressed, decoded = best
    assert abs(value - TARGET_MEAN) < .1
    assert decoded.getchannel("A").getextrema() == (255, 255)
    assert decoded.getpixel((256, 256)) == (255, 255, 255, 255)
    for xy in ((0, 0), (511, 0), (0, 511), (511, 511)):
        assert decoded.getpixel(xy)[:3] == (0, 0, 0)
    low_w, low_h = source[61:63]
    thumbnail = encode(decoded.resize((low_w, low_h), Image.Resampling.LANCZOS), "DXT1")
    result = source[:80] + thumbnail + compressed
    assert len(result) == len(source) and result[:80] == source[:80]
    independent = decode_bc3(result[offset:], w, h)
    independent_mean = sum(.2126 * r + .7152 * g + .0722 * b for r, g, b, a in independent) / (w * h)
    assert abs(independent_mean - value) < .05
    assert abs(independent_mean - TARGET_MEAN) < .1
    return result, {"baseline_Glare_mean": baseline_mean, "decoded_DXT5_mean": value,
                    "independent_decoder_mean": independent_mean, "texture_expansion_scale": scale,
                    "target": TARGET_MEAN, "range": [0, 255], "format": "DXT5",
                    "header_dimensions_flags_mips_unchanged_from_Glare": True,
                    "alpha_all_255": True, "black_corners_preserved": True}


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    upstream = ROOT / "originals/BRIGHT_2833227093.vpk"
    assert sha(upstream) == "d7ec3f83a31390e6cac0596cf4d9ffb89b8c9c7025f5c7e71a211d5bd2412243"
    original = read(upstream)[TEXTURES[0]]
    texture, metrics = build_texture(original)
    baseline = DIRECTORY / "baseline.vpk.bak"
    if baseline.exists():
        assert sha(baseline) == sha(OUTPUT)
    else:
        shutil.copyfile(OUTPUT, baseline)
    before = read(baseline)
    after = dict(before)
    after.update({p: texture for p in TEXTURES})
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
            archive.writestr(name, texture)
    replay = dict(before)
    with zipfile.ZipFile(patch) as archive:
        assert archive.testzip() is None
        replay.update({name: archive.read(name) for name in archive.namelist()})
    replayed = REPORT / "replayed.vpk"
    write(replayed, replay)
    assert replayed.read_bytes() == candidate.read_bytes()
    restored = DIRECTORY / "restored" / OUTPUT.name
    restored.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(baseline, restored)
    assert sha(restored) == sha(baseline) and read(restored) == before
    save(REPORT / "verification.json", {
        "scope": "ordinary compressed texture numeric mean; game output pending",
        "candidate_sha256": sha(candidate), "baseline_sha256": sha(baseline),
        "metrics": metrics, "changed_members": list(TEXTURES), "unchanged_members": len(before) - 2,
        "patch": str(patch), "restored_baseline": str(restored)})
    print("PASS DXT5 decoded mean:", metrics["decoded_DXT5_mean"], "independent:", metrics["independent_decoder_mean"])
    print("PASS only two LED textures changed; original Glare header/alpha retained; patch replay and rollback copy")
    print("CANDIDATE", candidate)


if __name__ == "__main__":
    main()
