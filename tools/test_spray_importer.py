"""Own synthetic images only; game deployment is tested against a workspace fixture."""

import json
from pathlib import Path
import struct
import tempfile
import unittest

from PIL import Image
import spray_importer as tool
from vpk import read


class ImporterTests(unittest.TestCase):
    def setUp(self):
        parent = tool.ROOT / 'reports/spray_importer/tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temporary.name)
        self.home = self.root / 'home'
        self.image = self.root / 'own.png'
        Image.new('RGBA', (120, 60), (230, 50, 10, 128)).save(self.image)

    def tearDown(self):
        self.temporary.cleanup()

    def make_build(self):
        tool.import_image(self.image, 17, self.home)
        return tool.build(self.home)

    def game(self, folder):
        game = self.root / 'game'
        (game / 'left4dead2').mkdir(parents=True)
        (game / 'left4dead2/gameinfo.txt').write_text(
            '"GameInfo" { "FileSystem" { "SearchPaths" { "Game" "update" } } }', encoding='utf-8')
        files = read(tool.BASE)
        entries = {'left4dead2/addons/' + tool.VPK_NAME: tool.BASE.read_bytes()}
        entries.update({'update/' + name: data for name, data in files.items() if name.startswith(tool.PREFIX)})
        for name, data in entries.items():
            path = game / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return game, entries

    def test_slot_bounds(self):
        for value in (0, 41, True, '1', None):
            with self.assertRaises(ValueError):
                tool.slot_number(value)

    def test_aspect_alpha_and_roundtrip(self):
        image = tool.load_image(self.image)
        self.assertEqual(image.size, (256, 256))
        self.assertEqual(image.getpixel((0, 0))[3], 0)
        # Pillow resamples RGBA through premultiplied alpha (one-unit RGB rounding).
        self.assertTrue(all(abs(a - b) <= 1 for a, b in
                            zip(image.getpixel((128, 128)), (230, 50, 10, 128))))
        raw = tool.encode_vtf(image)
        self.assertEqual(len(raw), 262224)
        self.assertEqual(tool.decode_vtf(raw).tobytes(), image.tobytes())

    def test_common_image_formats(self):
        for extension in ('jpg', 'bmp', 'tga', 'webp'):
            path = self.root / ('own.' + extension)
            Image.new('RGB', (100, 100), 'red').save(path)
            self.assertEqual(tool.load_image(path).size, (256, 256))

    def test_vtf_input(self):
        path = self.root / 'own.vtf'
        path.write_bytes(tool.encode_vtf(tool.load_image(self.image)))
        self.assertEqual(tool.load_image(path).size, (256, 256))

    def test_dxt_formats(self):
        for fmt, alpha in ((13, b''), (14, b'\xff' * 8), (15, b'\xff\0' + b'\0' * 6)):
            header = bytearray(tool.encode_vtf(Image.new('RGBA', (256, 256)))[:80])
            struct.pack_into('<HH', header, 16, 4, 4)
            struct.pack_into('<I', header, 52, fmt)
            image = tool.decode_vtf(bytes(header) + alpha + struct.pack('<HHI', 0xf800, 0, 0))
            self.assertEqual(image.getpixel((0, 0)), (255, 0, 0, 255))

    def test_resource_table(self):
        raw = tool.encode_vtf(tool.load_image(self.image))
        header = bytearray(raw[:80] + b'\0' * 8)
        struct.pack_into('<II', header, 8, 3, 88)
        struct.pack_into('<I', header, 68, 1)
        header[80:83] = b'\x30\0\0'
        struct.pack_into('<I', header, 84, 88)
        self.assertEqual(tool.decode_vtf(bytes(header) + raw[80:]).size, (256, 256))

    def test_vtf_rejects_bad_headers(self):
        raw = tool.encode_vtf(tool.load_image(self.image))
        cases = [b'bad', raw[:100]]
        for offset, value, fmt in ((24, 2, '<H'), (20, 0x4000, '<I'), (52, 999, '<I')):
            broken = bytearray(raw)
            struct.pack_into(fmt, broken, offset, value)
            cases.append(bytes(broken))
        for case in cases:
            with self.assertRaises(ValueError):
                tool.decode_vtf(case)

    def test_import_retains_old_generation(self):
        before = tool.import_image(self.image, 17, self.home)
        after = tool.import_image(self.image, 17, self.home)
        self.assertNotEqual(before, after)
        self.assertTrue(before.exists())

    def test_build_only_replaces_selected_texture(self):
        folder = self.make_build()
        original, modified = read(tool.BASE), read(folder / tool.VPK_NAME)
        self.assertEqual([name for name in original if original[name] != modified[name]],
                         [tool.PREFIX + 'test_017.vtf'])
        self.assertEqual((folder / 'mod' / (tool.PREFIX + 'test_017.vtf')).read_bytes(),
                         modified[tool.PREFIX + 'test_017.vtf'])
        self.assertEqual(original['materials/vgui/logos/ui/csp_test/test_017.vmt'],
                         modified['materials/vgui/logos/ui/csp_test/test_017.vmt'])

    def test_incremental_slots(self):
        tool.import_image(self.image, 1, self.home)
        tool.import_image(self.image, 40, self.home)
        folder = tool.build(self.home)
        self.assertEqual(set(json.loads((folder / 'manifest.json').read_text())['slots']), {'001', '040'})

    def test_tampered_import_rejected(self):
        self.make_build()
        row = json.loads((self.home / 'slots.json').read_text())['017']
        (self.home / row['texture']).write_bytes(b'changed')
        with self.assertRaises(AssertionError):
            tool.build(self.home)

    def test_real_file_deploy_and_rollback(self):
        folder = self.make_build()
        game, before = self.game(folder)
        transaction = tool.deploy(folder, self.home, game, fixture=True)
        path = game / ('update/' + tool.PREFIX + 'test_017.vtf')
        self.assertNotEqual(path.read_bytes(), before['update/' + tool.PREFIX + 'test_017.vtf'])
        tool.rollback(transaction, game, fixture=True)
        for name, data in before.items():
            self.assertEqual((game / name).read_bytes(), data)

    def test_rollback_preserves_external_changes(self):
        folder = self.make_build()
        game, before = self.game(folder)
        transaction = tool.deploy(folder, self.home, game, fixture=True)
        path = game / ('update/' + tool.PREFIX + 'test_040.vtf')
        path.write_bytes(b'external change')
        vpk_before = (game / ('left4dead2/addons/' + tool.VPK_NAME)).read_bytes()
        with self.assertRaises(AssertionError):
            tool.rollback(transaction, game, fixture=True)
        self.assertEqual(path.read_bytes(), b'external change')
        self.assertEqual((game / ('left4dead2/addons/' + tool.VPK_NAME)).read_bytes(), vpk_before)

    def test_tampered_build_rejected_before_writes(self):
        folder = self.make_build()
        game, before = self.game(folder)
        (folder / 'mod' / (tool.PREFIX + 'test_017.vtf')).write_bytes(b'tamper')
        with self.assertRaises(AssertionError):
            tool.deploy(folder, self.home, game, fixture=True)
        for name, data in before.items():
            self.assertEqual((game / name).read_bytes(), data)

    def test_stale_build_rejected_before_writes(self):
        folder = self.make_build()
        game, before = self.game(folder)
        tool.import_image(self.image, 18, self.home)
        with self.assertRaises(AssertionError):
            tool.deploy(folder, self.home, game, fixture=True)
        for name, data in before.items():
            self.assertEqual((game / name).read_bytes(), data)


if __name__ == '__main__':
    unittest.main(verbosity=2)
