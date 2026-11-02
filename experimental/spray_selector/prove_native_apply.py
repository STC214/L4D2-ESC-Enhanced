"""Replay the installed GameUI's spray selection code against numbered fixtures.

The actual native handler executes in Unicorn. Engine CVar and rendering services
are controlled mocks: this proves command/path dispatch, NOT a live-game spray.
"""

import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from trace_flashlight_native import PE
from catalog import fixtures
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESP

GAME = Path(r'E:\SteamLibrary\steamapps\common\Left 4 Dead 2')
OUT = ROOT / 'reports/spray_selector'
PIN = '321ec9b5865582330af61e81eb347da31cc213cc6c95b80d6d98170b8a5fbb40'


def replay(pe, catalog, identifier):
    page_number, slot = catalog.selection(identifier)
    page = catalog.page(page_number)
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    machine.mem_map(pe.base, 0x300000)
    for _, address, size, offset in pe.sections:
        machine.mem_write(address, pe.raw[offset:offset + size])
    data, stack, stop = 0x20000000, 0x21000000, 0x22000000
    for base in (data, stack, stop):
        machine.mem_map(base, 0x10000)
    obj, command, var, table = data, data + 0x2000, data + 0x3000, data + 0x4000
    setter = stop + 0x100
    result = dict(identifier=identifier, page=page_number, slot=slot, page_size=len(page),
                  setters=[], previews=[], mocked_calls=[])

    def word(address, value):
        machine.mem_write(address, struct.pack('<I', value))

    def get(address):
        return struct.unpack('<I', machine.mem_read(address, 4))[0]

    def string(address):
        value = bytearray()
        for at in range(1024):
            byte = machine.mem_read(address + at, 1)[0]
            if not byte:
                return bytes(value).decode('ascii')
            value.append(byte)
        raise AssertionError('Unterminated string')

    def ret(clean=0, value=0):
        esp = machine.reg_read(UC_X86_REG_ESP)
        target = get(esp)
        machine.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
        machine.reg_write(UC_X86_REG_ESP, esp + 4 + clean)
        machine.reg_write(UC_X86_REG_EIP, target)

    def hook(uc, address, size, context):
        esp = uc.reg_read(UC_X86_REG_ESP)
        if address == 0x100befe0:  # strcmp, cdecl
            left, right = string(get(esp + 4)), string(get(esp + 8))
            ret(value=(left > right) - (left < right))
        elif address == 0x100bf130:  # case-insensitive strstr, cdecl
            left, right = string(get(esp + 4)), string(get(esp + 8))
            offset = left.lower().find(right.lower())
            ret(value=get(esp + 4) + offset if offset >= 0 else 0)
        elif address == 0x10010f80:  # native command-prefix helper
            ret(value=int(string(get(esp + 4)).startswith(string(get(esp + 8)))))
        elif address == 0x100beeb0:  # strlen
            ret(value=len(string(get(esp + 4))))
        elif address == 0x100bf4c0:  # bounded formatting, cdecl
            dest, capacity, fmt = get(esp + 4), get(esp + 8), string(get(esp + 12))
            assert fmt == 'materials/vgui/logos/%s%s.vtf', fmt
            output = fmt % (string(get(esp + 16)), string(get(esp + 20)))
            assert len(output) + 1 <= capacity
            uc.mem_write(dest, output.encode() + b'\0')
            ret(value=len(output))
        elif address == 0x10087cd0:  # native ConVarRef construction
            name = string(get(esp + 4))
            assert name == 'cl_logofile', name
            reference = uc.reg_read(UC_X86_REG_ECX)
            for index in range(4):
                word(reference + index * 8, var)
            result['mocked_calls'].append('ConVarRef(cl_logofile)')
            ret(clean=8)
        elif address == 0x10087a30:  # active local player slot
            ret(value=0)
        elif address == setter:
            assert uc.reg_read(UC_X86_REG_ECX) == var
            result['setters'].append(string(get(esp + 4)))
            ret(clean=4)
        elif address == 0x1007cf40:  # VGUI preview material update
            result['previews'].append(dict(name=string(get(esp + 4)), suffix=string(get(esp + 12))))
            ret()
        elif address == 0x1013a861:  # security-cookie check
            ret()

    machine.hook_add(UC_HOOK_CODE, hook)
    word(obj + 0x2c8, len(page))
    for index, entry in enumerate(page):
        assert len(entry.native_name) < 0x104
        machine.mem_write(obj + 0x2cc + index * 0x105, entry.native_name.encode() + b'\0')
        machine.mem_write(obj + 0x3d0 + index * 0x105, b'\0')
    word(var, table)
    word(table + 0xc, setter)
    command_text = '_spraypaint' + chr(0x30 + slot)
    machine.mem_write(command, command_text.encode() + b'\0')
    word(stack + 0x8000, stop)
    word(stack + 0x8004, command)
    machine.reg_write(UC_X86_REG_ESP, stack + 0x8000)
    machine.reg_write(UC_X86_REG_ECX, obj)
    machine.emu_start(0x1006a620, stop, count=10000)
    assert machine.reg_read(UC_X86_REG_EIP) == stop
    expected = catalog.by_id[identifier]
    assert result['setters'] == [expected.texture], result
    assert result['previews'] == [dict(name=expected.native_name, suffix='')], result
    assert machine.reg_read(UC_X86_REG_ESP) == stack + 0x8008
    result['native_command'] = command_text
    return result


def main():
    pe = PE(GAME / 'bin/gameui.dll')
    assert hashlib.sha256(pe.raw).hexdigest() == PIN, 'Re-establish native addresses after game update'
    catalog = fixtures()
    preview_format = pe.raw[pe.offset(0x10184230):].split(b'\0', 1)[0].decode()
    assert preview_format == 'logos/UI/%s', 'Recheck ImagePanel material-prefix contract'
    cases = [replay(pe, catalog, entry.identifier) for entry in catalog.entries]
    assert len(cases) == 40 and cases[16]['setters'][0].endswith('test_017.vtf')
    report = dict(status='PASS', scope='Native x86 handler replay with CVar/preview mocks; NOT live UI, rendering, network upload or persistence',
                  target=str(pe.path), sha256=PIN, native_handler='0x1006a620',
                  native_handler_bytes_sha256=hashlib.sha256(pe.raw[pe.offset(0x1006a620):pe.offset(0x1006ae30)]).hexdigest(),
                  page_size=12, catalog_entries=40, cases=cases, native_preview_format=preview_format,
                  decision='Page an independent catalog into at most 12 native slots; do not enlarge the native 16-slot array')
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / 'native_apply.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert json.loads(output.read_text(encoding='utf-8')) == report
    print('PASS installed native handler: 40/40 numbered entries map to the expected cl_logofile setter and preview')
    print('PASS global entries 17 and 40 use page-local slots; no game DLL patched; live integration pending')


if __name__ == '__main__':
    main()
