"""Inspect local cvar constructors and connection event definitions read-only."""

from collections import deque
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from release_paths import ROOT


GAME = Path(r"E:\SteamLibrary\steamapps\common\Left 4 Dead 2")
OUT = ROOT / "reports/c_session_inputs"


def selected_members(path):
    with path.open('rb') as stream:
        sig, version, size = struct.unpack('<III', stream.read(12))
        assert sig == 0x55AA1234 and version in (1, 2)
        header = 12 if version == 1 else 28
        stream.seek(header)
        tree = stream.read(size)
    at = 0
    def string():
        nonlocal at
        end = tree.index(b'\0', at)
        result = tree[at:end].decode('utf-8', errors='surrogateescape')
        at = end + 1
        return result
    result = {}
    while ext := string():
        while folder := string():
            while name := string():
                crc, preload, archive, offset, length, term = struct.unpack_from('<IHHIIH', tree, at)
                at += 18
                content = tree[at:at + preload]
                at += preload
                if ext == 'res' and name.lower() in ('gameevents', 'serverevents', 'modevents', 'engineevents'):
                    if length:
                        source = path if archive == 0x7fff else path.with_name(path.name.replace('_dir.vpk', f'_{archive:03}.vpk'))
                        with source.open('rb') as stream:
                            stream.seek(header + size + offset if archive == 0x7fff else offset)
                            content += stream.read(length)
                    assert zlib.crc32(content) == crc
                    result[(folder + '/' if folder != ' ' else '') + name + '.' + ext] = content
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'native': [], 'events': []}
    for relative, needles in (
        ('left4dead2/bin/client.dll', ['r_flashlightfov', 'r_farz']),
        ('bin/engine.dll', ['VEngineClient013', 'GAMEEVENTSMANAGER002', 'client_beginconnect', 'client_connected', 'client_disconnect']),
    ):
        path = GAME / relative
        raw = path.read_bytes()
        u32 = lambda at: struct.unpack_from('<I', raw, at)[0]
        pe = u32(0x3c)
        opt = pe + 24
        base = u32(opt + 28)
        table = opt + struct.unpack_from('<H', raw, pe + 20)[0]
        sections = []
        for i in range(struct.unpack_from('<H', raw, pe + 6)[0]):
            at = table + i * 40
            name = raw[at:at + 8].split(b'\0')[0].decode()
            vs, rva, size, offset = struct.unpack_from('<IIII', raw, at + 8)
            sections.append((name, base + rva, size, offset))
        strings = {}
        for needle in needles:
            offset = raw.find(needle.encode() + b'\0')
            while offset >= 0:
                for _, va, size, start in sections:
                    if start <= offset < start + size:
                        strings[va + offset - start] = {'text': needle, 'va': hex(va + offset - start), 'contexts': []}
                offset = raw.find(needle.encode() + b'\0', offset + len(needle) + 1)
        engine = Cs(CS_ARCH_X86, CS_MODE_32)
        engine.skipdata = True
        for name, va, size, offset in sections:
            if name != '.text':
                continue
            previous, pending = deque(maxlen=16), []
            for address, _, mnemonic, operands in engine.disasm_lite(raw[offset:offset + size], va):
                row = f'{address:08x}: {mnemonic} {operands}'
                for context, left in list(pending):
                    context.append(row)
                    pending.remove((context, left))
                    if left > 1:
                        pending.append((context, left - 1))
                for match in re.findall(r'0x[0-9a-f]+', operands):
                    key = int(match, 16)
                    if key in strings:
                        context = list(previous) + [row]
                        strings[key]['contexts'].append(context)
                        pending.append((context, 20))
                previous.append(row)
        item = {'path': relative, 'sha256': hashlib.sha256(raw).hexdigest(), 'strings': list(strings.values())}
        report['native'].append(item)
        listing = '\n\n'.join(s['text'] + ' ' + s['va'] + '\n' + '\n'.join('\n'.join(c) for c in s['contexts']) for s in strings.values())
        (OUT / (path.stem + '_refs.txt')).write_text(listing, encoding='utf-8')
        print(relative, item['sha256'])
    for directory in ('update', 'left4dead2_dlc3', 'left4dead2_dlc2', 'left4dead2_dlc1', 'left4dead2', 'hl2'):
        pak = GAME / directory / 'pak01_dir.vpk'
        if pak.is_file():
            for name, content in selected_members(pak).items():
                dest = OUT / directory / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
                report['events'].append({'pak': str(pak), 'member': name, 'output': str(dest.relative_to(ROOT))})
                print('EVENT_RESOURCE', directory, name)
    (OUT / 'inspection.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('REPORT ' + str(OUT))


if __name__ == '__main__':
    main()
