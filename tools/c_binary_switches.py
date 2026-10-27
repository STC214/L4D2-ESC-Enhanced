"""Native GameUI checkboxes for semantically boolean settings, not numeric ranges."""

from inspect_menu import blocks, fields

# A checked box means the written effect is active. Never silently invert a
# replicated CVar or invent an unsupported inverted-checkbox resource flag.
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
    props.update(controlname="CvarToggleCheckButton", cvar_name=props["concommand"],
                 labeltext=SWITCHES[command], font="DefaultVerySmall", paintbackground="0",
                 tooltiptext="勾选：" + SWITCHES[command] + "；未勾选：不启用此项")
    # Flat native checkbox: remove SliderControl's nested drop-button child.
    lines = [f'"{name}"', "{"] + [f'\t"{key}" "{value}"' for key, value in props.items()] + ["}"]
    return "\n".join(lines)


def validate(text):
    seen = set()
    for name, _, _, block in blocks(text):
        props = fields(block)
        command = props.get("concommand", "").lower()
        if command in SWITCHES:
            assert props["controlname"] == "CvarToggleCheckButton"
            assert props["cvar_name"].lower() == command and props["labeltext"] == SWITCHES[command]
            assert '"BtnDropButton"' not in block
            assert props["minvalue"] == "0" and props["maxvalue"] == "1"
            seen.add(command)
        elif props.get("controlname") == "CvarToggleCheckButton":
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
