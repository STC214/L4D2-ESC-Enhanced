"""Inspect VPK directory/CRC and VTF headers only; never decode image pixels."""

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path


def inspect(filename):
    raw = Path(filename).read_bytes()
    if len(raw) < 12:
        raise ValueError("Truncated VPK header")
    signature, version, tree_size = struct.unpack_from("<III", raw)
    if signature != 0x55AA1234 or version not in (1, 2):
        raise ValueError("Unsupported VPK header")
    header = 12 if version == 1 else 28
    end = header + tree_size
    if end > len(raw):
        raise ValueError("Truncated directory")
    data_end = len(raw)
    if version == 2:
        sections = struct.unpack_from("<IIII", raw, 12)
        if end + sum(sections) != len(raw):
            raise ValueError("Invalid section boundaries")
        data_end = end + sections[0]
    at = header

    def token():
        nonlocal at
        stop = raw.find(b"\0", at, end)
        if stop < 0:
            raise ValueError("Truncated directory string")
        value = raw[at:stop].decode("utf-8", errors="strict")
        at = stop + 1
        return value

    entries = []
    while extension := token():
        while directory := token():
            while name := token():
                if at + 18 > end:
                    raise ValueError("Truncated directory entry")
                crc, preload, archive, offset, size, terminator = struct.unpack_from(
                    "<IHHIIH", raw, at
                )
                at += 18
                if terminator != 0xFFFF or at + preload > end:
                    raise ValueError("Invalid entry")
                if size and (archive != 0x7FFF or offset + size > data_end - end):
                    raise ValueError("External archive or invalid payload")
                data = raw[at : at + preload]
                at += preload
                if size:
                    data += raw[end + offset : end + offset + size]
                key = name + ("." + extension if extension != " " else "")
                if directory != " ":
                    key = directory + "/" + key
                item = {
                    "member": key,
                    "bytes": len(data),
                    "crc_ok": zlib.crc32(data) == crc,
                }
                if extension.lower() == "vtf":
                    if len(data) < 64 or data[:4] != b"VTF\0":
                        item["vtf_error"] = "Invalid VTF header"
                    else:
                        major, minor, vtf_header = struct.unpack_from("<III", data, 4)
                        width, height, flags, frames, first_frame = struct.unpack_from(
                            "<HHIHH", data, 16
                        )
                        item["vtf_header"] = {
                            "version": [major, minor],
                            "header_bytes": vtf_header,
                            "width": width,
                            "height": height,
                            "flags": flags,
                            "frames": frames,
                            "first_frame": first_frame,
                            "format": struct.unpack_from("<I", data, 52)[0],
                            "mips": data[56],
                            "depth": struct.unpack_from("<H", data, 63)[0]
                            if minor >= 2 and len(data) >= 65
                            else 1,
                        }
                entries.append(item)
    if at != end:
        raise ValueError("Unexpected directory end")
    return {
        "source": str(Path(filename).resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "vpk_version": version,
        "all_crc_ok": all(item["crc_ok"] for item in entries),
        "inspection": "Directory, CRC and VTF headers only; no pixel decoding/rendering",
        "entries": entries,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vpk")
    parser.add_argument("report")
    args = parser.parse_args()
    result = inspect(args.vpk)
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
