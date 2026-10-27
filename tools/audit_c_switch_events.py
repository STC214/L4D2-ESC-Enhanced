"""Read-only, pinned GameUI checkbox event-path investigation and replay."""

import hashlib
import re
import struct

from c_binary_switches import SWITCHES
from c_session_release import GAME, ROOT, save
from trace_flashlight_native import PE
from inspect_menu import blocks, fields
from vpk import read

PIN = "321ec9b5865582330af61e81eb347da31cc213cc6c95b80d6d98170b8a5fbb40"
RECORD = ROOT / "reports/c_switch_events/investigation.json"


def replay(pe, start, selected, apply):
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP

    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    machine.mem_map(pe.base, 0x300000)
    for _, address, size, offset in pe.sections:
        machine.mem_write(address, pe.raw[offset:offset + size])
    data, stack, stop = 0x20000000, 0x21000000, 0x22000000
    for base in (data, stack, stop):
        machine.mem_map(base, 0x10000)
    obj, table, cvar, cvtable = data, data + 0x1000, data + 0x2000, data + 0x3000
    get_selected, post_signal, set_value = stop + 0x100, stop + 0x200, stop + 0x300

    def word(address, value):
        machine.mem_write(address, struct.pack("<I", value))

    def read_word(address):
        return struct.unpack("<I", machine.mem_read(address, 4))[0]

    word(obj, table)
    word(obj + 0x220, cvar)
    word(cvar, cvtable)
    word(cvtable + 4, set_value)
    word(table + 0x400, get_selected)
    word(table + 0xc0, post_signal)
    machine.mem_write(obj + 0x240, bytes([start]))
    result = {"initial": start, "selected": selected, "apply_changes": apply,
              "value": start, "setter_calls": [], "signals": []}

    def return_from(args, value=0):
        esp = machine.reg_read(UC_X86_REG_ESP)
        target = read_word(esp)
        machine.reg_write(UC_X86_REG_EAX, value)
        machine.reg_write(UC_X86_REG_ESP, esp + 4 + args)
        machine.reg_write(UC_X86_REG_EIP, target)

    def hook(uc, address, size, context):
        esp = uc.reg_read(UC_X86_REG_ESP)
        if address == get_selected:
            return_from(0, selected)
        elif address == 0x100c0af0:  # operator new; caller cleans size
            return_from(0, data + 0x4000)
        elif address == 0x100c0e40:  # KeyValues constructor; thiscall, three args
            name = read_word(esp + 4)
            offset = pe.offset(name)
            result["signals"].append(pe.raw[offset:].split(b"\0", 1)[0].decode())
            return_from(12, data + 0x4000)
        elif address == post_signal:
            return_from(4)
        elif address == 0x10087ae0:  # ConVarRef IsValid
            return_from(0, 1)
        elif address == 0x10087a30:  # split-screen slot
            return_from(0, 0)
        elif address == set_value:
            result["value"] = read_word(esp + 4)
            result["setter_calls"].append(result["value"])
            return_from(4)

    machine.hook_add(UC_HOOK_CODE, hook)
    word(stack + 0x8000, stop)
    machine.reg_write(UC_X86_REG_ESP, stack + 0x8000)
    machine.reg_write(UC_X86_REG_ECX, obj)
    machine.emu_start(0x10004500 if apply else 0x10004550, stop, count=1000)
    assert machine.reg_read(UC_X86_REG_EIP) == stop
    return result


def main():
    pe = PE(GAME / "bin/gameui.dll")
    digest = hashlib.sha256(pe.raw).hexdigest()
    assert digest == PIN, "GameUI changed; re-establish event-path evidence"
    strings = [m.group().decode() for m in re.finditer(rb"[ -~]{5,}\x00", pe.raw)
               if b"Cvar" in m.group() or b"AutoApply" in m.group()]
    cases = [replay(pe, old, new, apply) for old, new in ((0, 1), (1, 0)) for apply in (False, True)]
    from review_c_switch_fix import BASE, BASE_HASH, MENU
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_HASH
    original = {fields(block).get("concommand", "").lower(): fields(block)
                for _, _, _, block in blocks(read(BASE)[MENU].decode("utf-8-sig"))}
    assert all(original[cvar]["controlname"] == "CvarToggleCheckButton" for cvar in SWITCHES)
    for case in cases:
        assert case["value"] == (case["selected"] if case["apply_changes"] else case["initial"])
        assert case["setter_calls"] == ([case["selected"]] if case["apply_changes"] else [])
        assert case["signals"] == ([] if case["apply_changes"] else ["ControlModified"])
    report = {"target": str(pe.path), "sha256": digest, "baseline_vpk": str(BASE), "baseline_sha256": BASE_HASH,
              "scope": "Pinned native handler machine code replay; VGUI dependencies mocked, NOT live UI clicks",
              "button_checked": pe.listing(0x10004550, before=0, after=83),
              "apply_changes": pe.listing(0x10004500, before=0, after=71),
              "factory_candidates": strings, "replays": cases,
              "affected": [{"cvar": cvar, "label": label, "defect": "ControlModified without immediate ApplyChanges"}
                           for cvar, label in SWITCHES.items()]}
    save(RECORD, report)
    print("PASS native checked handler emits ControlModified, zero setter calls, both directions")
    print("PASS explicit ApplyChanges invokes setter, both directions; all 10 controls share this event path")
    print("FACTORIES", strings)
    print("RECORD", RECORD)


if __name__ == "__main__":
    main()
