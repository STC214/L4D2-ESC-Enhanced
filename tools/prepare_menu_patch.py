"""Print an apply_patch proposal; never write resource code directly."""

import math
import re
from pathlib import Path

from inspect_menu import TOKEN, blocks, fields


ROOT = Path(__file__).resolve().parents[1]
MENU = "resource/ui/l4d360ui/ingamemainmenu.res"
DEFAULTS = {
    "fog_enable": "0", "cl_ragdoll_maxcount": "0",
    "sv_disable_glow_survivors": "0", "sv_disable_glow_faritems": "0",
    "r_flashlightconstant": "1", "r_flashlightfar": "3000",
    "r_flashlightfov": "179",
}
LABELS = {
    "volume": "游戏音量", "snd_musicvolume": "音乐音量",
    "mat_monitorgamma": "屏幕伽马", "mat_monitorgamma_tv_enabled": "电视亮度模式",
    "closecaption": "字幕", "gameinstructor_enable": "游戏提示",
    "cl_viewmodelfovsurvivor": "手臂视场", "fov_desired": "第一视场",
    "cam_idealdist": "第三人称距离", "r_RainParticleDensity": "雨量",
    "r_SnowParticles": "雪量", "cl_crosshair_red": "准星红色",
    "cl_crosshair_green": "准星绿色", "cl_crosshair_blue": "准星蓝色",
    "cl_crosshair_alpha": "准星透明度", "cl_crosshair_thickness": "准星粗细",
    "cl_crosshair_dynamic": "动态准星", "net_graph": "网络参数图",
    "net_graphheight": "网络图高度", "net_graphpos": "网络图位置",
    "net_graphproportionalfont": "网络图字体", "net_graphshowinterp": "网络图色条",
    "cl_interp": "LERP 值", "cl_interp_ratio": "LERP 比率",
}


def set_fields(block, changes):
    tokens = [m for m in TOKEN.finditer(block) if not m[0].startswith("//")]
    depth = 0
    edits = []
    found = set()
    for i, token in enumerate(tokens):
        if token[0] == "{":
            depth += 1
        elif token[0] == "}":
            depth -= 1
        elif depth == 1:
            key = token[0].strip('"').lower()
            if key in changes and tokens[i + 1][0].startswith('"'):
                value = tokens[i + 1]
                edits.append((value.start(), value.end(), '"' + str(changes[key]) + '"'))
                found.add(key)
    for start, end, value in reversed(edits):
        block = block[:start] + value + block[end:]
    missing = {k: v for k, v in changes.items() if k not in found}
    if missing:
        at = block.index("{") + 1
        addition = "".join(f'\n\t\t"{k}" "{v}"' for k, v in missing.items())
        block = block[:at] + addition + block[at:]
    return block


def slider(name, command, minimum, maximum, label):
    return f'''"{name}"
\t{{
\t\t"ControlName" "SliderControl"
\t\t"fieldName" "{name}"
\t\t"xpos" "0"
\t\t"ypos" "0"
\t\t"wide" "184"
\t\t"tall" "15"
\t\t"visible" "1"
\t\t"enabled" "1"
\t\t"minValue" "{minimum}"
\t\t"maxValue" "{maximum}"
\t\t"stepSize" "1"
\t\t"conCommand" "{command}"
\t\t"inverseFill" "0"
\t\t"BtnDropButton"
\t\t{{
\t\t\t"ControlName" "L4D360HybridButton"
\t\t\t"fieldName" "BtnDropButton"
\t\t\t"tall" "15"
\t\t\t"visible" "1"
\t\t\t"enabled" "1"
\t\t\t"labelText" "{label}"
\t\t\t"style" "SmallButton"
\t\t\t"ActivationType" "1"
\t\t\t"OnlyActiveUser" "1"
\t\t}}
\t}}'''


def child_label(block, label, height=15):
    expression = re.compile(r'("labeltext"\s+")[^"]*(")', re.I)
    block = expression.sub(lambda m: m[1] + label + m[2], block)
    # Child-only label text height; no range or command mutations.
    block = re.sub(r'("tall"\s+")[^"]*(")', lambda m: m[1] + str(height) + m[2], block)
    return block


