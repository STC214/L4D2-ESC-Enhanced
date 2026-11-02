"""Deployment fixtures stay inside reports; never modify the real game."""

import contextlib
import io
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import deploy
from vpk import write


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        base = deploy.ROOT / 'reports/spray_selector/deploy_fixtures'
        base.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.game = self.root / 'game'
        self.work = self.root / 'work'
        for relative in ('left4dead2/addons/workshop', 'bin/neko/plugins'):
            (self.game / relative).mkdir(parents=True)
        self.raw = '"AddonList"\r\n{\r\n\t"正常.vpk" "1"\r\n}\r\n'.encode('gb18030')
        self.addonlist = self.game / 'left4dead2/addonlist.txt'
        self.addonlist.write_bytes(self.raw)
        for key, value in (('WORK', self.work), ('JOURNAL', self.work / 'transaction.json')):
            mock = patch.object(deploy, key, value)
            mock.start()
            self.addCleanup(mock.stop)

    def install(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return deploy.deploy(self.game, fixture=True)

    def rollback(self, journal):
        with contextlib.redirect_stdout(io.StringIO()):
            deploy.rollback(journal)

    def test_fresh_install_and_exact_rollback(self):
        journal = self.install()
        self.assertEqual(deploy.sha(deploy.target(self.game, 'vpk')), deploy.sha(deploy.VPK))
        self.assertEqual(deploy.sha(deploy.target(self.game, 'dll')), deploy.sha(deploy.DLL))
        self.assertEqual(deploy.addon_state(self.addonlist.read_bytes()), '1')
        self.rollback(journal)
        self.assertEqual(self.addonlist.read_bytes(), self.raw)
        self.assertFalse(deploy.target(self.game, 'vpk').exists())
        self.assertFalse(deploy.target(self.game, 'dll').exists())

    def test_existing_components_restored(self):
        deploy.target(self.game, 'vpk').write_bytes(b'previous CSP VPK fixture')
        deploy.target(self.game, 'dll').write_bytes(b'previous CSP DLL fixture')
        journal = self.install()
        self.rollback(journal)
        self.assertEqual(deploy.target(self.game, 'vpk').read_bytes(), b'previous CSP VPK fixture')
        self.assertEqual(deploy.target(self.game, 'dll').read_bytes(), b'previous CSP DLL fixture')

    def test_preserve_other_addonlist_edits(self):
        journal = self.install()
        raw = self.addonlist.read_bytes()
        self.addonlist.write_bytes(raw.replace(b'}', b'"new_user_addon.vpk" "0"\r\n}'))
        self.rollback(journal)
        self.assertIsNone(deploy.addon_state(self.addonlist.read_bytes()))
        self.assertIn(b'"new_user_addon.vpk" "0"', self.addonlist.read_bytes())

    def test_disabled_entry_restored(self):
        before = deploy.set_addon(self.raw, '0')
        self.addonlist.write_bytes(before)
        journal = self.install()
        self.rollback(journal)
        self.assertEqual(self.addonlist.read_bytes(), before)

    def test_rollback_rejects_external_component_changes_before_writing(self):
        journal = self.install()
        deploy.target(self.game, 'dll').write_bytes(b'user replaced DLL')
        with self.assertRaises(AssertionError):
            self.rollback(journal)
        self.assertEqual(deploy.sha(deploy.target(self.game, 'vpk')), deploy.sha(deploy.VPK))
        self.assertEqual(deploy.addon_state(self.addonlist.read_bytes()), '1')

    def test_rollback_preview_has_no_writes(self):
        journal = self.install()
        before = self.addonlist.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            deploy.rollback(journal, preview=True)
        self.assertEqual(self.addonlist.read_bytes(), before)
        self.assertTrue(deploy.target(self.game, 'dll').exists())

    def test_scan_finds_enabled_menu_override(self):
        path = self.game / 'left4dead2/addons/other.vpk'
        write(path, {'resource/ui/l4d360ui/multiplayer.res': b'fixture'})
        report = deploy.conflicts(self.game)
        self.assertEqual(len(report['collisions']), 1)
        self.assertEqual(report['collisions'][0]['path'], str(path))

    def test_scan_ignores_disabled_override(self):
        path = self.game / 'left4dead2/addons/other.vpk'
        write(path, {'resource/ui/l4d360ui/multiplayer.res': b'fixture'})
        self.addonlist.write_bytes(b'"AddonList" {"other.vpk" "0"}')
        self.assertEqual(deploy.conflicts(self.game)['collisions'], [])

    def test_entry_edit_preserves_encoding(self):
        for encoding in ('utf-8', 'utf-8-sig', 'gb18030'):
            raw = '"AddonList" {"普通.vpk" "1"}'.encode(encoding)
            added = deploy.set_addon(raw, '1')
            self.assertIn('普通.vpk', added.decode(encoding))
            self.assertEqual(deploy.addon_state(added), '1')

    def test_active_malformed_vpk_fails_closed(self):
        (self.game / 'left4dead2/addons/bad.vpk').write_bytes(b'NOT A VPK ARCHIVE')
        with self.assertRaises(AssertionError):
            deploy.conflicts(self.game)

    def test_zip_installer_is_reported_not_treated_as_native_vpk(self):
        path = self.game / 'left4dead2/addons/platform.vpk'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('setup.txt', 'fixture installer, not a native game archive')
        result = deploy.conflicts(self.game)
        self.assertEqual(result['collisions'], [])
        self.assertEqual(result['inspected'][0]['format'], 'ZIP_INSTALLER_NOT_NATIVE_VPK')


if __name__ == '__main__':
    unittest.main(verbosity=2)
