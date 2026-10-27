"""Build an isolated shader-cache experiment; never install or change C.

Only the fade operand of the final attenuation multiply is replaced by an
existing literal 1. Instruction lengths, shader reflection and all other
operands are preserved. Every dynamic blob in every unique static block is
checked; unfamiliar layouts fail rather than producing a partial patch.
"""

import argparse
import hashlib
import json
import lzma
from pathlib import Path
import struct
import subprocess
import zipfile

from c_session_release import ROOT, GAME, save, sha
from vpk import read, write

OUT = ROOT / "dist/flashlight_nofade_test"
REPORT = ROOT / "reports/flashlight_nofade_test"
RELATIVE = "shaders/fxc/flashlight_ps30.vcs"
SOURCE_HASH = "cd9b779c792d9391c82da548d155efe80801812fda0f41585725bc766cd3829f"


def instructions(code):
    words = struct.unpack("<" + "I" * (len(code) // 4), code)
    assert words[0] == 0xffff0300
    cursor = 1
    rows = []
    while cursor < len(words):
        token = words[cursor]
        op = token & 0xffff
        if op == 0xffff:
            assert cursor == len(words) - 1
            return rows
        length = ((token >> 16) & 0x7fff) if op == 0xfffe else ((token >> 24) & 15)
        assert length and cursor + length < len(words)
        rows.append((cursor, op, token, words[cursor + 1:cursor + length + 1]))
        cursor += 1 + length
    raise AssertionError("Missing shader END")


def register(token):
    return ((token >> 28) & 7) | ((token >> 8) & 0x18), token & 0x7ff


def patch_shader(code):
    rows = instructions(code)
    ones = []
    for _, op, _, args in rows:
        if op == 81:  # DEF cN, literal.x/y/z/w
            for component, value in enumerate(args[1:]):
                if value == 0x3f800000:
                    ones.append(0xa0000000 | args[0] & 0x7ff | ((component * 0x55) << 16))
    assert ones
    patches = []
    for i, (_, op, _, args) in enumerate(rows):
        if op != 8 or len(args) != 3 or register(args[1]) != (2, 13):
            continue  # DP3 attenuation = c13 dot (1,1/d,1/d²).
        for j in range(i + 1, min(i + 14, len(rows))):
            at, operation, token, operands = rows[j]
            if operation != 5 or len(operands) != 3 or not operands[0] & 0x00100000:
                continue  # MUL_SAT
            if register(operands[1]) != register(args[0]):
                continue
            mask = (args[0] >> 16) & 15
            assert mask and not mask & (mask - 1)
            component = mask.bit_length() - 1
            if (operands[1] >> 16) & 255 != component * 0x55:
                continue
            prev = rows[j - 1]
            assert prev[1] == 5 and prev[3][0] & 0x00100000
            assert register(prev[3][0]) == register(operands[2])
            assert register(operands[2])[0] == 0
            # The preceding calculation must explicitly use farZ and -0.4.
            near = rows[i + 1:j]
            assert any(register(a) == (2, 13) and (a >> 16) & 255 == 255
                       for _, _, _, operands_ in near for a in operands_)
            assert any(op_ == 81 and 0xbecccccd in operands_ for _, op_, _, operands_ in rows)
            patches.append((4 * (at + 3), operands[2], ones[0]))
            break
    assert len(patches) == 1, f"Expected one verified fade multiply, got {len(patches)}"
    output = bytearray(code)
    for offset, before, after in patches:
        assert struct.unpack_from("<I", output, offset)[0] == before
        struct.pack_into("<I", output, offset, after)
    assert len(output) == len(code)
    assert instructions(output)
    changed = [i for i in range(0, len(code), 4) if code[i:i + 4] != output[i:i + 4]]
    assert changed == [p[0] for p in patches]
    return bytes(output), [{"byte_offset": p[0], "before": hex(p[1]), "after": hex(p[2])} for p in patches]


def decode_block(block):
    assert block[:4] == b"LZMA"
    expected, compressed = struct.unpack_from("<II", block, 4)
    assert len(block) == 17 + compressed
    p = block[12]
    filters = [{"id": lzma.FILTER_LZMA1, "dict_size": struct.unpack_from("<I", block, 13)[0],
                "lc": p % 9, "lp": p // 9 % 5, "pb": p // 45}]
    data = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters).decompress(block[17:], max_length=expected)
    assert len(data) == expected
    return data, filters, block[12:17]


def transform(raw, verify_against=None):
    header = struct.unpack_from("<7I", raw)
    assert header[0] == 6
    count = header[5]
    entries = [struct.unpack_from("<II", raw, 28 + i * 8) for i in range(count)]
    assert entries[-1] == (0xffffffff, len(raw))
    assert all(entries[i][1] < entries[i + 1][1] for i in range(count - 1))
    output = bytearray(raw[:entries[0][1]])
    changes = []
    examples = []
    for i, (static_id, offset) in enumerate(entries[:-1]):
        struct.pack_into("<I", output, 28 + i * 8 + 4, len(output))
        end = entries[i + 1][1]
        while offset < end:
            token = struct.unpack_from("<I", raw, offset)[0]
            offset += 4
            if token == 0xffffffff:
                output.extend(struct.pack("<I", token))
                assert offset == end
                break
            assert token >> 30 == 1, "Unreviewed cache block compression"
            length = token & 0x3fffffff
            data, filters, props = decode_block(raw[offset:offset + length])
            offset += length
            cursor = 0
            modified = bytearray()
            while cursor < len(data):
                combo, size = struct.unpack_from("<II", data, cursor)
                code = data[cursor + 8:cursor + 8 + size]
                assert len(code) == size
                try:
                    patched, patch = patch_shader(code)
                except AssertionError as exc:
                    diagnostic = REPORT / "unrecognized_shader.bin"
                    diagnostic.write_bytes(code)
                    raise AssertionError(f"static={static_id} dynamic={combo}: {exc}; saved {diagnostic}") from exc
                if static_id == 0:
                    examples.append((combo, code, patched))
                modified.extend(struct.pack("<II", combo, size) + patched)
                changes.append({"static": static_id, "dynamic": combo, "patch": patch})
                cursor += 8 + size
            assert cursor == len(data) and len(modified) == len(data)
            compressed = lzma.compress(bytes(modified), format=lzma.FORMAT_RAW, filters=filters)
            block = b"LZMA" + struct.pack("<II", len(modified), len(compressed)) + props + compressed
            assert decode_block(block)[0] == modified
            output.extend(struct.pack("<I", 0x40000000 | len(block)) + block)
        assert offset == end
    struct.pack_into("<I", output, 28 + (count - 1) * 8 + 4, len(output))
    # Static IDs, aliases, header, reflection and source CRC are not rewritten.
    assert output[:28] == raw[:28]
    assert output[28 + count * 8:entries[0][1]] == raw[28 + count * 8:entries[0][1]]
    assert all(struct.unpack_from("<I", output, 28 + i * 8)[0] == entry[0] for i, entry in enumerate(entries))
    return bytes(output), changes, examples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rollback-copy", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    if args.rollback_copy:
        source_copy = OUT / "original" / RELATIVE
        assert sha(source_copy) == SOURCE_HASH
        restored_copy = OUT / "rollback_copy" / RELATIVE
        restored_copy.parent.mkdir(parents=True, exist_ok=True)
        restored_copy.write_bytes(source_copy.read_bytes())
        assert sha(restored_copy) == SOURCE_HASH
        print("PASS restored/reopened original shader copy; no game writes:", restored_copy)
        return
    source = GAME / "hl2" / RELATIVE
    assert sha(source) == SOURCE_HASH
    original = source.read_bytes()
    backup = OUT / "original" / RELATIVE
    backup.parent.mkdir(parents=True, exist_ok=True)
    if backup.exists():
        assert backup.read_bytes() == original
    else:
        backup.write_bytes(original)
    modified, patches, examples = transform(original)
    target = OUT / "loose/left4dead2" / RELATIVE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(modified)
    assert target.read_bytes() == transform(backup.read_bytes())[0]
    records = []
    compiler = r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\fxc.exe"
    for combo, before, after in examples:
        for label, data in (("before", before), ("after", after)):
            binary = REPORT / f"static0_dynamic{combo}_{label}.bin"
            binary.write_bytes(data)
            command = [compiler, "/nologo", "/dumpbin", str(binary)]
            result = subprocess.run(command, capture_output=True, text=True, errors="replace")
            assert result.returncode == 0, result.stderr
            binary.with_suffix(".asm").write_text(result.stdout, encoding="utf-8")
            records.append({"command": command, "stdout": result.stdout, "stderr": result.stderr,
                            "exit_status": result.returncode})
    patch_manifest = REPORT / "shader_operand_patch.json"
    save(patch_manifest, {"source_sha256": SOURCE_HASH, "modified_sha256": sha(target),
                          "shader_member": RELATIVE, "per_blob_operand_changes": patches})
    patch_zip = REPORT / "patch.zip"
    with zipfile.ZipFile(patch_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(patch_manifest, "shader_operand_patch.json")
        archive.writestr(RELATIVE, modified)
    with zipfile.ZipFile(patch_zip) as archive:
        assert archive.testzip() is None and archive.read(RELATIVE) == modified
        assert json.loads(archive.read("shader_operand_patch.json"))["source_sha256"] == SOURCE_HASH
    info = b'"AddonInfo" { "addonTitle" "TEST flashlight end-fade disabled PS30" "addonVersion" "0.1-test" "addonAuthor" "Local test" "addonDescription" "PS30 flashlight only. No LED, CFG or DLL. Runtime loading unverified." }\n'
    vpk = OUT / "C_flashlight_nofade_TEST.vpk"
    write(vpk, {"addoninfo.txt": info, RELATIVE: modified})
    assert read(vpk) == {"addoninfo.txt": info, RELATIVE: modified}
    control = OUT / "baseline_control_DO_NOT_ENABLE_WITH_TEST.vpk"
    write(control, {"addoninfo.txt": info.replace(b"disabled", b"baseline"), RELATIVE: original})
    assert read(control)[RELATIVE] == original
    archive_path = OUT / "C_flashlight_nofade_loose_TEST.zip"
    guide = (ROOT / "docs/FLASHLIGHT_NOFADE_TEST.md").read_bytes()
    (OUT / "README.md").write_bytes(guide)
    assert (OUT / "README.md").read_bytes() == guide
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("left4dead2/" + RELATIVE, modified)
        archive.writestr("README.md", guide)
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None and archive.read("left4dead2/" + RELATIVE) == modified
        assert archive.read("README.md") == guide
    # Runnable rollback role is a clean original cache copy, never a game write.
    restored = OUT / "rollback_copy" / RELATIVE
    restored.parent.mkdir(parents=True, exist_ok=True)
    restored.write_bytes(backup.read_bytes())
    assert sha(restored) == SOURCE_HASH
    light = read(ROOT / "originals/LIGHT_962925054.vpk")
    assert set(light) == {"materials/effects/flashlight001.vtf", "addoninfo.txt"}
    from inspect_bright_flashlight import measure
    stats = measure(light["materials/effects/flashlight001.vtf"])
    save(REPORT / "verification.json", {
        "scope": "all unique static blocks/dynamic blobs in flashlight_ps30 only; no live game test",
        "source": str(source), "source_sha256": SOURCE_HASH, "modified_sha256": sha(target),
        "patched_shader_blobs": len(patches), "patches": patches, "records": records,
        "artifacts": {str(p.relative_to(ROOT)): sha(p) for p in (vpk, control, archive_path, backup, restored, patch_manifest, patch_zip)},
        "workshop_962925054": {"members": list(light), "texture_stats": stats,
                                 "changes_shader_or_distance_parameters": False},
        "deployment": "NOT_DEPLOYED", "runtime_loading_and_visual_effect": "UNVERIFIED"})
    print("PASS unique shader blobs patched:", len(patches))
    print("PASS one source-operand word per blob; all cache blocks decoded/recompressed/reopened")
    print("PASS representative before/after D3D disassembly, VPK/ZIP reopen and original rollback copy")
    print("TEST VPK", vpk)
    print("LOOSE TEST ZIP", archive_path)


if __name__ == "__main__":
    main()
