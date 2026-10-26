"""Bottom-right C chat overlay; keep unrelated HUD payloads byte-identical."""

import argparse
import difflib
import hashlib
from pathlib import Path
import shutil

from inspect_menu import blocks, fields
from prepare_menu_patch import set_fields
from release_paths import ROOT, OUTPUT, C_FILENAME
from verify_menu import coordinate
from vpk import read

CHAT = "resource/ui/basechat.res"
LAYOUT = "scripts/hudlayout.res"
BASE = ROOT / "originals/C_before_chat_bottom_right.vpk"
BASE_HASH = "b220c062478606ce1f0d7e5a27490ec7f604ec78a7b2c1e2495ddf331ada44ab"
ROOT_FIELDS = {"xpos": "r297", "ypos": "r200", "wide": "280", "tall": "120"}
CHANGES = {
    "HudChat": ROOT_FIELDS,
    "KeyStateLabel": {"wide": "260"},
    "ChatInputLine": {"ypos": "95", "tall": "20"},
    "HudChatHistory": {"ypos": "16"},
}


def baseline():
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_HASH
    return read(BASE)


def edit(data, changes):
    text = data.decode("utf-8-sig")
    found = set()
    for name, start, end, block in reversed(blocks(text)):
        if name in changes:
            text = text[:start] + set_fields(block, changes[name]) + text[end:]
            found.add(name)
    assert found == changes.keys()
    return text.encode("utf-8")


def apply(files):
    result = dict(files)
    result[CHAT] = edit(files[CHAT], CHANGES)
    result[LAYOUT] = edit(files[LAYOUT], {"HudChat": ROOT_FIELDS})
    return result


def validate(files):
    before = baseline()
    expected = apply(before)
    for path in (CHAT, LAYOUT):
        assert files[path] == expected[path], "Unexpected chat/HUD modification: " + path
    nodes = {n: fields(b) for n, _, _, b in blocks(files[CHAT].decode("utf-8-sig"))}
    root = nodes["HudChat"]
    assert all(root[k] == v for k, v in ROOT_FIELDS.items())
    w, h = float(root["wide"]), float(root["tall"])
    for name in ("KeyStateLabel", "ChatInputLine", "HudChatHistory", "ChatFiltersButton"):
        f = nodes[name]
        x, y, cw, ch = (float(f[k]) for k in ("xpos", "ypos", "wide", "tall"))
        assert 0 <= x and x + cw <= w and 0 <= y and y + ch <= h, name
    key, history, entry = (nodes[n] for n in ("KeyStateLabel", "HudChatHistory", "ChatInputLine"))
    assert float(key["ypos"]) + float(key["tall"]) <= float(history["ypos"])
    assert float(history["ypos"]) + float(history["tall"]) <= float(entry["ypos"])
    for width, height in ((640, 480), (1280, 720), (1920, 1080), (2560, 1440), (3440, 1440), (3840, 2160)):
        logical_width = width * 480 / height
        x, y = coordinate(root["xpos"], logical_width, w), coordinate(root["ypos"], 480, h)
        assert x >= 0 and y >= 0 and x + w <= logical_width and y + h <= 480
        assert abs(logical_width - x - w - 17) < 0.001
        assert 480 - y - h == 80
        # Finite default-Evo model: the map is at the top, while chat begins
        # at 280/480 of the rendering height. Not a live UI/capture assertion.
        assert y * height / 480 > 0.236111075 * height + 18 * max(0.65, min(width / 1920, height / 1080, 4))
    print("PASS chat right/bottom anchors; history/input/key label inside parent; six viewport models")
    print("PASS right margin 17, bottom HUD clearance 80 logical units; default-Evo finite layout separated")


def verify():
    before, current = baseline(), read(OUTPUT)
    assert set(before) == set(current)
    assert {p for p in before if before[p] != current[p]} == {CHAT, LAYOUT}
    validate(current)
    directory = ROOT / "reports/c_chat_bottom_right"
    directory.mkdir(parents=True, exist_ok=True)
    patch = "".join("".join(difflib.unified_diff(
        before[p].decode("utf-8-sig").splitlines(keepends=True),
        current[p].decode("utf-8-sig").splitlines(keepends=True),
        fromfile="before/" + p, tofile="after/" + p)) for p in (CHAT, LAYOUT))
    target = directory / "chat.patch"
    target.write_text(patch, encoding="utf-8", newline="\n")
    assert target.read_text(encoding="utf-8") == patch.replace("\r\n", "\n")
    print("PASS exact task delta: two chat resources; all other 220 members byte-identical")
    print("PATCH " + str(target))


def rollback_copy():
    before = baseline()
    target = ROOT / "dist/rollback_chat_bottom_right" / C_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BASE, target)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == BASE_HASH
    assert read(target) == before
    print("PASS previous C restored/reopened; helper unchanged: " + str(target))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("baseline", "verify", "rollback-copy"))
    action = parser.parse_args().action
    if action == "baseline":
        old = {n: fields(b) for n, _, _, b in blocks(baseline()[CHAT].decode("utf-8-sig"))}
        assert (old["HudChat"]["xpos"], old["HudChat"]["ypos"]) == ("17", "65")
        print("BASELINE chat x=17 y=65; input y=395 outside 100-high parent")
        print("BASE SHA256 " + BASE_HASH)
    elif action == "verify":
        verify()
    else:
        rollback_copy()


if __name__ == "__main__":
    main()
