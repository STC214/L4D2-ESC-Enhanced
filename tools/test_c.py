"""Regression and fault-injection tests for the complete C build pipeline."""

import contextlib
import hashlib
import io
import json
import re
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from audit_c import inspect
from build_c_mod import OUTPUT, adapt_resource, prepare, validate_resolution, video_resolution
from c_menu_consolidation import PATCH, SUBMENUS, bindings, transform, baseline
from c_chat_layout import CHAT
from c_flashlight_assets import TEXTURES, SHADER, validate as validate_flashlight
from hud_integration import HUD, ROOT, LAYOUT, PICKUP, SPEED
from tumtara_integration import (
    MAIN, EXTRAS, FLYOUT, BEFORE, BUTTONS, MAIN_FILES, controls as menu_controls,
    validate as validate_tumtara,
)
from kv_audit import parse, scalars
from proxy_model import ScalarModel, speed_samples
from verify_c_mod import CFG, validate_files
from vpk import read, write


class KeyValuesTests(unittest.TestCase):
    def test_conditional_platforms_retained(self):
        tree = parse('Root { Panel [$X360] { fieldName "same" } Panel [$WIN32] { fieldName "same" } }')
        self.assertEqual(tree[0].value[0].conditions, ("[$X360]",))
        self.assertEqual(tree[0].value[1].conditions, ("[$WIN32]",))

    def test_scalar_duplicate_and_quoted_braces(self):
        tree = parse('Root { key "{" key "}" }')
        self.assertEqual(scalars(tree[0].value)["key"], "}")

    def test_malformed_pairs_rejected(self):
        for text in ('Root { key }', 'Root {', 'Root {} trailing', 'Root {} }', 'Root { key "unterminated'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse(text)


class ConfigurationTests(unittest.TestCase):
    def test_permanent_release_filename_shared(self):
        import audit_c
        import full_review
        import verify_tumtara_merge
        from release_paths import C_FILENAME, OUTPUT as release_output
        self.assertEqual(C_FILENAME, "【00】C_ESC_LED_血条和速度_TUMTaRA.vpk")
        self.assertEqual(OUTPUT, ROOT / "dist" / C_FILENAME)
        for path in (release_output, audit_c.OUTPUT, full_review.OUTPUT, verify_tumtara_merge.OUTPUT):
            self.assertEqual(path, OUTPUT)

    def test_comment_does_not_override_video_resolution(self):
        text = '// "setting.defaultres" "9999"\nVideoConfig { "setting.defaultres" "1280" "setting.defaultresheight" "720" }'
        self.assertEqual(video_resolution(text), (1280, 720))

    def test_ambiguous_or_incomplete_video_rejected(self):
        for text in ('"setting.defaultres" "1280"',
                     'VideoConfig { "setting.defaultres" "1280" "setting.defaultres" "1920" "setting.defaultresheight" "720" }',
                     '"setting.defaultres" "abc" "setting.defaultresheight" "720"'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                video_resolution(text)

    def test_invalid_sizes_rejected(self):
        for width, height in ((0, 720), (1280, 0), (-1, 720), (1280, 400), (720, 1280)):
            with self.subTest(width=width, height=height), self.assertRaises(ValueError):
                validate_resolution(width, height)

    def test_cli_zero_width_does_not_publish(self):
        before = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
        result = subprocess.run([sys.executable, "-X", "utf8", "tools/build_c_mod.py", "--width", "0", "--height", "720"],
                                cwd=ROOT, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(hashlib.sha256(OUTPUT.read_bytes()).hexdigest(), before)


class ArchiveTests(unittest.TestCase):
    def test_vpk_roundtrip(self):
        with tempfile.TemporaryDirectory(prefix="c-vpk-test-") as directory:
            path = Path(directory) / "fixture.vpk"
            files = {"a/item.txt": b"fixture payload", "root.bin": bytes(range(255))}
            write(path, files)
            self.assertEqual(read(path), files)

    def test_vpk_crc_failure(self):
        with tempfile.TemporaryDirectory(prefix="c-vpk-test-") as directory:
            path = Path(directory) / "fixture.vpk"
            write(path, {"a.txt": b"test payload"})
            raw = bytearray(path.read_bytes())
            raw[-1] ^= 1
            path.write_bytes(raw)
            with self.assertRaises(AssertionError):
                read(path)

    def test_vpk_truncation_failure(self):
        with tempfile.TemporaryDirectory(prefix="c-vpk-test-") as directory:
            path = Path(directory) / "fixture.vpk"
            path.write_bytes(b"\x34\x12\xaa\x55")
            with self.assertRaises((ValueError, AssertionError, struct.error)):
                read(path)

    def test_patch_bundle_complete(self):
        with zipfile.ZipFile(PATCH) as archive:
            self.assertIsNone(archive.testzip())
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["result_sha256"], hashlib.sha256(OUTPUT.read_bytes()).hexdigest())
            expected = {"manifest.json", "menus.patch", "CSessionDefaults.dll"} | {"payload/" + n for n in manifest["changes"]}
            self.assertEqual(set(archive.namelist()), expected)
            for name, hashes in manifest["changes"].items():
                self.assertEqual(hashlib.sha256(archive.read("payload/" + name)).hexdigest(), hashes["after"])


class WholePackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = read(OUTPUT)

    def test_all_static_members_and_speed_model(self):
        self.assertEqual(inspect(OUTPUT)["errors"], [])

    def test_exact_latest_c_delta_and_toolbox_preserved(self):
        before = read(BEFORE)
        self.assertEqual(set(self.files) - set(before), {FLYOUT, SHADER})
        self.assertEqual({n for n in before if before[n] != self.files[n]},
                         {MAIN, LAYOUT, PICKUP, "resource/ui/l4d360ui/ingamemainmenu.res", CFG, CHAT, *SUBMENUS, *TEXTURES})
        self.assertEqual(self.files[EXTRAS], before[EXTRAS])

    def test_esc_has_no_default_writers_and_accepts_native_fov(self):
        menu = menu_controls(self.files["resource/ui/l4d360ui/ingamemainmenu.res"])
        self.assertFalse(any(n.startswith("Init_") for n in menu))
        self.assertNotIn("GuangSheJiao", menu)
        for name in ("Flashlightfov",):
            self.assertLessEqual(float(menu[name]["minvalue"]), 53)
            self.assertGreaterEqual(float(menu[name]["maxvalue"]), 53)
        self.assertIn(b"\nr_flashlightfov 165\n", self.files[CFG])

    def test_all_duplicate_menu_bindings_merged(self):
        self.assertTrue(all(len(refs) == 1 for refs in bindings(self.files).values()))
        self.assertEqual(set(bindings(self.files)), set(bindings(baseline())))

    def test_integrated_flashlight_assets_and_outline_minima(self):
        validate_flashlight(self.files)
        refs = bindings(self.files)
        for name in ("sv_disable_glow_survivors", "sv_disable_glow_faritems"):
            self.assertEqual(refs[name][0][2]["minvalue"], "0")
            self.assertIn((name + " 0\n").encode(), self.files[CFG])

    def test_integrated_shader_and_texture_mutations_rejected(self):
        for path in (*sorted(TEXTURES), SHADER):
            bad = dict(self.files)
            bad[path] = bad[path][:-1]
            with self.subTest(path=path), self.assertRaises(AssertionError):
                validate_files(bad, 1280, 720)

    def test_binary_options_have_scoped_checkbox_commit_binding_and_effect_labels(self):
        from c_binary_switches import SWITCHES, CONTROL, validate as validate_switches
        from inspect_menu import blocks, fields
        text = self.files["resource/ui/l4d360ui/ingamemainmenu.res"].decode("utf-8-sig")
        validate_switches(text)
        nodes = {fields(b).get("concommand", "").lower(): fields(b) for _, _, _, b in blocks(text)}
        texts = {fields(b).get("concommand", "").lower(): b for _, _, _, b in blocks(text)}
        for command in SWITCHES:
            self.assertEqual(nodes[command]["controlname"], CONTROL)
            self.assertEqual(nodes[command]["fieldname"], "C_ESC_BOOL_" + command)
            self.assertEqual(nodes[command]["cvar_name"].lower(), command)
            self.assertNotIn('"BtnDropButton"', texts[command])
            self.assertEqual(re.findall(r'"labeltext"\s+"([^"\n]+)"', texts[command], re.I), [SWITCHES[command]])
        for command in ("r_flashlightconstant", "r_rainparticledensity", "r_snowparticles", "cl_ragdoll_maxcount", "r_flashlightfov"):
            self.assertEqual(nodes[command]["controlname"], "SliderControl")
        header = (ROOT / "native/c_session_defaults/checkbox_bridge.h").read_text(encoding="utf-8")
        for command in SWITCHES:
            self.assertIn('"' + command + '"', header)

    def test_binary_options_first_and_remaining_relative_order_unchanged(self):
        from c_binary_switches import SWITCHES, CONTROL
        from inspect_menu import blocks, fields
        menu = "resource/ui/l4d360ui/ingamemainmenu.res"
        nodes = {fields(b)["concommand"].lower(): fields(b) for _, _, _, b in blocks(self.files[menu].decode("utf-8-sig"))
                 if fields(b).get("controlname") in ("SliderControl", CONTROL)}
        live_names = {props["fieldname"] for props in nodes.values()}
        original = [fields(b)["concommand"].lower() for name, _, _, b in blocks(baseline()[menu].decode("utf-8-sig"))
                    if fields(b).get("concommand", "").lower() in nodes and
                    (name in live_names or fields(b)["concommand"].lower() in SWITCHES)]
        binary = [name for name in original if name in SWITCHES]
        other = [name for name in original if name not in binary]
        visual = sorted(nodes, key=lambda name: (nodes[name]["xpos"] == "r196", int(nodes[name]["ypos"])))
        self.assertEqual(len(binary), 10)
        self.assertEqual(visual, binary + other)

    def test_chat_only_changes_two_resources(self):
        from c_chat_layout import apply as apply_chat, baseline as chat_baseline
        before = chat_baseline()
        chat_only = apply_chat(before)
        self.assertEqual({p for p in before if before[p] != chat_only[p]}, {CHAT, LAYOUT})
        for path in (CHAT, LAYOUT):
            self.assertEqual(chat_only[path], self.files[path])

    def test_fullscreen_background_uses_uniform_fill(self):
        menu = menu_controls(self.files["resource/ui/l4d360ui/ingamemainmenu.res"])
        panel = menu["PnlBackground_tweaks1"]
        for key, value in {"xpos": "0", "ypos": "0", "wide": "f0", "tall": "f0",
                           "paintbackground": "1", "paintbackgroundtype": "0",
                           "bgcolor_override": "0 0 0 232"}.items():
            self.assertEqual(panel[key], value)

    def test_chat_bottom_right_and_input_containment(self):
        from c_chat_layout import validate as validate_chat
        with contextlib.redirect_stdout(io.StringIO()):
            validate_chat(self.files)

    def test_chat_old_position_regression_rejected(self):
        from c_chat_layout import baseline as chat_baseline
        bad = dict(self.files)
        bad[CHAT] = chat_baseline()[CHAT]
        with self.assertRaises(AssertionError), contextlib.redirect_stdout(io.StringIO()):
            validate_files(bad, 1280, 720)

    def test_all_weather_defaults_are_zero(self):
        for command in (b"r_RainParticleDensity", b"r_SnowParticles", b"fog_override", b"fog_enable"):
            self.assertIn(b"\n" + command + b" 0\n", self.files[CFG])

    def test_consolidated_resolution_profiles(self):
        for width, height in ((640, 480), (1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)):
            with self.subTest(width=width, height=height), contextlib.redirect_stdout(io.StringIO()):
                validate_files(transform(baseline(), width, height), width, height)

    def test_first_escape_does_not_lock_slider_range(self):
        from c_menu_consolidation import MENU
        menu = menu_controls(self.files[MENU])
        self.assertEqual((menu["Flashlightfov"]["minvalue"], menu["Flashlightfov"]["maxvalue"]), ("50", "200"))
        self.assertIn("手电光圈".encode(), self.files[MENU])
        self.assertEqual((menu["c_thirdpersonshoulderheight-"]["minvalue"],
                          menu["c_thirdpersonshoulderheight-"]["maxvalue"]), ("-1000", "1000"))

    def test_duplicate_submenu_regression_rejected(self):
        bad = dict(self.files)
        bad[SUBMENUS[0]] = baseline()[SUBMENUS[0]]
        with self.assertRaises(AssertionError), contextlib.redirect_stdout(io.StringIO()):
            validate_files(bad, 1280, 720)

    def test_weather_enabled_regression_rejected(self):
        for command in (b"r_RainParticleDensity", b"r_SnowParticles", b"fog_override", b"fog_enable"):
            bad = dict(self.files)
            bad[CFG] = bad[CFG].replace(command + b" 0", command + b" 1")
            with self.subTest(command=command), self.assertRaises(AssertionError), contextlib.redirect_stdout(io.StringIO()):
                validate_files(bad, 1280, 720)

    def test_flashlight_bound_lock_regression_rejected(self):
        from c_menu_consolidation import MENU
        bad = dict(self.files)
        bad[MENU] = adapt_resource(bad[MENU].decode(), {"Flashlightfov": {"minvalue": "150"}}).encode()
        with self.assertRaises(AssertionError), contextlib.redirect_stdout(io.StringIO()):
            validate_files(bad, 1280, 720)

    def test_removed_navigation_target_regression_rejected(self):
        from c_menu_consolidation import MENU
        bad = dict(self.files)
        bad[MENU] = adapt_resource(bad[MENU].decode(), {"QuickKickPlayer": {"navright": "GuangSheJiao"}}).encode()
        with self.assertRaises(AssertionError), contextlib.redirect_stdout(io.StringIO()):
            validate_files(bad, 1280, 720)

    def test_old_esc_initializer_regression_rejected(self):
        from c_session_policy import BASE as session_base, MENU
        bad = dict(self.files)
        bad[MENU] = read(session_base)[MENU]
        with self.assertRaises(AssertionError), contextlib.redirect_stdout(io.StringIO()):
            validate_files(bad, 1280, 720)

    def test_donor_speed_default_layout(self):
        donor = read(HUD)
        self.assertEqual(self.files[PICKUP], donor[PICKUP])
        self.assertEqual(menu_controls(self.files[LAYOUT])["CItemPickupPanel"],
                         menu_controls(donor[LAYOUT])["CItemPickupPanel"])
        for name in SPEED:
            self.assertEqual(menu_controls(self.files[PICKUP])[name], menu_controls(donor[PICKUP])[name])

    def test_real_tumtara_menu_and_dependency_boundary(self):
        with contextlib.redirect_stdout(io.StringIO()):
            validate_tumtara(self.files)
        self.assertEqual(self.files[FLYOUT], read(MAIN_FILES)[FLYOUT])
        self.assertNotIn(FLYOUT, read(BUTTONS))
        self.assertFalse(any(n.startswith("maps/") for n in self.files))

    def test_tumtara_missing_resource_rejected(self):
        bad = dict(self.files)
        del bad[FLYOUT]
        with self.assertRaises((AssertionError, KeyError)), contextlib.redirect_stdout(io.StringIO()):
            validate_files(bad, 1280, 720)

    def test_tumtara_c_menu_regression_rejected(self):
        bad = dict(self.files)
        bad[MAIN] = bad[MAIN].replace('工具箱'.encode(), b'LOST_C_TOOLBOX')
        with self.assertRaises(AssertionError), contextlib.redirect_stdout(io.StringIO()):
            validate_tumtara(bad)

    def test_tumtara_button_out_of_bounds_rejected(self):
        bad = dict(self.files)
        bad[MAIN] = adapt_resource(bad[MAIN].decode(), {"BtnTUMTaRA": {"xpos": "9999"}}).encode()
        with self.assertRaises(AssertionError), contextlib.redirect_stdout(io.StringIO()):
            validate_tumtara(bad)

    def test_tumtara_popup_offset_out_of_bounds_rejected(self):
        bad = dict(self.files)
        bad[MAIN] = adapt_resource(bad[MAIN].decode(), {"FlmTUMTaRA": {"ypos": "-9999"}}).encode()
        with self.assertRaises(AssertionError), contextlib.redirect_stdout(io.StringIO()):
            validate_tumtara(bad)

    def test_tumtara_console_command_regression_rejected(self):
        bad = dict(self.files)
        bad[MAIN] = adapt_resource(bad[MAIN].decode(), {"BtnConsole": {"command": "#quit"}}).encode()
        with self.assertRaises(AssertionError), contextlib.redirect_stdout(io.StringIO()):
            validate_tumtara(bad)

    def test_speed_top_left_regression_rejected(self):
        bad = dict(self.files)
        bad[PICKUP] = read(BEFORE)[PICKUP]
        with self.assertRaises(AssertionError), contextlib.redirect_stdout(io.StringIO()):
            validate_files(bad, 1280, 720)

    def test_all_resolution_profiles(self):
        for width, height in ((640, 480), (1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)):
            with self.subTest(width=width, height=height), contextlib.redirect_stdout(io.StringIO()):
                files = prepare(width, height)
                validate_files(files, width, height)
                self.assertEqual(inspect(None, files)["errors"], [])

    def test_original_speed_defect_detected(self):
        old = read(HUD)
        rows = speed_samples(old)
        self.assertTrue(any(row["speed"] == 85 and row["actual_text"] == "0080" for row in rows))
        self.assertTrue(all(row["pass"] for row in speed_samples(self.files)))

    def test_first_bind_and_float_boundaries(self):
        for speed in (0, 0.5, 9.99, 85, 99.99, 1000.01, 9999, 10000):
            models = [ScalarModel(self.files[f"materials/vgui/hud/digits_{n}.vmt"].decode()) for n in (8, 17, 18, 19)]
            actual = "".join(str(m.bind(speed)) for m in models)
            self.assertEqual(actual, f"{int(min(9999, max(0, speed))):04d}")

    def test_max_average_material_sequences(self):
        sequences = (("max", (16, 13, 14, 15)), ("average", (12, 9, 10, 11)))
        speeds = [0, 85, 220, 250, 999, 1205, 9]
        for title, numbers in sequences:
            models = [ScalarModel(self.files[f"materials/vgui/hud/digits_{n}.vmt"].decode()) for n in numbers]
            for i, speed in enumerate(speeds):
                digits = [m.bind(speed, i + 1) for m in models]
                samples = [s for s in speeds[:i + 1] if s > 0]
                expected = max(samples, default=0) if title == "max" else int(sum(samples) / len(samples)) if samples else 0
                self.assertEqual("".join(str(d) for d in digits), f"{expected:04d}")

    def test_crosshair_regression_rejected(self):
        bad = dict(self.files)
        bad["materials/vgui/hud/altcrosshair.vtf"] = read(HUD)["materials/vgui/hud/altcrosshair.vtf"]
        with self.assertRaises(AssertionError), contextlib.redirect_stdout(io.StringIO()):
            validate_files(bad, 1280, 720)

    def test_unsafe_graph_height_rejected(self):
        bad = dict(self.files)
        bad[CFG] = bad[CFG].replace(b"net_graphheight 620", b"net_graphheight 2160")
        with self.assertRaises(AssertionError), contextlib.redirect_stdout(io.StringIO()):
            validate_files(bad, 1280, 720)

    def test_invalid_material_rejected(self):
        bad = dict(self.files)
        bad["materials/vgui/active.vmt"] = b'UnlitGeneric { "$basetexture" "vgui/active"'
        errors = inspect(None, bad)["errors"]
        self.assertTrue(any(row["file"] == "materials/vgui/active.vmt" for row in errors))

    def test_texture_payload_truncation_rejected(self):
        bad = dict(self.files)
        key = "materials/vgui/hud/speedometer.vtf"
        bad[key] = bad[key][:-1000]
        errors = inspect(None, bad)["errors"]
        self.assertTrue(any(row["file"] == key and row["issue"] == "texture-header" for row in errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
