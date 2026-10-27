"""Extract and disassemble a bounded shipped L4D2 shader-cache combo."""

import hashlib
import lzma
import struct
import subprocess

from c_session_release import ROOT, GAME, save


def main():
    directory = ROOT / "reports/flashlight_native"
    directory.mkdir(parents=True, exist_ok=True)
    target = GAME / "hl2/shaders/fxc/flashlight_ps30.vcs"
    raw = target.read_bytes()
    version, total, dynamic, flags, centroid, count, crc = struct.unpack_from("<7I", raw)
    assert version == 6 and count > 1
    static_id, offset = struct.unpack_from("<II", raw, 28)
    next_id, next_offset = struct.unpack_from("<II", raw, 36)
    block_size = struct.unpack_from("<I", raw, offset)[0]
    assert block_size >> 30 == 1
    block_size &= 0x3fffffff
    block = raw[offset + 4:offset + 4 + block_size]
    assert block[:4] == b"LZMA"
    expected, compressed = struct.unpack_from("<II", block, 4)
    p = block[12]
    filters = [{"id": lzma.FILTER_LZMA1, "dict_size": struct.unpack_from("<I", block, 13)[0],
                "lc": p % 9, "lp": p // 9 % 5, "pb": p // 45}]
    data = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters).decompress(
        block[17:17 + compressed], max_length=expected)
    assert len(data) == expected
    fxc = r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\fxc.exe"
    cursor = 0
    records = []
    while cursor < len(data):
        combo, size = struct.unpack_from("<II", data, cursor)
        code = data[cursor + 8:cursor + 8 + size]
        assert len(code) == size and code[:4] == b"\x00\x03\xff\xff"
        shader = directory / f"flashlight_static{static_id}_dynamic{combo}.bin"
        shader.write_bytes(code)
        assert shader.read_bytes() == code
        command = [fxc, "/nologo", "/dumpbin", str(shader)]
        result = subprocess.run(command, capture_output=True, text=True, errors="replace")
        assert result.returncode == 0, result.stderr
        listing = shader.with_suffix(".asm")
        listing.write_text(result.stdout, encoding="utf-8")
        assert listing.read_text(encoding="utf-8") == result.stdout
        records.append({"combo": combo, "shader_sha256": hashlib.sha256(code).hexdigest(),
                        "command": command, "stdout": result.stdout, "stderr": result.stderr,
                        "exit_status": result.returncode})
        print(result.stdout)
        cursor += 8 + size
    assert cursor == len(data)
    save(directory / "shader_disassembly.json", {
        "path": str(target), "sha256": hashlib.sha256(raw).hexdigest(),
        "version": version, "static_combo": static_id, "dynamic_combo_count_in_header": dynamic,
        "scope": "first static combo block, all its decoded dynamic shader blobs; not live GPU observation",
        "records": records})


if __name__ == "__main__":
    main()
