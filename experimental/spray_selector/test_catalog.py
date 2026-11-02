"""Paging tests use self-authored numbered fixtures only."""

from dataclasses import replace
import unittest

from catalog import Catalog, fixtures


class CatalogTests(unittest.TestCase):
    def test_40_entries_four_pages(self):
        catalog = fixtures()
        self.assertEqual(catalog.pages, 4)
        self.assertEqual([len(catalog.page(i)) for i in range(4)], [12, 12, 12, 4])
        self.assertEqual(tuple(item for i in range(4) for item in catalog.page(i)), catalog.entries)

    def test_boundaries_including_beyond_16(self):
        catalog = fixtures()
        for number in (1, 12, 13, 16, 17, 24, 25, 36, 37, 40):
            with self.subTest(number=number):
                page, slot = catalog.selection(f'test_{number:03}')
                self.assertLess(slot, 12)
                self.assertEqual(catalog.page(page)[slot].texture,
                                 f'materials/vgui/logos/csp_test/test_{number:03}.vtf')

    def test_native_relative_name(self):
        self.assertEqual(fixtures().entries[16].native_name, 'csp_test/test_017')

    def test_pages_do_not_apply_or_mutate_selection(self):
        catalog = fixtures()
        before = catalog.entries
        for number in (3, 0, 1, 1, 2, 0):
            catalog.page(number)
        self.assertEqual(catalog.entries, before)
        self.assertEqual(catalog.selection('test_017'), (1, 4))

    def test_duplicate_ids_rejected(self):
        item = fixtures().entries[0]
        with self.assertRaises(ValueError):
            Catalog([item, replace(item, texture=item.texture.replace('001', '002'))])

    def test_duplicate_paths_rejected(self):
        item = fixtures().entries[0]
        with self.assertRaises(ValueError):
            Catalog([item, replace(item, identifier='other')])

    def test_bad_paths_rejected(self):
        item = fixtures().entries[0]
        for path in ('../test.vtf', item.texture.upper(), item.texture + ';quit',
                     item.texture.replace('test_001', '../test_001'), 'C:/test.vtf',
                     'materials/vgui/logos/test.vtf', item.texture + '\n'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                Catalog([replace(item, texture=path)])

    def test_bad_ids_and_titles_rejected(self):
        item = fixtures().entries[0]
        for entry in (replace(item, identifier=''), replace(item, identifier='x;quit'),
                      replace(item, title=''), replace(item, title='test\nquit')):
            with self.assertRaises(ValueError):
                Catalog([entry])

    def test_invalid_page_or_id_rejected(self):
        catalog = fixtures()
        for page in (-1, 4, 100, 1.0, True):
            with self.assertRaises(ValueError):
                catalog.page(page)
        with self.assertRaises(ValueError):
            catalog.selection('missing')

    def test_invalid_catalog_size_rejected(self):
        with self.assertRaises(ValueError):
            Catalog([])
        for count in (0, -1, True, 10001):
            with self.assertRaises(ValueError):
                fixtures(count)

    def test_no_catalog_hard_limit_at_16(self):
        self.assertEqual(len(fixtures(1000).entries), 1000)


if __name__ == '__main__':
    unittest.main(verbosity=2)
