"""Read-only PE icon resource check against the generated multi-resolution ICO."""

import argparse
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]


def verify(exe, ico):
    raw, original = exe.read_bytes(), ico.read_bytes()
    word = lambda at: struct.unpack_from('<H', raw, at)[0]
    dword = lambda at: struct.unpack_from('<I', raw, at)[0]
    pe = dword(60)
    assert raw[pe:pe + 4] == b'PE\0\0' and word(pe + 4) == 0x8664
    optional = pe + 24
    assert word(optional) == 0x20b
    sections = optional + word(pe + 20)

    def offset(rva):
        for at in range(sections, sections + word(pe + 6) * 40, 40):
            virtual_size, start, raw_size, pointer = struct.unpack_from('<4I', raw, at + 8)
            if start <= rva < start + max(virtual_size, raw_size):
                assert rva - start < raw_size
                return pointer + rva - start
        raise AssertionError('RVA outside PE sections')

    resource_rva = dword(optional + 112 + 2 * 8)
    assert resource_rva
    base = offset(resource_rva)

    def entries(relative):
        at = base + relative
        count = word(at + 12) + word(at + 14)
        return dict(struct.unpack_from('<II', raw, at + 16 + i * 8) for i in range(count))

    def payload(kind, identifier):
        directory = entries(0)[kind]
        assert directory & 0x80000000
        language_dir = entries(directory & 0x7fffffff)[identifier]
        assert language_dir & 0x80000000
        leaves = entries(language_dir & 0x7fffffff)
        assert len(leaves) == 1
        entry = next(iter(leaves.values()))
        assert not entry & 0x80000000
        rva, size = struct.unpack_from('<II', raw, base + entry)
        start = offset(rva)
        data = raw[start:start + size]
        assert len(data) == size
        return data

    group = payload(14, 101)
    reserved, kind, count = struct.unpack_from('<HHH', group)
    assert (reserved, kind, count) == (0, 1, 7)
    assert struct.unpack_from('<HHH', original) == (0, 1, 7)
    sizes = []
    for i in range(count):
        width, height, _, _, planes, bits, length, identifier = struct.unpack_from('<BBBBHHIH', group, 6 + i * 14)
        source_width, source_height, _, _, source_planes, source_bits, source_length, start = struct.unpack_from('<BBBBHHII', original, 6 + i * 16)
        assert (width, height, planes, bits, length) == (source_width, source_height, source_planes, source_bits, source_length)
        data = payload(3, identifier)
        assert data == original[start:start + length] and data.startswith(b'\x89PNG\r\n\x1a\n')
        sizes.append(width or 256)
    assert sizes == [16, 24, 32, 48, 64, 128, 256]
    return dict(status='PASS', group_id=101, sizes=sizes,
                exe_sha256=hashlib.sha256(raw).hexdigest(), ico_sha256=hashlib.sha256(original).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, default=ROOT / 'dist/spray_importer_go/CSP_Spray_Manager.exe')
    parser.add_argument('--ico', type=Path, default=ROOT / 'native/spray_importer/assets/app.ico')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = verify(args.exe, args.ico)
    data = json.dumps(report, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(data, encoding='utf-8')
    print(data)


if __name__ == '__main__':
    main()
