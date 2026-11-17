"""Offline checks: package integrity, remote digest guards and publish allowlist."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import release_all_v140 as release


class ReleaseTests(unittest.TestCase):
    def test_numbered_baseline_pin_rejects_custom_or_matching_replacements(self):
        original = release.ROOT / 'native/spray_importer/assets/selector.vpk'
        release.verify_numbered_baseline(original, release.SELECTOR / 'CSP_Numbered_Selector_TEST.vpk')
        with tempfile.TemporaryDirectory(dir=release.ROOT / 'reports') as folder:
            custom = Path(folder) / 'custom.vpk'
            custom.write_bytes(b'custom game spray; never a release baseline')
            for a, b in ((original, custom), (custom, original), (custom, custom)):
                with self.assertRaises(AssertionError):
                    release.verify_numbered_baseline(a, b)

    def test_portable_launchers_use_only_relative_packaged_manager(self):
        deploy = (release.ROOT / 'portable/Deploy.cmd').read_text(encoding='utf-8')
        manager = (release.ROOT / 'portable/Spray_Manager.cmd').read_text(encoding='utf-8')
        self.assertIn('"%~dp0manager\\CSP_Spray_Manager.exe" --portable-install', deploy)
        self.assertIn('"%~dp0manager\\CSP_Spray_Manager.exe"', manager)
        self.assertNotIn('E:\\', deploy)
        self.assertNotIn('D:\\', deploy)
        self.assertNotIn('python', deploy.lower())

    def test_embedded_selector_matches_standalone_and_build_pin(self):
        with tempfile.TemporaryDirectory(dir=release.ROOT / 'reports') as folder:
            embedded, standalone = Path(folder) / 'embedded.dll', Path(folder) / 'standalone.dll'
            embedded.write_bytes(b'own bridge fixture')
            standalone.write_bytes(embedded.read_bytes())
            digest = release.sha(embedded)
            release.verify_selector_bridge(embedded, standalone, digest.upper())
            with self.assertRaises(AssertionError):
                release.verify_selector_bridge(embedded, standalone, '0' * 64)
            standalone.write_bytes(b'different bridge')
            with self.assertRaises(AssertionError):
                release.verify_selector_bridge(embedded, standalone, digest)

    def test_manager_guide_is_current_self_contained_manual(self):
        guide = release.manager_guide().decode('utf-8')
        self.assertIn('# CSP 喷漆处理工具使用说明', guide)
        self.assertIn('settings.json', guide)
        self.assertIn('2～256', guide)
        self.assertNotIn('](喷漆导入工具.md)', guide)
        self.assertNotIn('](便携整合包使用说明.md)', guide)
        self.assertIn('/blob/' + release.TAG + '/docs/', guide)

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
