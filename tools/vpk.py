"""Read and write single-file Valve VPK archives with CRC verification."""

import argparse
import struct
import zlib
from pathlib import Path


def read(path):
    raw = Path(path).read_bytes()
    signature, version, tree_size = struct.unpack_from("<III", raw)
    assert signature == 0x55AA1234 and version in (1, 2)
    header = 12 if version == 1 else 28
    cursor = header
    end = header + tree_size
    files = {}

    def string():
        nonlocal cursor
        stop = raw.index(b"\0", cursor, end)
        value = raw[cursor:stop].decode("utf-8")
        cursor = stop + 1
        return value

    while extension := string():
        while folder := string():
            while name := string():
                crc, preload, archive, offset, size, terminator = struct.unpack_from(
                    "<IHHIIH", raw, cursor
                )
                cursor += 18
                assert terminator == 0xFFFF
                content = raw[cursor : cursor + preload]
                cursor += preload
                if size:
                    assert archive == 0x7FFF, "External archive not supported"
                    start = end + offset
                    content += raw[start : start + size]
                assert len(content) == preload + size
                assert zlib.crc32(content) == crc, name
                filename = name + ("." + extension if extension != " " else "")
                key = filename if folder == " " else folder + "/" + filename
                assert key not in files
                files[key] = content
    assert cursor == end
    return files


def write(path, files):
    groups = {}
    for key, content in sorted(files.items()):
        p = Path(key)
        extension = p.suffix[1:] or " "
        folder = p.parent.as_posix()
        folder = " " if folder == "." else folder
        name = p.stem if p.suffix else p.name
        groups.setdefault(extension, {}).setdefault(folder, {})[name] = content
    tree = bytearray()
    data = bytearray()
    for extension, folders in groups.items():
        tree.extend(extension.encode() + b"\0")
        for folder, names in folders.items():
            tree.extend(folder.encode() + b"\0")
            for name, content in names.items():
                tree.extend(name.encode() + b"\0")
                tree.extend(
                    struct.pack(
                        "<IHHIIH", zlib.crc32(content), 0, 0x7FFF,
                        len(data), len(content), 0xFFFF,
                    )
                )
                data.extend(content)
            tree.extend(b"\0")
        tree.extend(b"\0")
    tree.extend(b"\0")
    Path(path).write_bytes(struct.pack("<III", 0x55AA1234, 1, len(tree)) + tree + data)
    assert read(path) == files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--extract", type=Path)
    args = parser.parse_args()
    for name, content in read(args.archive).items():
        print(f"{len(content):8} {name}")
        if args.extract:
            target = (args.extract / name).resolve()
            assert target.is_relative_to(args.extract.resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)


if __name__ == "__main__":
    main()
