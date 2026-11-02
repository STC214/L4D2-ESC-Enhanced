"""Static UI contract tests; not a substitute for Source UI runtime clicks."""

import unittest

from build_selector import build_files, validate, MULTIPLAYER
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from inspect_menu import blocks, fields
from prepare_menu_patch import set_fields


class SelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = build_files()

    def test_full_ui_contract(self):
        validate(self.files)

    def test_later_page_entries_have_distinct_confirm_and_apply(self):
        for number in (16, 17, 24, 25, 37, 40):
            content = self.files[f'resource/ui/csp_test/confirm_{number:03}.res'].decode()
            nodes = {name: fields(block) for name, _, _, block in blocks(content)}
            self.assertEqual(nodes[f'CSPApply{number:03}']['command'], f'CSP_TEST_APPLY_{number:03}')
            self.assertTrue(nodes['CSPConfirmPreview']['image'].endswith(f'test_{number:03}'))

    def test_missing_page_rejected(self):
        bad = dict(self.files)
        del bad['resource/ui/csp_test/page_4.res']
        with self.assertRaises(AssertionError):
            validate(bad)

    def test_misdirected_apply_rejected(self):
        bad = dict(self.files)
        path = 'resource/ui/csp_test/confirm_017.res'
        bad[path] = bad[path].replace(b'CSP_TEST_APPLY_017', b'CSP_TEST_APPLY_016')
        with self.assertRaises(AssertionError):
            validate(bad)

    def test_cancel_does_not_apply(self):
        for number in range(1, 41):
            content = self.files[f'resource/ui/csp_test/confirm_{number:03}.res'].decode()
            nodes = {name: fields(block) for name, _, _, block in blocks(content)}
            self.assertEqual(nodes['CSPCancel']['command'], f'FlmCSPPage{(number - 1) // 12 + 1}')

    def test_page_navigation_controls_reachable(self):
        path = 'resource/ui/csp_test/page_1.res'
        bad = dict(self.files)
        # Reintroduce the initial grid-only navigation trap; validator must catch it.
        bad[path] = bad[path].replace(b'"navdown" "CSPPrevPage"', b'"navdown" "CSPPick001"')
        bad[path] = bad[path].replace(b'"navup" "CSPClose"', b'"navup" "CSPPick012"')
        with self.assertRaises(AssertionError):
            validate(bad)

    def test_unrelated_native_menu_change_rejected(self):
        bad = dict(self.files)
        bad[MULTIPLAYER] = bad[MULTIPLAYER].replace(b'"Back"', b'"UnexpectedCommand"', 1)
        self.assertNotEqual(bad[MULTIPLAYER], self.files[MULTIPLAYER])
        with self.assertRaises(AssertionError):
            validate(bad)

    def test_zero_sized_popup_regression_rejected(self):
        text = self.files[MULTIPLAYER].decode()
        for name, start, end, block in blocks(text):
            if name in ('FlmCSPPage1', 'FlmCSPConfirm017'):
                bad = dict(self.files)
                bad[MULTIPLAYER] = (text[:start] + set_fields(block, {'wide': '0', 'tall': '0'}) + text[end:]).encode()
                with self.subTest(name=name), self.assertRaises(AssertionError):
                    validate(bad)

    def test_duplicate_vgui_preview_prefix_rejected(self):
        for path in ('resource/ui/csp_test/page_1.res', 'resource/ui/csp_test/confirm_017.res'):
            bad = dict(self.files)
            bad[path] = bad[path].replace(b'"image" "logos/ui/', b'"image" "vgui/logos/ui/', 1)
            self.assertNotEqual(bad[path], self.files[path])
            with self.subTest(path=path), self.assertRaises(AssertionError):
                validate(bad)


if __name__ == '__main__':
    unittest.main(verbosity=2)
