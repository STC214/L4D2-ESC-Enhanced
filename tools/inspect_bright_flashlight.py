"""Measure Workshop 2833227093 and local LED variants without installing it."""

import json
import math
import struct
from pathlib import Path

from c_session_release import ROOT, save, sha
from led_texture_2x import TEXTURES, decode_bc3, layout
from vpk import read

DIRECTORY = ROOT / "reports/bright_flashlight_2833227093"


def measure(data):
    offset, width, height, mips = layout(data)
    fmt = struct.unpack_from("<I", data, 52)[0]
    top_size = width * height * (8 if fmt == 24 else 1)
    if fmt == 15:
        pixels = decode_bc3(data[-top_size:], width, height)
        # Independent BC3 decoder comparison on the same top mip.
        from PIL import Image
        other = Image.frombytes("RGBA", (width, height), data[-top_size:], "bcn", 3).tobytes()
        assert all(abs(a - b) <= 1 for p, rgba in enumerate(pixels)
                   for a, b in zip(rgba, other[p * 4:p * 4 + 4]))
    elif fmt == 13:
        from PIL import Image
        size = max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * 8
        decoded = Image.frombytes("RGBA", (width, height), data[-size:], "bcn", 1).tobytes()
        pixels = [tuple(decoded[i:i + 4]) for i in range(0, len(decoded), 4)]
    else:
        assert fmt == 24
        pixels = [tuple(channel * 255 for channel in rgba)
                  for rgba in struct.iter_unpack("<eeee", data[-top_size:])]
    assert len(pixels) == width * height
    n = len(pixels)
    channels = [{"min": min(p[c] for p in pixels), "max": max(p[c] for p in pixels),
                 "mean": sum(p[c] for p in pixels) / n} for c in range(4)]
    lumas = [0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2] for p in pixels]
    rings = {}
    for low, high in ((0, .2), (.2, .5), (.5, .8), (.8, 1.0)):
        values = []
        for y in range(height):
            for x in range(width):
                radius = math.hypot((x + .5 - width / 2) / (width / 2),
                                    (y + .5 - height / 2) / (height / 2))
                if low <= radius < high:
                    values.append(lumas[y * width + x])
        rings[f"{low:.1f}-{high:.1f}"] = sum(values) / len(values)
    return {"width": width, "height": height, "format": fmt, "mips": mips,
            "flags": hex(struct.unpack_from("<I", data, 20)[0]),
            "reflectivity": list(struct.unpack_from("<fff", data, 32)),
            "channels_rgba_0_to_255_units": channels,
            "mean_luma_0_to_255_units": sum(lumas) / n,
            "white_pixel_percent": sum(min(p[:3]) >= 254 for p in pixels) * 100 / n,
            "black_pixel_percent": sum(max(p[:3]) == 0 for p in pixels) * 100 / n,
            "center_rgba": list(pixels[(height // 2) * width + width // 2]),
            "horizontal_center_samples_rgb": {str(x): list(pixels[(height // 2) * width + x][:3])
                                               for x in (16, 64, 128, 192, 256, 320, 384, 448, 496)},
            "radial_mean_luma": rings}


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    upstream = ROOT / "originals/BRIGHT_2833227093.vpk"
    source = read(upstream)
    assert list(source) == [TEXTURES[0]], "Unexpected runtime resources in upstream"
    extracted = DIRECTORY / TEXTURES[0]
    extracted.parent.mkdir(parents=True, exist_ok=True)
    extracted.write_bytes(source[TEXTURES[0]])
    assert extracted.read_bytes() == source[TEXTURES[0]]
    archives = {"Glare Flashlight": upstream,
                "C 原版 LED": ROOT / "dist/led_2x_test/baseline.vpk.bak",
                "浮点 2x 测试": ROOT / "dist/led_2x_test" / __import__("release_paths").C_FILENAME,
                "DXT5 半值对照": ROOT / "dist/led_half_test" / __import__("release_paths").C_FILENAME}
    results = {name: measure(read(path)[TEXTURES[0]]) for name, path in archives.items()}
    baseline = results["C 原版 LED"]["mean_luma_0_to_255_units"]
    for row in results.values():
        row["mean_luma_ratio_to_original_LED"] = row["mean_luma_0_to_255_units"] / baseline
    report = {"scope": "texture numeric data, not measured game output or screen luminance",
              "workshop_page": "https://steamcommunity.com/sharedfiles/filedetails/?id=2833227093",
              "upstream_sha256": sha(upstream), "inventory": {k: len(v) for k, v in source.items()},
              "independent_BC3_decoder_check": "Pillow comparison within 1/255 per component",
              "results": results, "game_files_modified_by_this_analysis": False}
    save(DIRECTORY / "analysis.json", report)
    rows = ["# Glare Flashlight 与 C LED 贴图数值对比\n",
            "仅统计顶级贴图数值，不等于屏幕或场景照度。未将此模组合并或部署。\n",
            "| 贴图 | 格式 | Mip 数 | RGB 亮度均值（0～255尺度） | 相对 C 原版 | 近纯白像素 |\n",
            "|---|---|---:|---:|---:|---:|\n"]
    for name, row in results.items():
        rows.append(f"| {name} | {row['format']} | {row['mips']} | {row['mean_luma_0_to_255_units']:.3f} | "
                    f"{row['mean_luma_ratio_to_original_LED']:.3f}× | {row['white_pixel_percent']:.2f}% |\n")
    rows += ["\n15 = DXT5；24 = RGBA16161616F。近纯白按所有 RGB 通道至少 254 统计。\n",
             "\n参考模组仅包含 materials/effects/flashlight001.vtf，无 VMT、CFG、DLL，也未覆盖 infected 版本。\n",
             "\n格式与 flags 解释参考 Valve SDK 的 bitmap/imageformat.h、vtf/vtf.h。\n",
             "\n推断：参考模组更高的贴图均值及更大的近纯白区域支持其增亮思路；"
             "没有证据支持把 RGB 调低就会更亮。浮点 2x 在游戏中变暗的原因仍需渲染路径验证。\n"]
    target = DIRECTORY / "分析.md"
    target.write_text("".join(rows), encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "".join(rows)
    print("".join(rows))
    print("REPORT", DIRECTORY / "analysis.json")


if __name__ == "__main__":
    main()
