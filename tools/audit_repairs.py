"""Narrow, evidence-backed repairs for defects found by independent C audits."""

from kv_audit import parse
from inspect_menu import blocks
from prepare_menu_patch import set_fields


CURRENT_DIGITS = {8: 1000, 17: 100, 18: 10, 19: 1}


def digit_material(divisor):
    # Explicit float temporaries avoid Source math proxies' integer-destination
    # arithmetic on the first bind. Final frame is an integer in [0,9].
    return f'''UnlitGeneric
{{
    "$basetexture" "vgui/hud/digits_1"
    "$translucent" "1"
    "$alpha" "1"
    "$vertexalpha" "1"
    "$ignorez" "1"
    "$no_fullbright" "1"
    "$vertexcolor" "1"
    "$speed" "0.0"
    "$bounded" "0.0"
    "$divisor" "{divisor}.0"
    "$ten" "10.0"
    "$quotient" "0.0"
    "$integer" "0.0"
    "$groups" "0.0"
    "$groups_integer" "0.0"
    "$multiple" "0.0"
    "$digit" "0.0"
    "$frame" "0"
    "Proxies"
    {{
        "PlayerSpeed" {{ "scale" "1" "resultVar" "$speed" }}
        "Clamp" {{ "srcVar1" "$speed" "min" "0" "max" "9999" "resultVar" "$bounded" }}
        "Divide" {{ "srcVar1" "$bounded" "srcVar2" "$divisor" "resultVar" "$quotient" }}
        "Int" {{ "srcVar1" "$quotient" "resultVar" "$integer" }}
        "Divide" {{ "srcVar1" "$integer" "srcVar2" "$ten" "resultVar" "$groups" }}
        "Int" {{ "srcVar1" "$groups" "resultVar" "$groups_integer" }}
        "Multiply" {{ "srcVar1" "$groups_integer" "srcVar2" "$ten" "resultVar" "$multiple" }}
        "Subtract" {{ "srcVar1" "$integer" "srcVar2" "$multiple" "resultVar" "$digit" }}
        "Int" {{ "srcVar1" "$digit" "resultVar" "$frame" }}
    }}
}}
'''


def repair_donor(name, content):
    if not name.endswith((".res", ".vmt")):
        return content
    text = content.decode("utf-8-sig")
    if name in ("materials/vgui/active.vmt", "materials/vgui/hud/scalablepanel_bgblack_outlinegrey.vmt"):
        text += "\n}\n}\n"
    elif name == "materials/vgui/arcgpt.vmt":
        assert text.rstrip().endswith("ArcPav")
        text = text[:text.rfind("ArcPav")]
    elif name == "materials/vgui/hud/s_equip_bg_inactive.vmt":
        obsolete = '$baseTexture "vgui\\hud\\S_equip_bg_inactive1"'
        assert text.count(obsolete) == 1
        text = text.replace(obsolete, "// Removed nonexistent duplicate base texture")
    elif name == "materials/vgui/hud/healthbar_bg_player.vmt":
        assert "healthbar_bg_4" in text
        text = text.replace("healthbar_bg_4", "healthbar_bg_player")
    elif name in ("resource/ui/hud/localplayerpanel_incap.res", "resource/ui/hud/teammatepanel_incap.res"):
        for control, start, end, block in reversed(blocks(text)):
            if control == "DownSign":
                text = text[:start] + set_fields(block, {"fieldname": "DownSign"}) + text[end:]
    elif name == "resource/ui/hud/teammatepanel.res":
        heads = [(start, end) for control, start, end, _ in blocks(text) if control == "Head"]
        assert len(heads) == 2
        # Preserve the later avatar declaration, with its intended 30x30 size.
        start, end = heads[0]
        text = text[:start] + text[end:]
    else:
        for number, divisor in CURRENT_DIGITS.items():
            if name == f"materials/vgui/hud/digits_{number}.vmt":
                text = digit_material(divisor)
                break
    if text != content.decode("utf-8-sig"):
        parse(text)
        return text.encode("utf-8")
    return content


if __name__ == "__main__":
    from pathlib import Path
    from vpk import read
    from proxy_model import speed_samples

    root = Path(__file__).resolve().parents[1]
    source = read(root / "originals/HUD_3230782214.vpk")
    # The pre-existing extra team-incap closer is repaired by the merge stage.
    selected = {n: c for n, c in source.items() if n != "resource/ui/hud/teammatepanel_incap.res"}
    repaired = {n: repair_donor(n, c) for n, c in selected.items()}
    rows = speed_samples(repaired)
    for row in rows:
        print(row)
    assert all(row["pass"] for row in rows)
    print("PASS narrow material/control repairs and integer speed frame model")
