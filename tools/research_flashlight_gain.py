"""Read-only strength research; in-memory bytecode probes are never packaged/deployed."""

from collections import Counter
import ctypes
import json
import struct

from build_flashlight_nofade_test import instructions, register, OUT, RELATIVE
from c_session_release import ROOT, GAME, save, sha, safe_target
from verify_flashlight_nofade_test import cache_blobs

REPORT = ROOT / "reports/flashlight_gain_research"


def listing(code):
    compiler = ctypes.WinDLL("d3dcompiler_47.dll")
    function = compiler.D3DDisassemble
    function.argtypes = (ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_char_p,
                         ctypes.POINTER(ctypes.c_void_p))
    function.restype = ctypes.c_long
    blob = ctypes.c_void_p()
    source = ctypes.create_string_buffer(code)
    status = function(source, len(code), 0, None, ctypes.byref(blob))
    assert status == 0 and blob.value
    table = ctypes.cast(blob, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    pointer = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)(table[3])
    size = ctypes.WINFUNCTYPE(ctypes.c_size_t, ctypes.c_void_p)(table[4])
    release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[2])
    try:
        return ctypes.string_at(pointer(blob), size(blob)).decode("ascii")
    finally:
        release(blob)


def probe(code):
    rows = instructions(code)
    sites = [(at, args) for at, op, token, args in rows
             if op == 5 and any(register(a) == (2, 28) for a in args[1:])]
    assert len(sites) == 1
    at, args = sites[0]
    dest = args[0]
    assert register(dest)[0] == 0
    mask = (dest >> 16) & 15
    assert mask.bit_count() == 3
    color = next(a for a in args[1:] if register(a) == (2, 28))
    assert not color & 0x0f000000
    # Compiler register allocation can pack logical RGB into xyz, xyw, xzw,
    # or yzw. Check the c28 swizzle, not the temporary lane letters.
    color_components = [((color >> 16) >> (2 * lane)) & 3 for lane in range(4) if mask & (1 << lane)]
    assert sorted(color_components) == [0, 1, 2]
    assert not dest & 0x00f00000  # Color multiplier itself is not saturated.
    src = 0x80e40000 | (dest & 0x7ff)  # Same temporary register, identity swizzle.
    addition = struct.pack("<4I", 0x03000002, dest, src, src)  # add RGB, RGB, RGB
    offset = (at + 1 + len(args)) * 4
    trial = code[:offset] + addition + code[offset:]
    assert trial[:offset] == code[:offset] and trial[offset + 16:] == code[offset:]
    assert len(instructions(trial)) == len(rows) + 1
    return trial, {"insertion_byte_offset": offset, "extra_instructions": 1,
                   "extra_texture_samples": 0, "extra_registers": 0,
                   "gain_site_is_rgb_only": True, "gain_site_has_no_saturate": True}


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    paths = {"deployed_C": safe_target("vpk"), "helper_DLL": safe_target("helper"),
             "deployed_shader_test": GAME / "left4dead2/addons/C_flashlight_nofade_TEST.vpk",
             "stock_shader": GAME / "hl2" / RELATIVE}
    before = {key: sha(path) for key, path in paths.items()}
    cache = OUT / "loose/left4dead2" / RELATIVE
    expected = json.loads((ROOT / "reports/flashlight_nofade_test/independent_verification.json").read_text(encoding="utf-8"))
    assert sha(cache) == expected["modified_sha256"]
    blobs = cache_blobs(cache.read_bytes())
    evidence = []
    representative = []
    counts = Counter()
    for key, code in blobs.items():
        trial, site = probe(code)
        disassembly = listing(trial)
        assert "ps_3_0" in disassembly
        counts["validated_in_memory_2x_probes"] += 1
        evidence.append({"static": key[0], "dynamic": key[1], **site})
        if key[0] == 0:
            baseline_asm = REPORT / f"static{key[0]}_dynamic{key[1]}_baseline.asm"
            probe_asm = REPORT / f"static{key[0]}_dynamic{key[1]}_2x_probe.asm"
            baseline_asm.write_text(listing(code), encoding="utf-8")
            probe_asm.write_text(disassembly, encoding="utf-8")
            assert baseline_asm.read_text(encoding="utf-8") == listing(code)
            assert probe_asm.read_text(encoding="utf-8") == disassembly
            representative.append({"baseline": str(baseline_asm), "probe": str(probe_asm)})
    assert len(evidence) == 2832
    after = {key: sha(path) for key, path in paths.items()}
    assert after == before
    save(REPORT / "analysis.json", {
        "scope": "shipped-cache analysis + in-memory bytecode structure probes, not game/GPU execution",
        "input_cache_sha256": sha(cache), "color_constant_register": "c28 / cFlashlightColor",
        "observations": {"shader_blobs": len(evidence), "unique_rgb_color_sites_per_blob": 1,
                         "all_gain_sites_unsaturated": True, "D3DDisassemble_success_count": counts["validated_in_memory_2x_probes"]},
        "proposed_method": "add RGB,RGB,RGB directly after texture * cFlashlightColor; retain no-fade patch",
        "evidence": evidence, "representative_listings": representative,
        "game_hashes_before": before, "game_hashes_after": after,
        "user_reported_runtime_evidence": "Existing no-fade test suppresses end fade; overall brightness insufficient",
        "limitations": ["No in-game 2x probe executed or deployed", "No measured screen-luminance multiplier",
                        "Tone mapping/exposure and HDR/LDR render target may clip/compress results",
                        "Only flashlight_ps30 covered, not independent eye/teeth shader files"],
        "new_runtime_mod_created": False, "deployment": "UNCHANGED"})
    print("PASS", len(evidence), "color sites: c28 RGB multiply, no saturation at gain site")
    print("PASS all in-memory 2x probes disassemble; +1 RGB ADD, +0 samples/registers; alpha untouched")
    print("PASS C, helper, deployed no-fade test and stock shader hashes unchanged")
    print("REPORT", REPORT / "analysis.json")


if __name__ == "__main__":
    main()
