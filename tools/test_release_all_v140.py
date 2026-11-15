"""Offline checks: package integrity, remote digest guards and publish allowlist."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import release_all_v140 as release


class ReleaseTests(unittest.TestCase):
    def test_go_top_level_counts_ignore_subtests_and_fuzz(self):
        run = ('--- PASS: TestOne (0.00s)\n'
               '    --- PASS: TestOne/child (0.00s)\n'
               '--- PASS: TestTwo (0.00s)\n'
               '--- PASS: FuzzParser (0.00s)\n'
               '    --- PASS: FuzzParser/seed#0 (0.00s)\n')
        release.verify_go_test_output(run * 2 + 'PASS\n', 2)
        for bad in (run + 'PASS\n', run * 3 + 'PASS\n',
                    run * 2 + '--- SKIP: TestMissing (0.00s)\nPASS\n',
                    run * 2 + '--- FAIL: TestBad (0.00s)\n', run * 2):
            with self.assertRaises(AssertionError):
                release.verify_go_test_output(bad, 2)

    def test_archive_manifest_crc_and_determinism(self):
        with tempfile.TemporaryDirectory(dir=release.ROOT / 'reports') as folder:
            a, b = Path(folder) / 'a.zip', Path(folder) / 'b.zip'
            payload = {'game/own.txt': b'own fixture', '使用说明.md': '测试'.encode()}
            release.archive(a, payload)
            release.archive(b, payload)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            with zipfile.ZipFile(a) as stream:
                self.assertIsNone(stream.testzip())
                manifest = json.loads(stream.read('manifest.json'))
                self.assertEqual(manifest['files'], {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()})

    def test_archive_rejects_escape(self):
        with tempfile.TemporaryDirectory(dir=release.ROOT / 'reports') as folder:
            with self.assertRaises(AssertionError):
                release.archive(Path(folder) / 'bad.zip', {'../user.txt': b'bad'})

    def test_remote_asset_digest_size_and_set(self):
        original = release.OUT
        try:
            with tempfile.TemporaryDirectory(dir=release.ROOT / 'reports') as folder:
                release.OUT = Path(folder)
                path = release.OUT / 'tool.exe'
                path.write_bytes(b'fixture not an executable')
                digest = release.sha(path)
                manifest = {'files': {'tool.exe': digest}}
                asset = dict(name='tool.exe', state='uploaded', size=path.stat().st_size, digest='sha256:' + digest)
                release.verify_remote({'assets': [asset]}, manifest)
                for row in ({**asset, 'digest': 'sha256:' + '0' * 64}, {**asset, 'size': 0}):
                    with self.assertRaises(AssertionError):
                        release.verify_remote({'assets': [row]}, manifest)
                with self.assertRaises(AssertionError):
                    release.verify_remote({'assets': []}, manifest)
        finally:
            release.OUT = original

    def test_publish_sources_exclude_user_data_and_build_cache(self):
        sources = release.sources()
        self.assertTrue(all(not name.startswith(('喷漆/', 'reports/', 'dist/')) for name in sources))
        self.assertIn('native/spray_importer/assets/selector.vpk', sources)
        self.assertIn('experimental/spray_selector/native/plugin.cpp', sources)


if __name__ == '__main__':
    unittest.main(verbosity=2)