def generate():
    original = (ROOT / "extracted/B" / MENU).read_text(encoding="utf-8-sig")
    original_blocks = blocks(original)
    sliders = [(n, b) for n, _, _, b in original_blocks if fields(b).get("controlname") == "SliderControl"]
    known = {fields(b)["concommand"] for _, b in sliders}
    for filename in ("dropdowncrosshair.res", "dropdownnetgraph.res", "dropdownweathercontrol.res"):
        text = (ROOT / "extracted/B/resource/ui/l4d360ui" / filename).read_text(encoding="utf-8-sig")
        for name, _, _, block in blocks(text):
            f = fields(block)
            command = f.get("concommand")
            if f.get("controlname") == "SliderControl" and command not in known:
                name = "Expanded_" + name
                block = re.sub(r'"fieldName"\s+"[^"]+"', '"fieldName" "' + name + '"', block, count=1)
                block = re.sub(r'^"[^"]+"', '"' + name + '"', block, count=1)
                block = re.sub(r'^\s*"usablePlayerIndex"\s+"nobody"\s*$', "", block, flags=re.M | re.I)
                sliders.append((name, block))
                known.add(command)
    sliders.append(("ShiTiXianZhi", slider("ShiTiXianZhi", "cl_ragdoll_maxcount", "0", "75", "尸体数量")))
    rows = math.ceil(len(sliders) / 2)
    assert rows <= 24, len(sliders)
    replacements = {}
    additions = []
    for i, (name, block) in enumerate(sliders):
        column, row = divmod(i, rows)
        f = fields(block)
        labels = re.findall(r'"labeltext"\s+"([^"\n]*)"', block, re.I)
        label = next((v for v in labels if v.strip()), LABELS.get(f["concommand"], f["concommand"]))
        block = child_label(block, label)
        block = set_fields(block, {
            "xpos": "c-92" if column == 0 else "r196",
            "ypos": str(14 + row * 19), "wide": "184", "tall": "15", "zpos": "3",
            "navup": sliders[column * rows + (row - 1) % min(rows, len(sliders) - column * rows)][0],
            "navdown": sliders[column * rows + (row + 1) % min(rows, len(sliders) - column * rows)][0],
        })
        if name in {n for n, _, _, _ in original_blocks}:
            replacements[name] = block
        else:
            additions.append(block)
    actions = [(n, b) for n, _, _, b in original_blocks if fields(b).get("controlname") in ("L4D360HybridButton", "DropDownMenu")]
    action_labels = {"DrpTvGammaHint": "电视亮度说明", "DrpCaptionsHint": "字幕说明", "DrpGameInstructorHint": "游戏提示说明"}
    for i, (name, block) in enumerate(actions):
        block = set_fields(block, {"xpos": "12", "ypos": str(43 + i * 25), "wide": "184", "tall": "20", "navup": actions[(i - 1) % len(actions)][0], "navdown": actions[(i + 1) % len(actions)][0]})
        # DropDownMenu's own button width is explicit and must grow with its parent.
        if fields(block).get("controlname") == "DropDownMenu":
            block = re.sub(r'("wide"\s+")[^"]*(")', r'\g<1>184\2', block)
        if name in action_labels:
            block = child_label(block, action_labels[name], 20)
        replacements[name] = block
    for name, _, _, block in original_blocks:
        f = fields(block)
        if name.startswith("PnlBackground"):
            if name == "PnlBackground_tweaks1":
                replacements[name] = set_fields(block, {"xpos": "0", "ypos": "0", "wide": "f0", "tall": "f0", "zpos": "-1", "bgcolor_override": "0 0 0 200"})
                # Hide its old nested strip rather than retain an obsolete overlay.
                replacements[name] = replacements[name].replace('"0 0 0 167"', '"0 0 0 0"')
            else:
                replacements[name] = set_fields(block, {"visible": "0", "enabled": "0"})
        elif f.get("controlname") == "ImagePanel":
            clock = ["Time_hour10", "Time_hour01", "hm", "Time_min10", "Time_min01", "ms", "Time_sec10", "Time_sec01"]
            if name in clock:
                replacements[name] = set_fields(block, {"xpos": str(56 + clock.index(name) * 12), "ypos": "12"})
            else:
                replacements[name] = set_fields(block, {"visible": "0"})
    for name, start, end, block in reversed(original_blocks):
        if name in replacements:
            original = original[:start] + replacements[name] + original[end:]
    for command, value in DEFAULTS.items():
        block = slider("Init_" + command, command, value, value, "")
        block = set_fields(block, {"xpos": "0", "ypos": "9999", "wide": "1", "tall": "1", "mouseinputenabled": "0", "keyboardsinputenabled": "0"})
        additions.append(block)
    at = original.rfind("}")
    original = original[:at] + "\n\t// Expanded controls and requested defaults.\n\t" + "\n\t".join(additions) + "\n" + original[at:]
    assert len(blocks(original)) >= len(original_blocks)
    return original


if __name__ == "__main__":
    text = generate()
    print("*** Begin Patch")
    print("*** Add File: modified/" + MENU)
    print("\n".join("+" + line for line in text.splitlines()))
    print("*** End Patch")
