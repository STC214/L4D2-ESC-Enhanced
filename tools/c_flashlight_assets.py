"""Pinned C-integrated DXT5 mean-190 LED + no-fade/RGB2x shader assets."""

import argparse
from functools import lru_cache
import hashlib
import struct

from release_paths import ROOT

TEXTURES = {"materials/effects/flashlight001.vtf", "materials/effects/flashlight001_infected.vtf"}
SHADER = "shaders/fxc/flashlight_ps30.vcs"
ADDED = {SHADER}
ASSETS = ROOT / "assets/c_flashlight"
PINS = {"flashlight_mean190.vtf": "0d0f47eec8acdef70635e1aef07d73fed5ece212a0ddae1ec7c43a40feac41f9",
        "flashlight_nofade_gain2x_ps30.vcs": "8fd828f885ccce1a4b082ba9a4541b0023f5ffd72d2a29830a04f196abef06e5"}


@lru_cache(maxsize=1)
def payload():
    data = {name: (ASSETS / name).read_bytes() for name in PINS}
    assert all(hashlib.sha256(data[name]).hexdigest() == digest for name, digest in PINS.items())
    from led_texture_2x import layout, decode_bc3
    texture = data["flashlight_mean190.vtf"]
    offset, w, h, mips = layout(texture)
    assert (w, h, mips) == (512, 512, 1) and struct.unpack_from("<I", texture, 52)[0] == 15
    pixels = decode_bc3(texture[offset:], w, h)
    average = sum(.2126 * r + .7152 * g + .0722 * b for r, g, b, a in pixels) / (w * h)
    assert abs(average - 190) < .1 and all(p[3] == 255 for p in pixels)
    return {**{name: texture for name in TEXTURES}, SHADER: data["flashlight_nofade_gain2x_ps30.vcs"]}


def validate(files):
    assert all(files[name] == content for name, content in payload().items()), "Integrated flashlight payload differs"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify", "deep"))
    action = parser.parse_args().action
    if action == "prepare":
        from vpk import read
        from release_paths import C_FILENAME
        sources = {"flashlight_mean190.vtf": read(ROOT / "dist/led_mean190_test" / C_FILENAME)[next(iter(TEXTURES))],
                   "flashlight_nofade_gain2x_ps30.vcs": read(ROOT / "dist/flashlight_gain2x_test/C_flashlight_nofade_TEST.vpk")[SHADER]}
        ASSETS.mkdir(parents=True, exist_ok=True)
        for name, content in sources.items():
            assert hashlib.sha256(content).hexdigest() == PINS[name]
            target = ASSETS / name
            if target.exists():
                assert target.read_bytes() == content
            else:
                target.write_bytes(content)
            assert target.read_bytes() == content
    data = payload()
    if action == "deep":
        from verify_flashlight_nofade_test import cache_blobs, disassemble
        blobs = cache_blobs(data[SHADER])
        assert len(blobs) == 2832
        assert all(disassemble(code) == 0 for code in blobs.values())
        print("PASS all 2832 integrated shader programs disassemble")
    print("PASS pinned LED mean ~190 DXT5 and no-fade/RGB2x shader assets")


if __name__ == "__main__":
    main()
