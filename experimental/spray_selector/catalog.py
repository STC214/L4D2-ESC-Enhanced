"""Independent spray catalog and 12-slot paging; no game filesystem access."""

from dataclasses import dataclass
import re

PAGE_SIZE = 12
PREFIX = "materials/vgui/logos/csp_test/"
PATH = re.compile(r"materials/vgui/logos/csp_test/[a-z0-9_]+\.vtf\Z")


@dataclass(frozen=True)
class Entry:
    identifier: str
    title: str
    texture: str

    @property
    def native_name(self):
        """Native _spraypaint handler prepends materials/vgui/logos/ and .vtf."""
        return self.texture.removeprefix("materials/vgui/logos/").removesuffix(".vtf")


class Catalog:
    def __init__(self, entries):
        self.entries = tuple(entries)
        if not self.entries:
            raise ValueError("Empty catalog")
        ids, paths = set(), set()
        for entry in self.entries:
            if not re.fullmatch(r"[a-z0-9_]{1,48}", entry.identifier):
                raise ValueError("Invalid entry ID")
            if not entry.title or any(ord(c) < 32 for c in entry.title):
                raise ValueError("Invalid title")
            if not PATH.fullmatch(entry.texture) or len(entry.native_name.encode()) > 240:
                raise ValueError("Noncanonical or out-of-namespace texture")
            if entry.identifier in ids or entry.texture.casefold() in paths:
                raise ValueError("Duplicate entry ID or texture path")
            ids.add(entry.identifier)
            paths.add(entry.texture.casefold())
        self.by_id = {entry.identifier: entry for entry in self.entries}

    @property
    def pages(self):
        return (len(self.entries) + PAGE_SIZE - 1) // PAGE_SIZE

    def page(self, number):
        if type(number) is not int or not 0 <= number < self.pages:
            raise ValueError("Invalid page")
        return self.entries[number * PAGE_SIZE:(number + 1) * PAGE_SIZE]

    def selection(self, identifier):
        """Return page/slot, not a global index into the native 16-slot array."""
        if identifier not in self.by_id:
            raise ValueError("Unknown entry ID")
        index = self.entries.index(self.by_id[identifier])
        return index // PAGE_SIZE, index % PAGE_SIZE


def fixtures(count=40):
    if type(count) is not int or not 1 <= count <= 10000:
        raise ValueError("Invalid fixture count")
    return Catalog(Entry(f"test_{i:03}", f"TEST {i:03}", PREFIX + f"test_{i:03}.vtf")
                   for i in range(1, count + 1))
