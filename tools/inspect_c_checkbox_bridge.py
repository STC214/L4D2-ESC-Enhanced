"""Inspect the pinned native checkbox/Panel names and hook boundary, read-only."""

import hashlib
import struct

from audit_c_switch_events import PIN
from c_session_release import GAME, ROOT, save
from trace_flashlight_native import PE


def main():
    pe = PE(GAME / "bin/gameui.dll")
    assert hashlib.sha256(pe.raw).hexdigest() == PIN
    report = {"path": str(pe.path), "sha256": PIN, "strings": {}, "vtable": {}}
    for label in ("fieldName", "fieldname", "CheckButtonChecked", "ApplyChanges", "CvarToggleCheckButton", "CvarToggleCheckButton_GameUI"):
        at = pe.raw.find(label.encode() + b"\0")
        if at < 0:
            continue
        va = pe.va(at)
        report["strings"][label] = {"va": hex(va), "refs": {
            hex(ref): pe.listing(ref, before=24, after=100) for ref in pe.refs(va)}}
    for offset in (0, 0x8, 0x10, 0x14, 0x18, 0x1c, 0x20, 0x24, 0x28, 0x2c, 0x30, 0x34, 0x38, 0x3fc, 0x400):
        va = struct.unpack_from("<I", pe.raw, pe.offset(0x1015f674 + offset))[0]
        report["vtable"][hex(offset)] = {"target": hex(va), "assembly": pe.listing(va, before=0, after=48)}
    save(ROOT / "reports/c_checkbox_bridge/inspection.json", report)
    for label, info in report["strings"].items():
        print(label, info["va"], "refs", list(info["refs"]))
    for offset, info in report["vtable"].items():
        print(offset, info["target"])


if __name__ == "__main__":
    main()
