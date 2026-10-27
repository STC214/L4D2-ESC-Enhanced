"""Scoped native checkboxes with companion immediate-commit bridge, grouped first."""

import math
import re

from inspect_menu import blocks, fields
from prepare_menu_patch import set_fields

# 1 means the written effect is active. The companion 1.3.1 bridge completes
# this exact GameUI control's otherwise deferred ApplyChanges event path.
CONTROL = "CvarToggleCheckButton_GameUI"
SWITCHES = {
    "mat_monitorgamma_tv_enabled": "电视亮度模式",
    "closecaption": "显示字幕",
    "gameinstructor_enable": "显示游戏提示",
    "sv_disable_glow_survivors": "关闭角色轮廓",
    "sv_disable_glow_faritems": "关闭远处物品轮廓",
    "director_show_intensity": "显示导演强度信息",
    "mat_fullbright": "地图全亮",
    "nav_edit": "导航网格编辑",
    "fog_override": "覆盖地图雾参数",
    "fog_enable": "显示雾气",
}


def convert(name, block):
    props = fields(block)
    command = props.get("concommand", "").lower()
    if command not in SWITCHES:
        return block
    assert props["minvalue"] == "0" and props["maxvalue"] == "1"
    assert props["controlname"] == "SliderControl", "Convert only the pinned slider baseline"
    unique = "C_ESC_BOOL_" + command
    props.update(controlname=CONTROL, fieldname=unique, cvar_name=props["concommand"],
                 labeltext=SWITCHES[command], font="DefaultVerySmall", paintbackground="0",
                 tooltiptext="勾选即提交：" + SWITCHES[command] + "；取消即关闭此项")
    return "\n".join([f'"{unique}"', "{"] + [f'\t"{key}" "{value}"' for key, value in props.items()] + ["}"])


def bridge_navigation(text, original):
    mapping = {name: "C_ESC_BOOL_" + props["concommand"].lower() for name, props in original.items()
               if props.get("concommand", "").lower() in SWITCHES}
    for _, start, end, block in reversed(blocks(text)):
        changes = {key: mapping[value] for key, value in fields(block).items()
                   if key.startswith("nav") and value in mapping}
        if changes:
            text = text[:start] + set_fields(block, changes) + text[end:]
    return text


def ordered_settings(names, properties):
    """Stable partition: boolean settings first, remaining relative order intact."""
    binary = [name for name in names if properties[name].get("concommand", "").lower() in SWITCHES]
    remaining = [name for name in names if name not in binary]
    return binary + remaining


def layout_changes(name, names):
    rows = math.ceil(len(names) / 2)
    column, row = divmod(names.index(name), rows)
    own = names[column * rows:(column + 1) * rows]
    other = names[(1 - column) * rows:(2 - column) * rows]
    peer = other[min(row, len(other) - 1)]
    return {"xpos": "c-92" if column == 0 else "r196", "ypos": str(14 + row * 19),
            "navup": own[(row - 1) % len(own)], "navdown": own[(row + 1) % len(own)],
            "navleft": peer, "navright": peer}


def validate(text):
    seen = set()
    for name, _, _, block in blocks(text):
        props = fields(block)
        command = props.get("concommand", "").lower()
        if command in SWITCHES:
            assert props["controlname"] == CONTROL
            assert props["fieldname"] == name == "C_ESC_BOOL_" + command
            assert props["cvar_name"].lower() == command
            assert '"BtnDropButton"' not in block
            assert props["minvalue"] == "0" and props["maxvalue"] == "1"
            assert re.findall(r'"labeltext"\s+"([^"\n]+)"', block, re.I) == [SWITCHES[command]]
            seen.add(command)
        elif props.get("controlname") in ("CvarToggleCheckButton", CONTROL):
            raise AssertionError("Numeric setting accidentally converted to checkbox: " + name)
    assert seen == set(SWITCHES)


def main():
    from c_menu_consolidation import baseline, MENU
    import re
    for name, _, _, block in blocks(baseline()[MENU].decode("utf-8-sig")):
        props = fields(block)
        if props.get("minvalue") == "0" and props.get("maxvalue") == "1":
            print(name, props.get("concommand"), re.findall(r'"labeltext"\s+"([^"\n]+)"', block, re.I))


if __name__ == "__main__":
    main()
