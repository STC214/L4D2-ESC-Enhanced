"""Exercise real deployment/rollback logic in isolated, non-game fixtures."""

import argparse
import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import c_session_release as release


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='c-session-deploy-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / 'game'
        self.work = self.root / 'reports/deploy'
        self.sources = {'vpk': self.root / 'new.vpk', 'helper': self.root / 'new.dll'}
        self.targets = dict(release.TARGETS)
        self.before = b'confirmed old C'
        for path in (self.game / 'bin/engine.dll', self.game / 'bin/left4neko.dll'):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture engine or loader')
        self.target('helper').parent.mkdir(parents=True, exist_ok=True)
        self.target('vpk').parent.mkdir(parents=True, exist_ok=True)
        self.target('vpk').write_bytes(self.before)
        self.sources['vpk'].write_bytes(b'new C')
        self.sources['helper'].write_bytes(b'new helper')
        build = self.root / 'reports/c_session_plugin_build.json'
        build.parent.mkdir(parents=True, exist_ok=True)
        build.write_text(json.dumps({'engine_profile_sha256': release.sha(self.game / 'bin/engine.dll')}), encoding='utf-8')
        for key, value in {'ROOT': self.root, 'GAME': self.game, 'WORK': self.work,
                           'JOURNAL': self.work / 'transaction.json', 'SOURCES': self.sources,
                           'BASE_HASH': release.sha(self.target('vpk')), 'TARGETS': self.targets}.items():
            item = patch.object(release, key, value)
            item.start()
            self.addCleanup(item.stop)
        for name in ('stopped', 'package'):
            item = patch.object(release, name)
            item.start()
            self.addCleanup(item.stop)
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def target(self, key):
        return self.game / self.targets[key]

    def journal(self):
        return json.loads(release.JOURNAL.read_text(encoding='utf-8'))

    def test_initial_install_verify_and_preview(self):
        release.deploy()
        release.verify_installed()
        before = {k: self.target(k).read_bytes() for k in self.targets}
        release.rollback_game()
        self.assertEqual(before, {k: self.target(k).read_bytes() for k in self.targets})

    def test_idempotent_deploy_preserves_journal_and_backup(self):
        release.deploy()
        journal = release.JOURNAL.read_bytes()
        release.deploy()
        self.assertEqual(release.JOURNAL.read_bytes(), journal)
        backup = self.root / self.journal()['files']['vpk']['backup']
        self.assertEqual(backup.read_bytes(), self.before)

    def test_upgrade_from_previous_record(self):
        release.deploy()
        self.sources['helper'].write_bytes(b'fixed helper v2')
        release.deploy()
        release.verify_installed()
        self.assertEqual(self.target('helper').read_bytes(), b'fixed helper v2')

    def test_upgrade_rollback_restores_previous_pair(self):
        release.deploy()
        old_pair = {k: self.target(k).read_bytes() for k in self.targets}
        self.sources['vpk'].write_bytes(b'new C v2')
        self.sources['helper'].write_bytes(b'new helper v2')
        release.deploy()
        release.rollback_game(True)
        self.assertEqual({k: self.target(k).read_bytes() for k in self.targets}, old_pair)

    def test_reinstall_after_rollback(self):
        release.deploy()
        release.rollback_game(True)
        self.assertEqual(self.target('vpk').read_bytes(), self.before)
        self.assertFalse(self.target('helper').exists())
        release.deploy()
        release.verify_installed()
        release.rollback_game(True)
        release.rollback_game(True)
        self.assertEqual(self.target('vpk').read_bytes(), self.before)

    def test_partial_copy_failure_keeps_active_files_recoverable(self):
        original = shutil.copyfile

        def broken_copy(src, dst, *args, **kwargs):
            if Path(src) == self.sources['helper']:
                Path(dst).write_bytes(b'partial')
                raise OSError('injected partial copy')
            return original(src, dst, *args, **kwargs)

        with patch.object(release.shutil, 'copyfile', side_effect=broken_copy):
            with self.assertRaises(OSError):
                release.deploy()
        release.rollback_game(True)
        self.assertEqual(self.target('vpk').read_bytes(), self.before)
        self.assertFalse(self.target('helper').exists())

    def test_all_targets_preflight_before_any_game_write(self):
        self.targets['helper'] = Path('missing/plugins/helper.dll')
        with self.assertRaises((AssertionError, OSError, ValueError)):
            release.deploy()
        self.assertEqual(self.target('vpk').read_bytes(), self.before)

    def test_external_edit_blocks_rollback_without_overwrite(self):
        release.deploy()
        self.target('helper').write_bytes(b'user edit')
        current = self.target('vpk').read_bytes()
        with self.assertRaises((AssertionError, ValueError)):
            release.rollback_game(True)
        self.assertEqual(self.target('helper').read_bytes(), b'user edit')
        self.assertEqual(self.target('vpk').read_bytes(), current)

    def test_external_edit_blocks_upgrade(self):
        release.deploy()
        self.target('vpk').write_bytes(b'user C')
        self.sources['helper'].write_bytes(b'new helper v2')
        with self.assertRaises((AssertionError, ValueError)):
            release.deploy()
        self.assertEqual(self.target('vpk').read_bytes(), b'user C')

    def test_legacy_journal_can_upgrade(self):
        release.deploy()
        journal = self.journal()
        journal.pop('generation')
        for entry in journal['files'].values():
            entry.pop('disabled_relative')
        release.save(release.JOURNAL, journal)
        self.sources['helper'].write_bytes(b'fixed legacy helper')
        release.deploy()
        release.verify_installed()
        archived = self.root / self.journal()['previous_transaction']
        self.assertEqual(json.loads(archived.read_text(encoding='utf-8')), journal)

    def test_partial_copy_failure_during_upgrade_can_rollback(self):
        release.deploy()
        old = {k: self.target(k).read_bytes() for k in self.targets}
        self.sources['vpk'].write_bytes(b'newer C')
        self.sources['helper'].write_bytes(b'newer helper')
        original = shutil.copyfile

        def fail(src, dst, *args, **kwargs):
            if Path(src) == self.sources['helper']:
                Path(dst).write_bytes(b'partial')
                raise OSError('injected upgrade copy failure')
            return original(src, dst, *args, **kwargs)

        with patch.object(release.shutil, 'copyfile', side_effect=fail):
            with self.assertRaises(OSError):
                release.deploy()
        self.assertEqual(self.target('helper').read_bytes(), old['helper'])
        release.rollback_game(True)
        self.assertEqual({k: self.target(k).read_bytes() for k in self.targets}, old)
        self.assertFalse(list(self.game.rglob('*.c-session.tmp')))

    def test_journal_replace_failure_does_not_change_game(self):
        original = release.os.replace

        def fail(src, dst):
            if Path(dst) == release.JOURNAL:
                raise OSError('injected journal commit failure')
            return original(src, dst)

        with patch.object(release.os, 'replace', side_effect=fail):
            with self.assertRaises(OSError):
                release.deploy()
        self.assertEqual(self.target('vpk').read_bytes(), self.before)
        self.assertFalse(self.target('helper').exists())
        self.assertFalse(release.JOURNAL.exists())

    def test_incomplete_journal_rejected_before_rollback(self):
        release.deploy()
        journal = self.journal()
        del journal['files']['helper']
        release.save(release.JOURNAL, journal)
        before = {k: self.target(k).read_bytes() for k in self.targets}
        with self.assertRaises(AssertionError):
            release.rollback_game(True)
        self.assertEqual({k: self.target(k).read_bytes() for k in self.targets}, before)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(DeploymentTests))
    print(output.getvalue(), end='')
    if args.report:
        release.save(args.report, {'command': [sys.executable, *sys.argv], 'scope': 'temporary fixture files only',
                                  'stdout': output.getvalue(), 'exit_status': int(not result.wasSuccessful()),
                                  'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors)})
    raise SystemExit(not result.wasSuccessful())


if __name__ == '__main__':
    main()
