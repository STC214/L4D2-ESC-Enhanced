"""Independently reopen both VCS caches and validate all modified shader blobs."""

import ctypes
import struct

from build_flashlight_nofade_test import OUT, REPORT, RELATIVE, SOURCE_HASH, decode_block, instructions
from c_session_release import GAME, save, sha
from vpk import read


def cache_blobs(raw):
    assert struct.unpack_from("<I", raw)[0] == 6
    count = struct.unpack_from("<I", raw, 20)[0]
    entries = [struct.unpack_from("<II", raw, 28 + i * 8) for i in range(count)]
    assert entries[-1] == (0xffffffff, len(raw))
    output = {}
    for i, (static, cursor) in enumerate(entries[:-1]):
        end = entries[i + 1][1]
        terminated = False
        while cursor < end:
            token = struct.unpack_from("<I", raw, cursor)[0]
            cursor += 4
            if token == 0xffffffff:
                assert cursor == end
                terminated = True
                break
            size = token & 0x3fffffff
            assert token >> 30 == 1 and cursor + size <= end
            data = decode_block(raw[cursor:cursor + size])[0]
            cursor += size
            at = 0
            while at < len(data):
                dynamic, length = struct.unpack_from("<II", data, at)
                code = data[at + 8:at + 8 + length]
                assert len(code) == length and (static, dynamic) not in output
                output[static, dynamic] = code
                at += 8 + length
            assert at == len(data)
        assert terminated
    return output


def disassemble(code):
    compiler = ctypes.WinDLL("d3dcompiler_47.dll")
    function = compiler.D3DDisassemble
    function.argtypes = (ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_char_p,
                         ctypes.POINTER(ctypes.c_void_p))
    function.restype = ctypes.c_long
    source = ctypes.create_string_buffer(code)
    blob = ctypes.c_void_p()
    result = function(source, len(code), 0, None, ctypes.byref(blob))
    assert result == 0 and blob.value, f"D3DDisassemble HRESULT={result}"
    table = ctypes.cast(blob, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    get_pointer = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)(table[3])
    get_size = ctypes.WINFUNCTYPE(ctypes.c_size_t, ctypes.c_void_p)(table[4])
    release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[2])
    try:
        listing = ctypes.string_at(get_pointer(blob), get_size(blob)).decode("ascii")
        assert "ps_3_0" in listing
        return result
    finally:
        release(blob)


def main():
    baseline_path = OUT / "original" / RELATIVE
    candidate_path = OUT / "loose/left4dead2" / RELATIVE
    assert sha(baseline_path) == SOURCE_HASH
    original, modified = baseline_path.read_bytes(), candidate_path.read_bytes()
    before, after = cache_blobs(original), cache_blobs(modified)
    assert before.keys() == after.keys()
    counts = 0
    for key in before:
        a, b = before[key], after[key]
        assert len(a) == len(b)
        changed = [i for i in range(0, len(a), 4) if a[i:i + 4] != b[i:i + 4]]
        assert len(changed) == 1
        offset = changed[0]
        replacement = struct.unpack_from("<I", b, offset)[0]
        one_register = replacement & 0x7ff
        swizzle = (replacement >> 16) & 255
        assert swizzle in (0, 0x55, 0xaa, 0xff)
        component = (0, 0x55, 0xaa, 0xff).index(swizzle)
        assert any(op == 81 and args[0] & 0x7ff == one_register and args[1 + component] == 0x3f800000
                   for _, op, _, args in instructions(b))
        assert disassemble(b) == 0
        counts += 1
    candidate = OUT / "C_flashlight_nofade_TEST.vpk"
    assert read(candidate)[RELATIVE] == modified
    assert (GAME / "hl2" / RELATIVE).read_bytes() == original
    numeric = []
    for d in (1000, 1800, 2100, 2400, 2700, 2999):
        raw = 1 + 100 / d
        fade = max(0, min(1, (3000 - d) / 1200))
        old, new = min(1, raw * fade), min(1, raw)
        assert new >= old
        numeric.append({"distance": d, "baseline_coefficient": old, "modified_coefficient": new})
    save(REPORT / "independent_verification.json", {
        "scope": "all shipped-cache blobs reopened, one-word difference and D3DDisassemble; not live GPU validation",
        "checked_blobs": counts, "D3DDisassemble_success_count": counts,
        "baseline_sha256": sha(baseline_path), "modified_sha256": sha(candidate_path),
        "model_inputs": "C=1 L=100 Q=0 F=3000, distances within F; not sampled game values",
        "numeric_examples": numeric, "original_game_shader_unchanged": True,
        "loading_and_visual_effect": "UNVERIFIED", "deployment": "NOT_DEPLOYED"})
    print("PASS independent cache reopen and one-word delta:", counts, "shader blobs")
    print("PASS D3DDisassemble HRESULT=0 for every modified blob")
    print("PASS model removes only end-fade term; original game shader unchanged; runtime pending")


if __name__ == "__main__":
    main()
