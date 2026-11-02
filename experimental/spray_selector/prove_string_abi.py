"""Replay actual engine IConVar thunks: slot 2 is float, slot 3 is string."""

import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from trace_flashlight_native import PE
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP


def replay(pe, entry, kind):
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    end = max(address + size for _, address, size, _ in pe.sections)
    machine.mem_map(pe.base, (end - pe.base + 0xfff) & ~0xfff)
    for _, address, size, offset in pe.sections:
        machine.mem_write(address, pe.raw[offset:offset + size])
    data, stack, stop = 0x20000000, 0x21000000, 0x22000000
    for address in (data, stack, stop):
        machine.mem_map(address, 0x10000)
    obj, table, argument = data, data + 0x1000, data + 0x2000
    path = 'materials/vgui/logos/csp_test/test_017.vtf'

    def word(at, value):
        machine.mem_write(at, struct.pack('<I', value))

    def get(at):
        return struct.unpack('<I', machine.mem_read(at, 4))[0]

    result = dict(entry=hex(entry), calls=[])

    def hook(uc, address, size, context):
        if address not in (stop + 0x100, stop + 0x200):
            return
        esp = uc.reg_read(UC_X86_REG_ESP)
        assert uc.reg_read(UC_X86_REG_ECX) == obj
        raw = get(esp + 4)
        if address == stop + 0x100:
            value = bytes(uc.mem_read(raw, len(path) + 1)).split(b'\0')[0].decode()
            result['calls'].append(dict(kind='string', value=value))
        else:
            result['calls'].append(dict(kind='float', bits=raw))
        uc.reg_write(UC_X86_REG_EIP, get(esp))
        uc.reg_write(UC_X86_REG_ESP, esp + 8)
        uc.reg_write(UC_X86_REG_EAX, 0)

    word(obj, table)
    word(obj + 0x1c, obj)
    word(table + 0x30, stop + 0x100)
    word(table + 0x34, stop + 0x200)
    machine.mem_write(argument, path.encode() + b'\0')
    word(stack + 0x8000, stop)
    word(stack + 0x8004, argument)
    machine.reg_write(UC_X86_REG_ECX, obj + 0x18)
    machine.reg_write(UC_X86_REG_ESP, stack + 0x8000)
    machine.hook_add(UC_HOOK_CODE, hook)
    machine.emu_start(entry, stop, count=100)
    assert machine.reg_read(UC_X86_REG_EIP) == stop
    assert len(result['calls']) == 1 and result['calls'][0]['kind'] == kind
    if kind == 'string':
        assert result['calls'][0]['value'] == path
    return result


def main():
    pe = PE(Path(r'E:\SteamLibrary\steamapps\common\Left 4 Dead 2\bin\engine.dll'))
    digest = hashlib.sha256(pe.raw).hexdigest()
    assert digest == '8a6d468059394bf4cfce32f11dcba12ef45de88da1373084d5a2916d0bf7ba86'
    pointers = [struct.unpack_from('<I', pe.raw, pe.offset(0x103ec550 + slot * 4))[0] for slot in (2, 3)]
    assert pointers == [0x10283310, 0x10283300]
    cases = [replay(pe, pointers[0], 'float'), replay(pe, pointers[1], 'string')]
    report = dict(scope='Native engine thunks, mocked underlying ConVar implementation; no game process writes',
                  target_sha256=digest, vtable='0x103ec550', old_slot=2, correct_string_slot=3, cases=cases,
                  assembly={hex(at): pe.listing(at, before=0, after=32) for at in pointers})
    output = ROOT / 'reports/spray_selector/string_abi.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    assert json.loads(output.read_text(encoding='utf-8')) == report
    print('PASS actual engine: old slot 2 forwards to float, slot 3 forwards the exact string to the parent ConVar')


if __name__ == '__main__':
    main()
