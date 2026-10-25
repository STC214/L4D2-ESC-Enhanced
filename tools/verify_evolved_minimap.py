"""Targeted profile, deployment and negative tests without running Evolved."""

import argparse
import codecs
import contextlib
import io
import json
import unittest

from deploy_evolved_minimap import (
    BUNDLE, CFG, GAME, PLAN, PROFILE, SOURCE, STUDY, WORK, active_settings,
    config_payload, load, safe_target, sha, snapshot, verify,
)


class ProfileTests(unittest.TestCase):
    def test_defaults(self):
        values = active_settings(config_payload(None))
        self.assertEqual(values["NoHmdMinimapEnabled"], "true")
        self.assertEqual(values["NoHmdWorldNavigationEnabled"], "true")
        self.assertEqual(len(values), 8)

    def test_minimal_patch_preserves_user_values_comments_bom_crlf(self):
        old = codecs.BOM_UTF8 + b'# user\r\nOtherSetting=keep\r\nNoHmdMinimapEnabled=false\r\n'
        result = config_payload(old)
        self.assertTrue(result.startswith(codecs.BOM_UTF8))
        self.assertIn(b'# user\r\nOtherSetting=keep\r\n', result)
        self.assertNotIn(b'\n', result.replace(b'\r\n', b''))
        self.assertEqual(active_settings(result)["OtherSetting"], "keep")

    def test_duplicate_rejected(self):
        with self.assertRaises(AssertionError):
            config_payload(b'NoHmdMinimapEnabled=false\nNoHmdMinimapEnabled=true\n')

    def test_unknown_format_rejected(self):
        with self.assertRaises(AssertionError):
            config_payload(b'[UnknownSection]\n')

    def test_comment_is_not_active_value(self):
        self.assertEqual(active_settings(b'#NoHmdMinimapEnabled=false\n'), {})

    def test_profile_idempotent(self):
        self.assertEqual(config_payload(PROFILE.read_bytes()), PROFILE.read_bytes())

    def test_path_escape_rejected(self):
        for name in ('../outside.dll', 'C:/outside.dll'):
            with self.subTest(name=name), self.assertRaises(AssertionError):
                safe_target(name)

    def test_real_menu_descriptors_present(self):
        rows = {row['key']: row for row in load(STUDY / 'settings_table.json')['rows']}
        self.assertEqual(rows['NoHmdMinimapEnabled']['label'], '小地图导航')
        self.assertEqual(rows['NoHmdWorldNavigationEnabled']['label'], '实景导航箭头')
        self.assertEqual(rows['NoHmdMinimapEnabled']['type'], 0)
        self.assertEqual(rows['NoHmdWorldNavigationEnabled']['type'], 0)
        code = load(STUDY / 'command_registration_evidence.json')['pseudocode']
        self.assertIn('"evo_config"', code)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--tests', action='store_true')
    args = parser.parse_args()
    if args.tests:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProfileTests))
        raise SystemExit(not result.wasSuccessful())
    if args.baseline:
        plan = load(PLAN)
        for row in plan['records']:
            assert snapshot(safe_target(row['path'])) == row['before']
        sample = active_settings((SOURCE / 'Evolved/config.sample').read_bytes())
        assert 'NoHmdMinimapEnabled' not in sample and 'NoHmdWorldNavigationEnabled' not in sample
        print('PASS game baseline matches plan; original sample map/navigation entries are comments, not active settings')
        print('PASS original DLL bytes preserved; existing menu/console route requires no native patch')
        return
    verify()
    plan = load(PLAN)
    for name in ('bin/neko/plugins/L4D2Evolved.dll', 'bin/neko/plugins/L4d2evomodel.dll'):
        assert (GAME / name).read_bytes() == (SOURCE / name).read_bytes()
    assert not (GAME / 'Evolved/config2.txt').exists()
    assert active_settings((GAME / CFG).read_bytes()) == active_settings(PROFILE.read_bytes())
    print('PASS both native DLLs byte-identical; original settings menu and evo_config command retained')
    print('PASS explicit map/navigation defaults enabled, no second config override')


if __name__ == '__main__':
    main()
