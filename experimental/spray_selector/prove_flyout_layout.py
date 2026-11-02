"""Replay native Flyout layout: a named PnlBackground supplies popup bounds."""

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


def replay(pe, background_name, height, initial_size=(0, 0)):
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    machine.mem_map(pe.base, 0x300000)
    for _, address, size, offset in pe.sections:
        machine.mem_write(address, pe.raw[offset:offset + size])
    data, stack, stop = 0x20000000, 0x21000000, 0x22000000
    for base in (data, stack, stop):
        machine.mem_map(base, 0x10000)
    obj, bg, table = data, data + 0x1000, data + 0x2000
    result = dict(background_name=background_name, design_size=[450, height], initial_size=list(initial_size),
                  size=list(initial_size), lookups=[])

    def word(address, value):
        machine.mem_write(address, struct.pack('<I', value))

    def get(address):
        return struct.unpack('<I', machine.mem_read(address, 4))[0]

    def ret(clean=0, value=0):
        esp = machine.reg_read(UC_X86_REG_ESP)
        target = get(esp)
        machine.reg_write(UC_X86_REG_EAX, value)
        machine.reg_write(UC_X86_REG_ESP, esp + 4 + clean)
        machine.reg_write(UC_X86_REG_EIP, target)

    def hook(uc, address, size, context):
        esp = uc.reg_read(UC_X86_REG_ESP)
        if address == 0x100ceb70:  # FindChildByName(name, recurse)
            name_at = get(esp + 4)
            name = pe.raw[pe.offset(name_at):].split(b'\0', 1)[0].decode()
            result['lookups'].append(name)
            ret(8, bg if name == background_name else 0)
        elif address == 0x100ca5e0:  # GetSize(width*, height*)
            dimensions = [450, height] if uc.reg_read(UC_X86_REG_ECX) == bg else result['size']
            word(get(esp + 4), dimensions[0])
            word(get(esp + 8), dimensions[1])
            ret(8)
        elif address == 0x100ca5b0:  # SetSize(width, height)
            result['size'] = [get(esp + 4), get(esp + 8)]
            ret(8)
        elif address == 0x100cb5d0:  # Sizing fixture has no interactive child buttons.
            ret(value=0)
        elif address in (stop + 0x100, stop + 0x200):
            ret(4)

    word(obj, table)
    word(bg, table)
    word(table + 0x84, stop + 0x100)
    word(table + 0x11c, stop + 0x200)
    word(stack + 0x8000, stop)
    word(stack + 0x8004, 1)
    machine.hook_add(UC_HOOK_CODE, hook)
    machine.reg_write(UC_X86_REG_ESP, stack + 0x8000)
    machine.reg_write(UC_X86_REG_ECX, obj)
    machine.emu_start(0x1002d8d0, stop, count=2000)
    assert machine.reg_read(UC_X86_REG_EIP) == stop
    assert result['lookups'] == ['PnlBackground']
    return result


def main():
    pe = PE(Path(r'E:\SteamLibrary\steamapps\common\Left 4 Dead 2\bin\gameui.dll'))
    digest = hashlib.sha256(pe.raw).hexdigest()
    assert digest == '321ec9b5865582330af61e81eb347da31cc213cc6c95b80d6d98170b8a5fbb40'
    cases = [replay(pe, 'CSPBackground', 330), replay(pe, 'CSPBackground', 330, (450, 330)),
             replay(pe, 'CSPBackground', 245, (450, 245)), replay(pe, 'PnlBackground', 472)]
    assert [case['size'] for case in cases] == [[0, 0], [450, 330], [450, 245], [450, 330]], cases
    report = dict(scope='Actual native layout code with panel services mocked; not a live popup click', target_sha256=digest,
                  layout_va='0x1002d8d0', vertical_scale=struct.unpack_from('<f', pe.raw, pe.offset(0x101683c8))[0], cases=cases)
    output = ROOT / 'reports/spray_selector/flyout_layout.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    assert json.loads(output.read_text(encoding='utf-8')) == report
    print('PASS native layout: old custom popup stays 0x0; explicit grid/confirm sizes stay 450x330 / 450x245 without native list rescaling')


if __name__ == '__main__':
    main()
