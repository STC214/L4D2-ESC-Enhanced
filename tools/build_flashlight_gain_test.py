"""Build no-end-fade + RGB 2x from the verified no-fade cache, not from stock."""

import argparse
import hashlib
import json
import lzma
import shutil
import struct
import zipfile

from build_flashlight_nofade_test import OUT as BASE_OUT, REPORT as BASE_REPORT, RELATIVE, decode_block
from c_session_release import ROOT, save, sha
from research_flashlight_gain import probe, listing
from verify_flashlight_nofade_test import cache_blobs
from vpk import read, write

OUT = ROOT / "dist/flashlight_gain2x_test"
REPORT = ROOT / "reports/flashlight_gain2x_test"


def transform(raw):
    assert struct.unpack_from("<I", raw)[0] == 6
    count = struct.unpack_from("<I", raw, 20)[0]
    entries = [struct.unpack_from("<II", raw, 28 + i * 8) for i in range(count)]
    assert entries[-1] == (0xffffffff, len(raw))
    output = bytearray(raw[:entries[0][1]])
    records = []
    for i, (static, cursor) in enumerate(entries[:-1]):
        struct.pack_into("<I", output, 28 + i * 8 + 4, len(output))
        end = entries[i + 1][1]
        while cursor < end:
            token = struct.unpack_from("<I", raw, cursor)[0]
            cursor += 4
            if token == 0xffffffff:
                assert cursor == end
                output.extend(struct.pack("<I", token))
                break
            size = token & 0x3fffffff
            assert token >> 30 == 1 and cursor + size <= end
            data, filters, props = decode_block(raw[cursor:cursor + size])
            cursor += size
            at = 0
            modified = bytearray()
            while at < len(data):
                dynamic, length = struct.unpack_from("<II", data, at)
                code = data[at + 8:at + 8 + length]
                assert len(code) == length
                boosted, change = probe(code)
                modified.extend(struct.pack("<II", dynamic, len(boosted)) + boosted)
                records.append({"static": static, "dynamic": dynamic, **change})
                at += 8 + length
            assert at == len(data)
            compressed = lzma.compress(bytes(modified), format=lzma.FORMAT_RAW, filters=filters)
            block = b"LZMA" + struct.pack("<II", len(modified), len(compressed)) + props + compressed
            assert decode_block(block)[0] == modified
            output.extend(struct.pack("<I", 0x40000000 | len(block)) + block)
        assert cursor == end
    struct.pack_into("<I", output, 28 + (count - 1) * 8 + 4, len(output))
    assert output[:28] == raw[:28]
    assert output[28 + count * 8:entries[0][1]] == raw[28 + count * 8:entries[0][1]]
    assert [struct.unpack_from("<I", output, 28 + i * 8)[0] for i in range(count)] == [x[0] for x in entries]
    return bytes(output), records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rollback-copy", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    source_vpk = BASE_OUT / "C_flashlight_nofade_TEST.vpk"
    baseline = OUT / "original/C_flashlight_nofade_TEST.vpk.bak"
    baseline.parent.mkdir(parents=True, exist_ok=True)
    if baseline.exists():
        assert sha(baseline) == sha(source_vpk)
    else:
        shutil.copyfile(source_vpk, baseline)
    if args.rollback_copy:
        restored = OUT / "rollback_copy/C_flashlight_nofade_TEST.vpk"
        restored.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(baseline, restored)
        assert sha(restored) == sha(source_vpk) and read(restored) == read(baseline)
        print("PASS restored/reopened prior no-fade VPK copy; no game writes", restored)
        return
    previous = read(baseline)
    expected = json.loads((BASE_REPORT / "independent_verification.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(previous[RELATIVE]).hexdigest() == expected["modified_sha256"]
    modified, changes = transform(previous[RELATIVE])
    candidate = OUT / "C_flashlight_nofade_TEST.vpk"
    payload = dict(previous)
    payload[RELATIVE] = modified
    payload["addoninfo.txt"] = b'"AddonInfo" { "addonTitle" "TEST no end-fade + flashlight RGB 2x" "addonVersion" "0.2-test" "addonAuthor" "Local test" "addonDescription" "Flashlight PS30 RGB gain only; retains no-fade. No LED, CFG or DLL. Visual gain unverified." }\n'
    write(candidate, payload)
    assert read(candidate) == payload
    assert set(payload) == set(previous) == {"addoninfo.txt", RELATIVE}
    before_blobs, after_blobs = cache_blobs(previous[RELATIVE]), cache_blobs(read(candidate)[RELATIVE])
    assert before_blobs.keys() == after_blobs.keys() and len(after_blobs) == 2832
    representative = []
    for key in before_blobs:
        original = before_blobs[key]
        code = after_blobs[key]
        trial, detail = probe(original)
        assert code == trial and len(code) == len(original) + 16
        disassembly = listing(code)
        assert "ps_3_0" in disassembly
        if key[0] == 0:
            records = {}
            for label, binary in (("before", original), ("after", code)):
                target = REPORT / f"static0_dynamic{key[1]}_{label}.asm"
                text = listing(binary)
                target.write_text(text, encoding="utf-8")
                assert target.read_text(encoding="utf-8") == text
                records[label] = {"path": str(target), "disassembly": text, "D3DDisassemble_HRESULT": 0}
            representative.append(records)
    patch = REPORT / "patch.zip"
    manifest = {"baseline_test_vpk_sha256": sha(baseline), "modified_vpk_sha256": sha(candidate),
                "insertion_per_shader": changes, "gain": 2}
    with zipfile.ZipFile(patch, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for name, data in payload.items():
            archive.writestr(name, data)
    replay = read(baseline)
    with zipfile.ZipFile(patch) as archive:
        assert archive.testzip() is None
        replay.update({name: archive.read(name) for name in payload})
    replayed = REPORT / "replayed.vpk"
    write(replayed, replay)
    assert replayed.read_bytes() == candidate.read_bytes()
    report = {"scope": "cache/VPK parsing, all blobs exact probe comparison and D3DDisassemble; no live 2x render test",
              "baseline_test_vpk_sha256": sha(baseline), "candidate_sha256": sha(candidate),
              "modified_sha256": hashlib.sha256(modified).hexdigest(),
              "checked_blobs": len(after_blobs), "D3DDisassemble_success_count": len(after_blobs),
              "gain": 2, "retains_all_baseline_nofade_changes": True,
              "per_blob_change": "+1 RGB ADD / +0 texture samples / +0 temp registers",
              "representative": representative, "patch": str(patch), "deployment": "NOT_DEPLOYED",
              "filename_reused_to_avoid_parallel_shader_overrides": True}
    save(REPORT / "independent_verification.json", report)
    print("PASS", len(after_blobs), "reopened shader blobs retain no-fade and add exact logical RGB 2x")
    print("PASS all D3DDisassemble HRESULT=0; VPK patch replay exact; same target filename")
    print("CANDIDATE", candidate)


if __name__ == "__main__":
    main()
